"""
INVENTARIO DE INSUMOS (2026-10-12). La existencia es el resultado de los
movimientos: compras suman (con conversión de unidades y costo promedio),
ventas restan según la receta, las anulaciones revierten, y el historial
siempre explica la existencia actual.
"""
from decimal import Decimal

import pytest

from tests.conftest import API_V1 as API, PROVEEDOR_PRUEBA, comprar, crear_insumo, crear_plato, existencia


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    return client, auth_headers_factory(usuario_factory(tenant, nombre_completo="Ana Bodega"))


def _movimientos(client, h, insumo_id):
    return client.get(f"{API}/inventario/insumos/{insumo_id}/movimientos", headers=h).json()["items"]


def _vender(client, h, plato_id, cantidad):
    """Enviar la orden es lo que saca los insumos de la bodega."""
    return client.post(f"{API}/ordenes", headers=h, json={"tipo": "llevar", "items": [{"producto_id": plato_id, "cantidad": cantidad}]})


def test_el_insumo_nace_en_cero_y_la_existencia_no_se_edita(s):
    client, h = s
    queso = crear_insumo(client, h, "Queso", "kg", costo="20000")
    assert Decimal(queso["existencia"]) == 0
    r = client.put(f"{API}/inventario/insumos/{queso['id']}", headers=h, json={"existencia": "500", "minimo": "2"})
    assert r.status_code == 200 and Decimal(r.json()["existencia"]) == 0 and Decimal(r.json()["minimo"]) == 2


def test_la_existencia_inicial_queda_como_movimiento_con_trazabilidad(s):
    client, h = s
    arroz = crear_insumo(client, h, "Arroz", "kg", costo="4000", existencia="12.5")
    assert Decimal(arroz["existencia"]) == Decimal("12.5")
    movs = _movimientos(client, h, arroz["id"])
    assert [(m["tipo"], Decimal(m["cantidad"]), m["usuario_nombre"]) for m in movs] == [("inicial", Decimal("12.5"), "Ana Bodega")]


def test_se_compra_en_kg_y_se_lleva_en_g_con_costo_por_gramo(s):
    client, h = s
    queso = crear_insumo(client, h, "Queso", "g")
    compra = comprar(client, h, [(queso["id"], "2", "kg", "30000")])
    assert compra["total"] == "60000.00" and compra["items"][0]["unidad"] == "kg"
    assert existencia(client, h, queso["id"]) == Decimal("2000")
    detalle = client.get(f"{API}/inventario/insumos/{queso['id']}", headers=h).json()
    assert Decimal(detalle["costo_unitario"]) == Decimal("30")  # $30 el gramo
    assert Decimal(detalle["costo_total"]) == Decimal("60000")


def test_el_costo_es_promedio_ponderado_y_anular_lo_devuelve(s):
    client, h = s
    pollo = crear_insumo(client, h, "Pollo", "kg")
    comprar(client, h, [(pollo["id"], "10", "kg", "10000")])
    segunda = comprar(client, h, [(pollo["id"], "10", "kg", "14000")])
    detalle = client.get(f"{API}/inventario/insumos/{pollo['id']}", headers=h).json()
    assert Decimal(detalle["costo_unitario"]) == Decimal("12000")
    assert client.post(f"{API}/compras/compras/{segunda['id']}/anular", headers=h).status_code == 200
    detalle = client.get(f"{API}/inventario/insumos/{pollo['id']}", headers=h).json()
    assert Decimal(detalle["existencia"]) == 10 and Decimal(detalle["costo_unitario"]) == Decimal("10000")


def test_una_unidad_incompatible_se_rechaza_con_la_causa(s):
    client, h = s
    huevo = crear_insumo(client, h, "Huevo", "unidad")
    proveedor = client.post(f"{API}/compras/proveedores", headers=h, json=PROVEEDOR_PRUEBA).json()
    r = client.post(f"{API}/compras/compras", headers=h, json={
        "proveedor_id": proveedor["id"], "fecha": "2026-01-01T09:00:00", "confirmar": True,
        "items": [{"insumo_id": huevo["id"], "cantidad": "1", "unidad": "kg", "precio_unitario": "5000"}],
    })
    assert r.status_code == 409 and "Huevo se lleva en unidad: no se puede comprar en kg" in r.json()["detail"]


