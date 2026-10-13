"""
CAJA (fase 6, 2026-10-12): cobrar una orden la convierte en venta con
comprobante interno; varios medios de pago, propina voluntaria, impuesto al
consumo desglosado, dividir la cuenta; apertura y cierre con cuadre por medio
de pago; gastos que salen de la caja.
"""
from decimal import Decimal

import pytest

from tests.conftest import API_V1 as API, abrir_caja, crear_insumo, crear_plato, tomar_orden


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h = auth_headers_factory(usuario_factory(tenant, nombre_completo="Carla Caja"))
    pan = crear_insumo(client, h, "Pan", "unidad", existencia="100")
    botella = crear_insumo(client, h, "Botella", "unidad", existencia="100")
    sandwich = crear_plato(client, h, "Sándwich", "10800", receta=[(pan["id"], "1", "unidad")])
    gaseosa = crear_plato(client, h, "Gaseosa", "5400", receta=[(botella["id"], "1", "unidad")], va_a_cocina=False)
    return client, h, sandwich, gaseosa, pan


def _cobrar(client, h, orden, pagos, **extra):
    return client.post(f"{API}/caja/cobros", headers=h, json={"orden_id": orden["id"], "pagos": pagos, **extra})


def test_sin_caja_abierta_no_se_cobra_y_no_se_abren_dos(s):
    client, h, sandwich, _, _ = s
    orden = tomar_orden(client, h, [sandwich["id"]])
    r = _cobrar(client, h, orden, [{"medio": "efectivo", "monto": "10800"}])
    assert r.status_code == 409 and "La caja está cerrada" in r.json()["detail"]
    abrir_caja(client, h, "100000")
    otra = client.post(f"{API}/caja/abrir", headers=h, json={"base_inicial": "0"})
    assert otra.status_code == 409 and "ya está abierta" in otra.json()["detail"]


def test_cobro_con_dos_medios_devueltas_impuesto_y_propina(s):
    client, h, sandwich, gaseosa, _ = s
    abrir_caja(client, h, "100000")
    orden = tomar_orden(client, h, [(sandwich["id"], 2), gaseosa["id"]], cliente_nombre="Ana María")
    # 2 × 10.800 + 5.400 = 27.000 con el 8 % incluido → base 25.000 + impuesto 2.000; propina 2.700.
    r = _cobrar(client, h, orden, [
        {"medio": "efectivo", "monto": "20000", "recibido": "50000"},
        {"medio": "nequi", "monto": "9700"},
    ], propina="2700")

    assert r.status_code == 201, r.text
    v = r.json()
    assert v["codigo"] == "CI-000001" and v["estado"] == "completada" and v["cajero_nombre"] == "Carla Caja"
    assert (Decimal(v["subtotal"]), Decimal(v["impuesto"]), Decimal(v["total"]), Decimal(v["propina"])) == (25000, 2000, 27000, 2700)
    assert Decimal(v["total_pagado"]) == 29700 and v["cliente_nombre"] == "Ana María"
    efectivo = next(p for p in v["pagos"] if p["medio"] == "efectivo")
    assert Decimal(efectivo["cambio"]) == 30000
    detalle = client.get(f"{API}/ordenes/{orden['id']}", headers=h).json()
    assert detalle["estado"] == "cobrada" and detalle["eventos"][-1]["tipo"] == "cobrada"

    caja = client.get(f"{API}/caja/actual", headers=h).json()["caja"]["resumen"]
    assert caja["ventas"] == 1 and Decimal(caja["propinas"]) == 2700
    assert Decimal(caja["esperado"]["efectivo"]) == 120000 and Decimal(caja["esperado"]["nequi"]) == 9700


