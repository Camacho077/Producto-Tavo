"""
Panel de avisos del dashboard: se calcula con los datos reales del negocio.

Cada test monta una situación concreta (un producto en cero, una caída de
ventas, una comanda demorada) y comprueba que el aviso aparece con las cifras
correctas — y que NO aparece cuando la situación no se da.
"""
from datetime import datetime, timedelta

import pytest

from tests.nombres import letras

from app.core.tiempo import ahora_utc
from app.modules.dashboard import avisos as reglas
from tests.conftest import comprar, crear_insumo, crear_plato

URL = "/api/v1/dashboard/avisos"


@pytest.fixture()
def sesion(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    return client, auth_headers_factory(admin), tenant


def crear_producto(client, headers, nombre, sku, precio="1000", stock_minimo=0):
    """Plato cuya receta gasta una unidad del insumo `nombre` (el inventario
    es de insumos: los avisos de existencias nombran al insumo)."""
    insumo = crear_insumo(client, headers, nombre, minimo=str(stock_minimo))
    plato = crear_plato(client, headers, f"Plato de {nombre}", precio, receta=[(insumo["id"], "1", "unidad")], sku=sku)
    return {**plato, "insumo_id": insumo["id"]}


def dar_stock(client, headers, producto_id, cantidad, fecha="2026-01-01T09:00:00"):
    plato = client.get(f"/api/v1/catalogo/productos/{producto_id}", headers=headers).json()
    comprar(client, headers, [(plato["receta"][0]["insumo_id"], cantidad, "unidad", "500")], fecha=fecha)


def vender(client, headers, producto_id, cantidad, fecha, precio="1000"):
    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Carlos Cliente",
            "fecha": fecha,
            "confirmar": True,
            "items": [{"producto_id": producto_id, "cantidad": cantidad, "precio_unitario": precio}],
        },
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


def claves(cuerpo):
    return [a["clave"] for a in cuerpo["avisos"]]


def aviso(cuerpo, clave):
    return next(a for a in cuerpo["avisos"] if a["clave"] == clave)


# =====================================================================
# Sin nada que reportar
# =====================================================================
def test_sin_datos_el_panel_dice_que_todo_esta_en_orden(sesion):
    client, headers, _ = sesion
    cuerpo = client.get(URL, headers=headers).json()
    assert cuerpo["avisos"] == []
    assert cuerpo["todo_en_orden"] is True


def test_un_producto_con_stock_sano_no_genera_avisos(sesion):
    client, headers, _ = sesion
    producto = crear_producto(client, headers, "Teclado", "TEC-1", stock_minimo=2)
    dar_stock(client, headers, producto["id"], 50)
    cuerpo = client.get(URL, headers=headers).json()
    assert claves(cuerpo) == []
    assert cuerpo["todo_en_orden"] is True


# =====================================================================
# Stock
# =====================================================================
def test_insumo_en_cero_es_un_aviso_critico_que_enlaza_a_su_ficha(sesion):
    client, headers, _ = sesion
    producto = crear_producto(client, headers, "Teclado", "TEC-1")
    cuerpo = client.get(URL, headers=headers).json()

    a = aviso(cuerpo, "stock_agotado")
    assert a["nivel"] == "critico"
    assert a["titulo"] == "1 insumo agotado"
    assert "Teclado sin existencias" in a["texto"]
    assert a["enlace"] == {"recurso": "insumo", "id": producto["insumo_id"]}
    assert cuerpo["todo_en_orden"] is False


def test_varios_agotados_se_resumen_y_enlazan_al_listado(sesion):
    client, headers, _ = sesion
    for i in range(5):
        crear_producto(client, headers, f"Producto {letras(i)}", f"P-{i}")
    a = aviso(client.get(URL, headers=headers).json(), "stock_agotado")
    assert a["titulo"] == "5 insumos agotados"
    assert "y 2 más" in a["texto"]
    assert a["enlace"] == {"recurso": "insumos", "id": None}