def test_la_venta_descuenta_por_receta_con_merma_y_anular_devuelve(s):
    client, h = s
    papa = crear_insumo(client, h, "Papa", "kg")
    aceite = crear_insumo(client, h, "Aceite", "L")
    comprar(client, h, [(papa["id"], "10", "kg", "2000"), (aceite["id"], "2", "L", "10000")])
    # 200 g de papa con 10 % de merma = 220 g por porción; 40 ml de aceite.
    papas = crear_plato(client, h, "Papas fritas", "6000", receta=[(papa["id"], "200", "g", "10"), (aceite["id"], "40", "ml")])

    venta = _vender(client, h, papas["id"], 5)
    assert venta.status_code == 201, venta.json()
    assert existencia(client, h, papa["id"]) == Decimal("8.9")  # 10 - 5 × 0,22
    assert existencia(client, h, aceite["id"]) == Decimal("1.8")  # 2 - 5 × 0,04

    movs = _movimientos(client, h, papa["id"])
    assert movs[0]["tipo"] == "venta" and Decimal(movs[0]["cantidad"]) == Decimal("-1.1")
    assert Decimal(movs[0]["valor"]) == Decimal("-2200")  # costo de lo vendido: 1,1 kg × $2.000

    assert client.post(f"{API}/ordenes/{venta.json()['id']}/anular", headers=h, json={"motivo": "Prueba"}).status_code == 200
    assert existencia(client, h, papa["id"]) == Decimal("10") and existencia(client, h, aceite["id"]) == Decimal("2")
    tipos = [m["tipo"] for m in _movimientos(client, h, papa["id"])]
    assert tipos == ["anulacion_orden", "venta", "compra"]
    assert sum(Decimal(m["cantidad"]) for m in _movimientos(client, h, papa["id"])) == existencia(client, h, papa["id"])


def test_si_un_insumo_no_alcanza_no_se_descuenta_nada_y_dice_cuanto_queda(s):
    client, h = s
    queso = crear_insumo(client, h, "Queso", "kg")
    pan = crear_insumo(client, h, "Pan", "unidad")
    comprar(client, h, [(queso["id"], "0.2", "kg", "20000"), (pan["id"], "10", "unidad", "500")])
    hamburguesa = crear_plato(client, h, "Hamburguesa", "15000", receta=[(pan["id"], "1", "unidad"), (queso["id"], "100", "g")])

    r = _vender(client, h, hamburguesa["id"], 3)
    assert r.status_code == 409
    assert r.json()["detail"] == "No se pudo enviar la orden: quedan 200 g de Queso y la orden necesita 300 g."
    assert r.json()["datos"]["faltantes"][0]["insumo"] == "Queso"
    assert existencia(client, h, pan["id"]) == 10  # tampoco se tocó el pan
    assert client.get(f"{API}/ordenes", headers=h, params={"vista": "todas"}).json()["total"] == 0


def test_vender_sin_existencias_si_el_restaurante_lo_permite(s):
    client, h = s
    config = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    client.put(f"{API}/ajustes/restaurante", headers=h, json={**config, "vender_sin_existencias": True})
    gaseosa = crear_insumo(client, h, "Gaseosa", "unidad")
    plato = crear_plato(client, h, "Gaseosa fría", "3000", receta=[(gaseosa["id"], "1", "unidad")])
    assert _vender(client, h, plato["id"], 2).status_code == 201
    assert existencia(client, h, gaseosa["id"]) == -2


def test_anular_compra_con_existencia_ya_gastada_se_bloquea(s):
    client, h = s
    arroz = crear_insumo(client, h, "Arroz", "kg")
    compra = comprar(client, h, [(arroz["id"], "5", "kg", "4000")])
    plato = crear_plato(client, h, "Arroz blanco", "4000", receta=[(arroz["id"], "1", "kg")])
    assert _vender(client, h, plato["id"], 4).status_code == 201
    r = client.post(f"{API}/compras/compras/{compra['id']}/anular", headers=h)
    assert r.status_code == 409 and "quedan 1 kg y esta compra ingresó 5 kg" in r.json()["detail"]
    assert existencia(client, h, arroz["id"]) == 1


