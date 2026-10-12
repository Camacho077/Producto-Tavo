"""
ÓRDENES CON COMANDA (fase 4, 2026-10-12): enviar una orden numera, descuenta
los insumos de las recetas y deja su comanda, todo o nada; agregar platos
saca una comanda con solo lo nuevo; anular devuelve exactamente lo que salió.
"""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.modules.ajustes.schemas import configuracion_de
from app.modules.ajustes.services import fecha_jornada
from app.modules.ordenes import schemas, services
from tests.conftest import API_V1 as API, crear_insumo, crear_plato, existencia


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    usuario = usuario_factory(tenant, nombre_completo="Marta Mesera")
    return client, auth_headers_factory(usuario), tenant, usuario


def _mesa(client, h, nombre="B2"):
    r = client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": nombre})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def carta(s):
    """Queso (kg) y pan (unidad); sándwich con 100 g de queso y extra queso
    de 30 g; gaseosa de venta directa."""
    client, h, _, _ = s
    queso = crear_insumo(client, h, "Queso", "kg", costo="20000", existencia="1")
    pan = crear_insumo(client, h, "Pan", "unidad", costo="500", existencia="20")
    tomate = crear_insumo(client, h, "Tomate", "kg", costo="4000", existencia="2")
    botella = crear_insumo(client, h, "Gaseosa botella", "unidad", costo="1800", existencia="24")
    sandwich = crear_plato(
        client, h, "Sándwich", "12000",
        receta=[(queso["id"], "100", "g"), (pan["id"], "1", "unidad"), (tomate["id"], "50", "g")],
        modificadores=[
            {"tipo": "extra", "nombre": "Extra queso", "precio": "2500", "insumo_id": queso["id"], "cantidad": "30", "unidad": "g"},
            {"tipo": "sin", "nombre": "Sin tomate", "insumo_id": tomate["id"]},
        ],
    )
    gaseosa = crear_plato(client, h, "Gaseosa", "3500", receta=[(botella["id"], "1", "unidad")], va_a_cocina=False)
    mods = {m["nombre"]: m["id"] for m in sandwich["modificadores"]}
    return {"queso": queso, "pan": pan, "tomate": tomate, "botella": botella, "sandwich": sandwich, "gaseosa": gaseosa, "mods": mods}


def _enviar(client, h, items, **datos):
    cuerpo = {"tipo": "llevar", **datos, "items": items}
    return client.post(f"{API}/ordenes", headers=h, json=cuerpo)


def test_enviar_numera_descuenta_y_deja_la_comanda(s, carta):
    client, h, _, _ = s
    mesa = _mesa(client, h)
    r = _enviar(client, h, [
        {"producto_id": carta["sandwich"]["id"], "cantidad": 2, "modificador_ids": [carta["mods"]["Extra queso"]], "nota": "Bien tostado"},
        {"producto_id": carta["gaseosa"]["id"]},
    ], tipo="local", mesa_id=mesa["id"])

    assert r.status_code == 201, r.text
    o = r.json()
    assert o["numero"] == 1 and o["mesa_nombre"] == "B2" and o["mesero_nombre"] == "Marta Mesera"
    assert Decimal(o["total"]) == Decimal("2") * (12000 + 2500) + 3500
    assert o["estado"] == "abierta" and o["estado_cocina"] == "entrante"
    assert len(o["comandas"]) == 1 and o["comandas"][0]["va_a_cocina"] is True
    sandwich = o["items"][0]
    assert sandwich["nota"] == "Bien tostado" and sandwich["modificadores"][0]["nombre"] == "Extra queso"
    assert o["items"][1]["va_a_cocina"] is False
    # 2 × (100 g + 30 g de extra) = 260 g de queso.
    assert existencia(client, h, carta["queso"]["id"]) == Decimal("0.74")
    assert existencia(client, h, carta["pan"]["id"]) == 18
    assert existencia(client, h, carta["botella"]["id"]) == 23
    movs = client.get(f"{API}/inventario/movimientos", headers=h, params={"tipo": "venta"}).json()["items"]
    assert {m["documento_codigo"] for m in movs} == {o["codigo"]}
    assert _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}]).json()["numero"] == 2