def test_stock_bajo_el_minimo_avisa_con_la_cifra_y_el_minimo(sesion):
    client, headers, _ = sesion
    producto = crear_producto(client, headers, "Mouse", "MOU-1", stock_minimo=10)
    dar_stock(client, headers, producto["id"], 3)
    a = aviso(client.get(URL, headers=headers).json(), "stock_bajo")
    assert a["nivel"] == "advertencia"
    assert a["titulo"] == "1 insumo bajo el mínimo"
    assert "Mouse (3 unidades, mínimo 10 unidades)" in a["texto"]
    assert a["enlace"] == {"recurso": "insumo", "id": producto["insumo_id"]}


def test_un_insumo_que_no_esta_en_ninguna_receta_no_avisa_agotado(sesion):
    client, headers, _ = sesion
    crear_insumo(client, headers, "Servilletas")
    assert "stock_agotado" not in claves(client.get(URL, headers=headers).json())


def test_sin_minimo_configurado_no_se_inventa_una_alerta_de_stock_bajo(sesion):
    client, headers, _ = sesion
    producto = crear_producto(client, headers, "Cable", "CAB-1", stock_minimo=0)
    dar_stock(client, headers, producto["id"], 1)
    assert "stock_bajo" not in claves(client.get(URL, headers=headers).json())


# =====================================================================
# Ventas
# =====================================================================
def test_caida_notable_de_ventas_frente_a_la_semana_anterior(sesion, db_session):
    client, headers, tenant = sesion
    ahora = ahora_utc()
    producto = crear_producto(client, headers, "Diadema", "DIA-1")
    dar_stock(client, headers, producto["id"], 1000)
    # Semana anterior: 10 unidades. Semana actual: 2.
    vender(client, headers, producto["id"], 10, (ahora - timedelta(days=10)).isoformat())
    vender(client, headers, producto["id"], 2, (ahora - timedelta(days=2)).isoformat())

    cuerpo = reglas.calcular(db_session, tenant.id, ahora)
    a = next(x for x in cuerpo["avisos"] if x["clave"] == "ventas_caida")
    assert a["nivel"] == "advertencia"
    assert a["titulo"] == "Las ventas cayeron 80% esta semana"
    assert a["enlace"] == {"recurso": "ventas", "id": None}
    assert cuerpo["todo_en_orden"] is False


def test_subida_notable_de_ventas_es_un_aviso_positivo(sesion, db_session):
    client, headers, tenant = sesion
    ahora = ahora_utc()
    producto = crear_producto(client, headers, "Diadema", "DIA-1")
    dar_stock(client, headers, producto["id"], 1000)
    vender(client, headers, producto["id"], 2, (ahora - timedelta(days=10)).isoformat())
    vender(client, headers, producto["id"], 10, (ahora - timedelta(days=2)).isoformat())

    cuerpo = reglas.calcular(db_session, tenant.id, ahora)
    a = next(x for x in cuerpo["avisos"] if x["clave"] == "ventas_subida")
    assert a["nivel"] == "positivo"
    assert "subieron 400%" in a["titulo"]
    # Un aviso positivo no rompe el "todo en orden".
    assert cuerpo["todo_en_orden"] is True


def test_una_variacion_pequena_no_se_reporta(sesion, db_session):
    client, headers, tenant = sesion
    ahora = ahora_utc()
    producto = crear_producto(client, headers, "Diadema", "DIA-1")
    dar_stock(client, headers, producto["id"], 1000)
    vender(client, headers, producto["id"], 10, (ahora - timedelta(days=10)).isoformat())
    vender(client, headers, producto["id"], 11, (ahora - timedelta(days=2)).isoformat())

    cuerpo = reglas.calcular(db_session, tenant.id, ahora)
    assert not [a for a in cuerpo["avisos"] if a["clave"].startswith("ventas_")]