def test_proveedor_surte_insumos_y_el_insumo_conoce_sus_proveedores(s, tenant_factory, usuario_factory, auth_headers_factory):
    client, h = s
    arroz = crear_insumo(client, h, "Arroz", "kg")
    frijol = crear_insumo(client, h, "Fríjol", "kg")
    proveedor = client.post(f"{API}/compras/proveedores", headers=h, json={**PROVEEDOR_PRUEBA, "insumo_ids": [arroz["id"], frijol["id"]]}).json()
    assert sorted(i["nombre"] for i in proveedor["insumos"]) == ["Arroz", "Fríjol"]
    detalle = client.get(f"{API}/inventario/insumos/{arroz['id']}", headers=h).json()
    assert [p["nombre"] for p in detalle["proveedores"]] == ["Proveedor de Pruebas"]
    filtrado = client.get(f"{API}/inventario/insumos", headers=h, params={"proveedor_id": proveedor["id"]}).json()
    assert filtrado["total"] == 2

    ajeno = crear_insumo(client, auth_headers_factory(usuario_factory(tenant_factory())), "Ajeno")
    r = client.put(f"{API}/compras/proveedores/{proveedor['id']}", headers=h, json={**PROVEEDOR_PRUEBA, "insumo_ids": [ajeno["id"]]})
    assert r.status_code == 404


def test_un_insumo_en_una_receta_o_con_movimientos_no_se_elimina(s):
    client, h = s
    tomate = crear_insumo(client, h, "Tomate", "kg")
    crear_plato(client, h, "Ensalada", "5000", receta=[(tomate["id"], "100", "g")])
    r = client.delete(f"{API}/inventario/insumos/{tomate['id']}", headers=h)
    assert r.status_code == 409 and "está en la receta de Ensalada" in r.json()["detail"]

    sal = crear_insumo(client, h, "Sal", "kg", existencia="1")
    r = client.delete(f"{API}/inventario/insumos/{sal['id']}", headers=h)
    assert r.status_code == 409 and "1 movimiento de inventario" in r.json()["detail"]

    libre = crear_insumo(client, h, "Libre", "kg")
    assert client.delete(f"{API}/inventario/insumos/{libre['id']}", headers=h).status_code == 204


def test_la_unidad_no_cambia_si_el_insumo_ya_se_usa(s):
    client, h = s
    leche = crear_insumo(client, h, "Leche", "L", existencia="3")
    r = client.put(f"{API}/inventario/insumos/{leche['id']}", headers=h, json={"unidad": "kg"})
    assert r.status_code == 409 and "No se puede cambiar la unidad de Leche" in r.json()["detail"]


def test_filtro_bajo_minimo_y_grupos(s):
    client, h = s
    crear_insumo(client, h, "Arroz", "kg", minimo="5", existencia="2", grupo="Abarrotes")
    crear_insumo(client, h, "Aceite", "L", minimo="1", existencia="3", grupo="Abarrotes")
    crear_insumo(client, h, "Pollo", "kg", grupo="Carnes")
    bajos = client.get(f"{API}/inventario/insumos", headers=h, params={"bajo_minimo": True}).json()["items"]
    assert [i["nombre"] for i in bajos] == ["Arroz"] and bajos[0]["bajo_minimo"] is True
    assert client.get(f"{API}/inventario/grupos", headers=h).json() == ["Abarrotes", "Carnes"]


def test_quien_no_ve_costos_no_los_ve_ni_los_escribe(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h_admin = auth_headers_factory(usuario_factory(tenant))
    bodega = auth_headers_factory(usuario_factory(tenant, rol=rol_factory(tenant, nombre="Bodega", permisos={"insumos": ["ver", "crear", "editar"]})))
    carne = crear_insumo(client, h_admin, "Carne", "kg", costo="25000")
    visto = client.get(f"{API}/inventario/insumos/{carne['id']}", headers=bodega).json()
    assert visto["costo_unitario"] is None and visto["costo_total"] is None
    client.put(f"{API}/inventario/insumos/{carne['id']}", headers=bodega, json={"costo_unitario": "1"})
    assert Decimal(client.get(f"{API}/inventario/insumos/{carne['id']}", headers=h_admin).json()["costo_unitario"]) == 25000