def test_el_sin_no_descuenta_el_insumo_quitado(s, carta):
    client, h, _, _ = s
    _enviar(client, h, [{"producto_id": carta["sandwich"]["id"], "modificador_ids": [carta["mods"]["Sin tomate"]]}])
    assert existencia(client, h, carta["tomate"]["id"]) == 2


def test_si_falta_un_insumo_no_se_guarda_nada_y_dice_cuanto_queda(s, carta):
    client, h, _, _ = s
    r = _enviar(client, h, [{"producto_id": carta["sandwich"]["id"], "cantidad": 11}])

    assert r.status_code == 409
    cuerpo = r.json()
    assert cuerpo["detail"] == "No se pudo enviar la orden: quedan 1 kg de Queso y la orden necesita 1,1 kg."
    assert cuerpo["datos"]["faltantes"][0]["insumo"] == "Queso"
    afectados = [p for p in cuerpo["datos"]["productos"] if carta["queso"]["id"] in p["insumo_ids"]]
    assert [p["nombre"] for p in afectados] == ["Sándwich"]
    assert existencia(client, h, carta["pan"]["id"]) == 20
    assert client.get(f"{API}/ordenes", headers=h, params={"vista": "todas"}).json()["total"] == 0
    # El consecutivo no se gastó.
    assert _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}]).json()["numero"] == 1


def test_marcar_agotado_desde_la_toma_de_pedidos(s, carta):
    client, h, _, _ = s
    r = client.post(f"{API}/ordenes/agotados", headers=h, json={"producto_id": carta["sandwich"]["id"]})
    assert r.status_code == 204
    pedido = _enviar(client, h, [{"producto_id": carta["sandwich"]["id"]}])
    assert pedido.status_code == 409 and "agotado hoy" in pedido.json()["detail"]
    en_carta = {p["nombre"]: p for p in client.get(f"{API}/ordenes/carta", headers=h).json()["productos"]}
    assert en_carta["Sándwich"]["agotado_hoy"] is True and en_carta["Gaseosa"]["agotado_hoy"] is False


def test_validaciones_del_encabezado(s, carta):
    client, h, _, _ = s
    item = [{"producto_id": carta["gaseosa"]["id"]}]
    sin_mesa = _enviar(client, h, item, tipo="local")
    assert sin_mesa.status_code == 422 and "elige para qué mesa" in sin_mesa.text
    domicilio = _enviar(client, h, item, tipo="domicilio", cliente_telefono="3001234567")
    assert domicilio.status_code == 422 and "la dirección" in domicilio.text
    telefono = _enviar(client, h, item, tipo="domicilio", cliente_direccion="Calle 1", cliente_telefono="123")
    assert telefono.status_code == 422
    assert _enviar(client, h, [], tipo="llevar").status_code == 422
    ajeno = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"], "modificador_ids": [carta["mods"]["Sin tomate"]]}])
    assert ajeno.status_code == 409 and "no es de Gaseosa" in ajeno.json()["detail"]


def test_tipo_deshabilitado_en_ajustes(s, carta):
    client, h, _, _ = s
    ajustes = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    client.put(f"{API}/ajustes/restaurante", headers=h, json={**ajustes, "tipos_orden": ["local", "llevar"]})
    r = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}], tipo="domicilio", cliente_direccion="Calle 1", cliente_telefono="3001234567")
    assert r.status_code == 409 and "a domicilio" in r.json()["detail"]


def test_agregar_platos_saca_una_comanda_solo_con_lo_nuevo(s, carta):
    client, h, _, _ = s
    o = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}]).json()
    assert o["comandas"][0]["estado"] == "lista"  # solo venta directa: no pasa por cocina

    r = client.post(f"{API}/ordenes/{o['id']}/items", headers=h, json={"items": [{"producto_id": carta["sandwich"]["id"]}]})

    assert r.status_code == 201, r.text
    o = r.json()
    assert [c["numero"] for c in o["comandas"]] == [1, 2] and o["comandas"][1]["estado"] == "entrante"
    assert [i["comanda_numero"] for i in o["items"]] == [1, 2]
    assert Decimal(o["total"]) == 3500 + 12000 and o["estado_cocina"] == "entrante"
    assert existencia(client, h, carta["queso"]["id"]) == Decimal("0.9")
    assert any(e["tipo"] == "agregado" and "Comanda 2" in e["nota"] for e in o["eventos"])