def test_los_pagos_deben_sumar_exacto(s):
    client, h, sandwich, _, _ = s
    abrir_caja(client, h)
    orden = tomar_orden(client, h, [sandwich["id"]])
    falta = _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "10000"}])
    assert falta.status_code == 409 and falta.json()["detail"] == "Los pagos suman $ 10.000 y la cuenta es $ 10.800: faltan $ 800."
    sobra = _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "11000"}])
    assert "sobran $ 200" in sobra.json()["detail"]
    poco = _cobrar(client, h, orden, [{"medio": "efectivo", "monto": "10800", "recibido": "10000"}])
    assert poco.status_code == 422 and "no alcanza" in poco.text
    assert _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "10800"}]).status_code == 201
    otra_vez = _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "10800"}])
    assert otra_vez.status_code == 409 and "ya está cobrada" in otra_vez.json()["detail"]


def test_impuesto_que_no_va_incluido_se_suma(s):
    client, h, sandwich, _, _ = s
    ajustes = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    client.put(f"{API}/ajustes/restaurante", headers=h, json={**ajustes, "impuesto_consumo": {"aplica": True, "tasa": "8", "incluido_en_precio": False}})
    abrir_caja(client, h)
    orden = tomar_orden(client, h, [sandwich["id"]])
    v = _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "11664"}]).json()
    assert (Decimal(v["subtotal"]), Decimal(v["impuesto"]), Decimal(v["total"])) == (10800, 864, 11664)


def test_dividir_la_cuenta_por_platos_y_dentro_de_una_linea(s):
    client, h, sandwich, gaseosa, _ = s
    abrir_caja(client, h)
    orden = tomar_orden(client, h, [(sandwich["id"], 2), gaseosa["id"]])
    sand, gas = orden["items"]
    # Persona 1: un sándwich y la gaseosa.
    r = _cobrar(client, h, orden, [{"medio": "efectivo", "monto": "16200"}],
                items=[{"orden_item_id": sand["id"], "cantidad": 1}, {"orden_item_id": gas["id"]}])
    assert r.status_code == 201, r.text
    assert [(i["nombre"], i["cantidad"]) for i in r.json()["items"]] == [("Sándwich", 1), ("Gaseosa", 1)]
    pendiente = next(o for o in client.get(f"{API}/caja/por-cobrar", headers=h).json() if o["id"] == orden["id"])
    assert Decimal(pendiente["por_cobrar"]) == 10800 and Decimal(pendiente["ya_cobrado"]) == 16200
    assert client.get(f"{API}/ordenes/{orden['id']}", headers=h).json()["estado"] == "abierta"
    # Persona 2: el resto.
    r2 = _cobrar(client, h, orden, [{"medio": "daviplata", "monto": "10800"}])
    assert r2.status_code == 201 and r2.json()["codigo"] == "CI-000002"
    assert client.get(f"{API}/ordenes/{orden['id']}", headers=h).json()["estado"] == "cobrada"


def test_anular_un_cobro_devuelve_los_platos_a_por_cobrar_mientras_la_caja_este_abierta(s):
    client, h, sandwich, _, pan = s
    abrir_caja(client, h)
    orden = tomar_orden(client, h, [sandwich["id"]])
    v = _cobrar(client, h, orden, [{"medio": "efectivo", "monto": "10800"}]).json()
    r = client.post(f"{API}/caja/ventas/{v['id']}/anular", headers=h, json={"motivo": "Se cobró a la mesa equivocada"})
    assert r.status_code == 200 and r.json()["estado"] == "anulada"
    assert client.get(f"{API}/ordenes/{orden['id']}", headers=h).json()["estado"] == "abierta"
    # Los insumos NO vuelven: la comida se sirvió.
    assert Decimal(client.get(f"{API}/inventario/insumos/{pan['id']}", headers=h).json()["existencia"]) == 99
    assert Decimal(client.get(f"{API}/caja/actual", headers=h).json()["caja"]["resumen"]["esperado"]["efectivo"]) == 0

    v2 = _cobrar(client, h, orden, [{"medio": "efectivo", "monto": "10800"}]).json()
    client.post(f"{API}/caja/cerrar", headers=h, json={"contado": {"efectivo": "10800"}})
    tarde = client.post(f"{API}/caja/ventas/{v2['id']}/anular", headers=h, json={"motivo": "Tarde"})
    assert tarde.status_code == 409 and "ya se cerró" in tarde.json()["detail"]