def test_sin_semana_anterior_no_se_calcula_un_porcentaje_sin_sentido(sesion, db_session):
    client, headers, tenant = sesion
    ahora = ahora_utc()
    producto = crear_producto(client, headers, "Diadema", "DIA-1")
    dar_stock(client, headers, producto["id"], 1000)
    vender(client, headers, producto["id"], 5, (ahora - timedelta(days=1)).isoformat())

    cuerpo = reglas.calcular(db_session, tenant.id, ahora)
    assert not [a for a in cuerpo["avisos"] if a["clave"].startswith("ventas_")]


def test_el_mas_vendido_de_la_semana_enlaza_al_producto(sesion, db_session):
    client, headers, tenant = sesion
    ahora = ahora_utc()
    top = crear_producto(client, headers, "Diadema", "DIA-1")
    otro = crear_producto(client, headers, "Cargador", "CAR-1")
    dar_stock(client, headers, top["id"], 1000)
    dar_stock(client, headers, otro["id"], 1000)
    vender(client, headers, top["id"], 9, (ahora - timedelta(days=1)).isoformat())
    vender(client, headers, otro["id"], 4, (ahora - timedelta(days=1)).isoformat())

    a = next(x for x in reglas.calcular(db_session, tenant.id, ahora)["avisos"] if x["clave"] == "mas_vendido")
    assert a["titulo"] == "Lo más vendido de la semana: Plato de Diadema"
    assert "9 unidades" in a["texto"]
    assert a["enlace"] == {"recurso": "producto", "id": top["id"]}


# =====================================================================
# Comandas demoradas en cocina
# =====================================================================
def _orden(client, headers, producto_id):
    resp = client.post("/api/v1/ordenes", headers=headers, json={"tipo": "llevar", "items": [{"producto_id": producto_id}]})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def test_comanda_que_pasa_el_tiempo_de_alerta_genera_aviso(sesion, db_session):
    client, headers, tenant = sesion
    producto = crear_producto(client, headers, "Arepa", "ARE-1")
    dar_stock(client, headers, producto["id"], 5)
    orden = _orden(client, headers, producto["id"])

    # Alerta por defecto: 15 minutos.
    a = next(x for x in reglas.calcular(db_session, tenant.id, ahora_utc() + timedelta(minutes=20))["avisos"] if x["clave"] == "comandas_demoradas")
    assert a["nivel"] == "advertencia" and a["titulo"] == "1 comanda demorada en cocina"
    assert f"#{orden['numero']}" in a["texto"] and "la alerta es a los 15 min" in a["texto"]
    assert a["enlace"] == {"recurso": "ordenes", "id": None}


def test_una_comanda_reciente_o_lista_no_esta_demorada(sesion, db_session):
    client, headers, tenant = sesion
    producto = crear_producto(client, headers, "Arepa", "ARE-1")
    dar_stock(client, headers, producto["id"], 5)
    _orden(client, headers, producto["id"])
    assert "comandas_demoradas" not in [a["clave"] for a in reglas.calcular(db_session, tenant.id, ahora_utc())["avisos"]]

    from app.modules.ordenes.models import Comanda

    for c in db_session.query(Comanda).filter(Comanda.tenant_id == tenant.id):
        c.estado = "lista"
    db_session.commit()
    futuro = ahora_utc() + timedelta(hours=2)
    assert "comandas_demoradas" not in [a["clave"] for a in reglas.calcular(db_session, tenant.id, futuro)["avisos"]]


# =====================================================================
# Multi-tenant
# =====================================================================
def test_los_avisos_no_se_mezclan_entre_empresas(client, tenant_factory, usuario_factory, auth_headers_factory):
    empresa_a = tenant_factory()
    empresa_b = tenant_factory()
    headers_a = auth_headers_factory(usuario_factory(empresa_a))
    headers_b = auth_headers_factory(usuario_factory(empresa_b))

    crear_producto(client, headers_a, "Teclado", "TEC-1")
    assert claves(client.get(URL, headers=headers_a).json()) == ["stock_agotado"]
    assert client.get(URL, headers=headers_b).json() == {"avisos": [], "todo_en_orden": True}


def test_el_endpoint_exige_autenticacion(client):
    assert client.get(URL).status_code == 401