def test_anular_un_plato_devuelve_exactamente_lo_que_salio(s, carta):
    client, h, _, _ = s
    o = _enviar(client, h, [
        {"producto_id": carta["sandwich"]["id"], "modificador_ids": [carta["mods"]["Extra queso"]]},
        {"producto_id": carta["gaseosa"]["id"]},
    ]).json()
    # La receta cambia después: se devuelve lo que salió, no la receta nueva.
    client.put(f"{API}/catalogo/productos/{carta['sandwich']['id']}", headers=h, json={"receta": [
        {"insumo_id": carta["queso"]["id"], "cantidad": "500", "unidad": "g"},
    ]})
    item = o["items"][0]
    sin_motivo = client.post(f"{API}/ordenes/{o['id']}/items/{item['id']}/anular", headers=h, json={"motivo": ""})
    assert sin_motivo.status_code == 422

    r = client.post(f"{API}/ordenes/{o['id']}/items/{item['id']}/anular", headers=h, json={"motivo": "El cliente cambió de opinión"})

    assert r.status_code == 200, r.text
    o = r.json()
    assert o["items"][0]["anulado"] is True and Decimal(o["total"]) == 3500
    assert o["comandas"][0]["estado"] == "entrante"  # la gaseosa sigue
    assert existencia(client, h, carta["queso"]["id"]) == 1 and existencia(client, h, carta["pan"]["id"]) == 20
    devol = client.get(f"{API}/inventario/movimientos", headers=h, params={"tipo": "anulacion_orden"}).json()["items"]
    assert {m["motivo"] for m in devol} == {"El cliente cambió de opinión"}
    # Lo último que queda no se anula plato por plato.
    ultimo = client.post(f"{API}/ordenes/{o['id']}/items/{o['items'][1]['id']}/anular", headers=h, json={"motivo": "Se fue"})
    assert ultimo.status_code == 409 and "anula la orden completa" in ultimo.json()["detail"]


def test_anular_la_orden_devuelve_todo_y_retira_las_comandas(s, carta):
    client, h, _, _ = s
    o = _enviar(client, h, [{"producto_id": carta["sandwich"]["id"], "cantidad": 3}]).json()
    r = client.post(f"{API}/ordenes/{o['id']}/anular", headers=h, json={"motivo": "Pedido duplicado"})
    assert r.status_code == 200
    o = r.json()
    assert o["estado"] == "anulada" and o["anulada_motivo"] == "Pedido duplicado" and o["comandas"][0]["estado"] == "anulada"
    assert existencia(client, h, carta["queso"]["id"]) == 1
    again = client.post(f"{API}/ordenes/{o['id']}/anular", headers=h, json={"motivo": "Otra vez"})
    assert again.status_code == 409 and "ya está anulada" in again.json()["detail"]
    assert client.post(f"{API}/ordenes/{o['id']}/items", headers=h, json={"items": [{"producto_id": carta["gaseosa"]["id"]}]}).status_code == 409


def test_entregar_solo_lo_listo(s, carta, db_session):
    client, h, _, _ = s
    o = _enviar(client, h, [{"producto_id": carta["sandwich"]["id"]}]).json()
    r = client.post(f"{API}/ordenes/{o['id']}/entregar", headers=h)
    assert r.status_code == 409 and "comanda 1 por empezar" in r.json()["detail"]

    from app.modules.ordenes.models import Comanda

    db_session.get(Comanda, o["comandas"][0]["id"]).estado = "lista"
    db_session.commit()
    r = client.post(f"{API}/ordenes/{o['id']}/entregar", headers=h)
    assert r.status_code == 200
    assert r.json()["comandas"][0]["entregada_por"] == "Marta Mesera" and r.json()["estado_cocina"] == "entregada"