def test_cierre_cuadra_por_medio_y_exige_motivo_si_no_cuadra(s):
    client, h, sandwich, gaseosa, _ = s
    abrir_caja(client, h, "50000")
    _cobrar(client, h, tomar_orden(client, h, [sandwich["id"]]), [{"medio": "efectivo", "monto": "10800"}])
    _cobrar(client, h, tomar_orden(client, h, [gaseosa["id"]]), [{"medio": "transferencia", "monto": "5400"}])
    gasto = client.post(f"{API}/gastos", headers=h, json={"fecha": "2026-01-02", "categoria": "aseo", "descripcion": "Jabón", "valor": "8000", "de_caja": True})
    assert gasto.status_code == 201, gasto.text
    esperado = client.get(f"{API}/caja/actual", headers=h).json()["caja"]["resumen"]["esperado"]
    assert Decimal(esperado["efectivo"]) == 50000 + 10800 - 8000 and Decimal(esperado["transferencia"]) == 5400

    sin_motivo = client.post(f"{API}/caja/cerrar", headers=h, json={"contado": {"efectivo": "52000", "transferencia": "5400"}})
    assert sin_motivo.status_code == 422 and "Efectivo: faltan $ 800" in sin_motivo.json()["detail"]

    r = client.post(f"{API}/caja/cerrar", headers=h, json={"contado": {"efectivo": "52000", "transferencia": "5400"}, "motivo_diferencia": "Devueltas mal dadas"})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["estado"] == "cerrada" and Decimal(c["diferencia"]) == -800 and c["motivo_diferencia"] == "Devueltas mal dadas"
    assert client.get(f"{API}/caja/actual", headers=h).json()["caja"] is None
    cierres = client.get(f"{API}/caja/cierres", headers=h).json()["items"]
    assert len(cierres) == 1 and Decimal(cierres[0]["resumen"]["esperado"]["efectivo"]) == 52800
    # El gasto de una caja cerrada ya no se toca.
    editar = client.put(f"{API}/gastos/{gasto.json()['id']}", headers=h, json={"fecha": "2026-01-02", "categoria": "aseo", "descripcion": "Jabón", "valor": "1"})
    assert editar.status_code == 409 and "ya se cerró" in editar.json()["detail"]


def test_medio_no_habilitado_y_documento_del_cliente(s):
    client, h, sandwich, _, _ = s
    ajustes = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    client.put(f"{API}/ajustes/restaurante", headers=h, json={**ajustes, "medios_pago": ["efectivo", "tarjeta"]})
    abrir_caja(client, h)
    orden = tomar_orden(client, h, [sandwich["id"]])
    r = _cobrar(client, h, orden, [{"medio": "nequi", "monto": "10800"}])
    assert r.status_code == 409 and "no recibe Nequi" in r.json()["detail"]
    nit_malo = _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "10800"}], cliente={"documento_tipo": "NIT", "documento": "900123456-1"})
    assert nit_malo.status_code == 422 and "dígito de verificación" in nit_malo.text
    ok = _cobrar(client, h, orden, [{"medio": "tarjeta", "monto": "10800"}], cliente={"nombre": "Empresa Uno", "documento_tipo": "NIT", "documento": "890903938-8", "correo": "Pagos@Uno.co"})
    assert ok.status_code == 201 and ok.json()["cliente_documento"] == "890903938-8" and ok.json()["cliente_correo"] == "pagos@uno.co"


def test_el_comprobante_dice_que_no_es_factura_electronica(s):
    client, h, sandwich, _, _ = s
    abrir_caja(client, h)
    v = _cobrar(client, h, tomar_orden(client, h, [sandwich["id"]]), [{"medio": "efectivo", "monto": "10800"}]).json()
    r = client.get(f"{API}/caja/ventas/{v['id']}/pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    from app.modules.caja.router import LEYENDA_COMPROBANTE

    assert LEYENDA_COMPROBANTE == "Comprobante interno, no válido como factura electrónica."


def test_una_orden_para_llevar_cobrada_sigue_en_cocina_hasta_entregarla(s):
    client, h, sandwich, _, _ = s
    abrir_caja(client, h)
    orden = tomar_orden(client, h, [sandwich["id"]])
    _cobrar(client, h, orden, [{"medio": "efectivo", "monto": "10800"}])
    cocina = client.get(f"{API}/cocina/comandas", headers=h).json()["comandas"]
    assert [c["orden_numero"] for c in cocina] == [orden["numero"]]
    assert [o["numero"] for o in client.get(f"{API}/ordenes", headers=h).json()["items"]] == [orden["numero"]]
    # Ya no se anula: tiene cobros.
    r = client.post(f"{API}/ordenes/{orden['id']}/anular", headers=h, json={"motivo": "Prueba"})
    assert r.status_code == 409


def test_gasto_de_caja_exige_caja_abierta_y_efectivo(s):
    client, h, _, _, _ = s
    base = {"fecha": "2026-01-02", "categoria": "gas", "descripcion": "Pipeta", "valor": "90000"}
    sin_caja = client.post(f"{API}/gastos", headers=h, json={**base, "de_caja": True})
    assert sin_caja.status_code == 409 and "No hay caja abierta" in sin_caja.json()["detail"]
    abrir_caja(client, h)
    tarjeta = client.post(f"{API}/gastos", headers=h, json={**base, "de_caja": True, "medio_pago": "tarjeta"})
    assert tarjeta.status_code == 409 and "Solo un gasto en efectivo" in tarjeta.json()["detail"]
    futuro = client.post(f"{API}/gastos", headers=h, json={**base, "fecha": "2999-01-01"})
    assert futuro.status_code == 422
    normal = client.post(f"{API}/gastos", headers=h, json={**base, "categoria": "arriendo", "valor": "2500000", "medio_pago": "transferencia"})
    assert normal.status_code == 201 and normal.json()["caja_id"] is None
    lista = client.get(f"{API}/gastos", headers=h, params={"categoria": "arriendo"}).json()
    assert lista["total"] == 1 and Decimal(lista["suma"]) == 2500000
    assert client.delete(f"{API}/gastos/{normal.json()['id']}", headers=h).status_code == 204


def test_el_cajero_cobra_y_cierra_pero_no_anula_ni_ve_gastos(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h_admin = auth_headers_factory(usuario_factory(tenant))
    pan = crear_insumo(client, h_admin, "Pan", "unidad", existencia="10")
    sandwich = crear_plato(client, h_admin, "Sándwich", "10800", receta=[(pan["id"], "1", "unidad")])
    cajero = rol_factory(tenant, nombre="Cajero", permisos={"ventas": ["ver", "crear"], "caja": ["ver", "cambiar_estado"], "ordenes": ["ver", "crear"]})
    h = auth_headers_factory(usuario_factory(tenant, rol=cajero))
    abrir_caja(client, h)
    v = _cobrar(client, h, tomar_orden(client, h, [sandwich["id"]]), [{"medio": "efectivo", "monto": "10800"}])
    assert v.status_code == 201
    anular = client.post(f"{API}/caja/ventas/{v.json()['id']}/anular", headers=h, json={"motivo": "Prueba"})
    assert anular.status_code == 403 and "anular cobros" in anular.json()["detail"]
    assert client.get(f"{API}/gastos", headers=h).status_code == 403
    assert v.json()["items"][0]["costo_unitario"] is None  # sin costos.ver
    assert client.post(f"{API}/caja/cerrar", headers=h, json={"contado": {"efectivo": "10800"}}).status_code == 200