def test_tablero_activas_entregadas_y_anuladas(s, carta):
    client, h, _, _ = s
    activa = _enviar(client, h, [{"producto_id": carta["sandwich"]["id"]}]).json()
    directa = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}]).json()
    client.post(f"{API}/ordenes/{directa['id']}/entregar", headers=h)
    anulada = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}]).json()
    client.post(f"{API}/ordenes/{anulada['id']}/anular", headers=h, json={"motivo": "Error al tomarla"})

    def numeros(vista):
        return [o["numero"] for o in client.get(f"{API}/ordenes", headers=h, params={"vista": vista}).json()["items"]]

    assert numeros("activas") == [activa["numero"]]
    assert numeros("entregadas") == [directa["numero"]]
    assert numeros("anuladas") == [anulada["numero"]]
    assert client.get(f"{API}/ordenes", headers=h, params={"q": "#1", "vista": "todas"}).json()["total"] == 1
    jornada = client.get(f"{API}/ordenes/jornada", headers=h).json()
    assert jornada["en_curso"] == 1 and jornada["ordenes"] == 2
    csv = client.get(f"{API}/ordenes", headers=h, params={"vista": "todas", "formato": "csv"})
    assert csv.status_code == 200 and "Sándwich" in csv.text


def test_estado_de_las_mesas(s, carta):
    client, h, _, _ = s
    libre, ocupada, por_cobrar = _mesa(client, h, "B10"), _mesa(client, h, "B2"), _mesa(client, h, "A1")
    _enviar(client, h, [{"producto_id": carta["sandwich"]["id"]}], tipo="local", mesa_id=ocupada["id"])
    o = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}], tipo="local", mesa_id=por_cobrar["id"]).json()
    client.post(f"{API}/ordenes/{o['id']}/entregar", headers=h)

    mesas = client.get(f"{API}/ordenes/mesas", headers=h).json()
    assert [m["nombre"] for m in mesas] == ["A1", "B2", "B10"]  # orden natural
    estados = {m["nombre"]: m["estado"] for m in mesas}
    assert estados == {"B10": "libre", "B2": "ocupada", "A1": "por_cobrar"}
    assert libre["id"] in {m["id"] for m in mesas}


def test_el_consecutivo_vuelve_a_1_en_la_jornada_siguiente(s, carta, db_session):
    _, _, tenant, usuario = s
    config = configuracion_de(tenant)
    hoy = datetime(2026, 10, 12, 15, 0)  # 10:00 en Colombia
    pedido = schemas.OrdenCreate(tipo="llevar", items=[schemas.ItemPedido(producto_id=carta["gaseosa"]["id"])])
    a = services.crear_orden(db_session, usuario, pedido, ahora=hoy)
    b = services.crear_orden(db_session, usuario, pedido, ahora=hoy + timedelta(hours=1))
    # 02:00 del 13 en Colombia: con la jornada desde las 06:00, todavía es la del 12.
    c = services.crear_orden(db_session, usuario, pedido, ahora=datetime(2026, 10, 13, 7, 0))
    d = services.crear_orden(db_session, usuario, pedido, ahora=datetime(2026, 10, 13, 15, 0))
    assert [(o.jornada.day, o.numero) for o in (a, b, c, d)] == [(12, 1), (12, 2), (12, 3), (13, 1)]
    assert fecha_jornada(config, datetime(2026, 10, 13, 7, 0)).day == 12


def test_mesero_sin_permiso_de_anular_no_anula(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory, carta, s):
    _, h_admin, tenant, _ = s
    mesero = rol_factory(tenant, nombre="Mesero", permisos={"ordenes": ["ver", "crear", "editar"]})
    h = auth_headers_factory(usuario_factory(tenant, rol=mesero))
    o = _enviar(client, h, [{"producto_id": carta["gaseosa"]["id"]}])
    assert o.status_code == 201
    r = client.post(f"{API}/ordenes/{o.json()['id']}/anular", headers=h, json={"motivo": "Prueba"})
    assert r.status_code == 403 and "anular órdenes" in r.json()["detail"]
    # Sin costos.ver no ve el costo de cada plato.
    assert o.json()["items"][0]["costo_unitario"] is None
