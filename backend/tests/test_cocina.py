"""
PANTALLA DE COCINA (fase 5, 2026-10-12): solo lo que va a cocina, Tomar y
Finalizar con quién y cuándo, y avisos de lo que se anuló.
"""
import pytest

from tests.conftest import API_V1 as API, crear_insumo, crear_plato


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    h_admin = auth_headers_factory(usuario_factory(tenant, nombre_completo="Marta Mesera"))
    cocinero = rol_factory(tenant, nombre="Cocinero", permisos={"cocina": ["ver", "cambiar_estado"]})
    h_cocina = auth_headers_factory(usuario_factory(tenant, rol=cocinero, nombre_completo="Carlos Cocina"))
    pan = crear_insumo(client, h_admin, "Pan", "unidad", existencia="50")
    botella = crear_insumo(client, h_admin, "Botella", "unidad", existencia="50")
    sandwich = crear_plato(client, h_admin, "Sándwich", "12000", receta=[(pan["id"], "1", "unidad")],
                           modificadores=[{"tipo": "sin", "nombre": "Sin cebolla"}])
    gaseosa = crear_plato(client, h_admin, "Gaseosa", "3500", receta=[(botella["id"], "1", "unidad")], va_a_cocina=False)
    return client, h_admin, h_cocina, sandwich, gaseosa


def _orden(client, h, items, **datos):
    r = client.post(f"{API}/ordenes", headers=h, json={"tipo": "llevar", "cliente_nombre": "Ana María", **datos, "items": items})
    assert r.status_code == 201, r.text
    return r.json()


def _cocina(client, h):
    r = client.get(f"{API}/cocina/comandas", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_solo_llega_lo_que_va_a_cocina(s):
    client, h, hc, sandwich, gaseosa = s
    mod = sandwich["modificadores"][0]["id"]
    o = _orden(client, h, [{"producto_id": sandwich["id"], "cantidad": 2, "modificador_ids": [mod]}, {"producto_id": gaseosa["id"]}], nota="Sin afán")
    _orden(client, h, [{"producto_id": gaseosa["id"]}])  # solo venta directa: no llega

    datos = _cocina(client, hc)
    assert datos["alerta_minutos"] == 15 and datos["sonido"] is True
    assert len(datos["comandas"]) == 1
    c = datos["comandas"][0]
    assert c["orden_numero"] == o["numero"] and c["destino"] == "Ana María" and c["estado"] == "entrante"
    assert [i["nombre"] for i in c["items"]] == ["Sándwich"] and c["items"][0]["modificadores"][0]["nombre"] == "Sin cebolla"
    assert c["nota"] == "Sin afán" and c["mesero_nombre"] == "Marta Mesera"


def test_tomar_y_finalizar_registran_quien_y_cuando(s):
    client, h, hc, sandwich, _ = s
    o = _orden(client, h, [{"producto_id": sandwich["id"]}])
    cid = o["comandas"][0]["id"]

    finalizar_antes = client.post(f"{API}/cocina/comandas/{cid}/finalizar", headers=hc)
    assert finalizar_antes.status_code == 409 and "por empezar" in finalizar_antes.json()["detail"]

    r = client.post(f"{API}/cocina/comandas/{cid}/tomar", headers=hc)
    assert r.status_code == 200 and r.json()["estado"] == "en_preparacion" and r.json()["tomada_por"] == "Carlos Cocina"
    otra_vez = client.post(f"{API}/cocina/comandas/{cid}/tomar", headers=hc)
    assert otra_vez.status_code == 409 and "quizá otra persona la movió" in otra_vez.json()["detail"]

    r = client.post(f"{API}/cocina/comandas/{cid}/finalizar", headers=hc)
    assert r.status_code == 200 and r.json()["estado"] == "lista" and r.json()["lista_por"] == "Carlos Cocina"

    detalle = client.get(f"{API}/ordenes/{o['id']}", headers=h).json()
    assert detalle["estado_cocina"] == "lista"
    assert [e["tipo"] for e in detalle["eventos"]] == ["creada", "tomada", "lista"]
    # Sigue en "Listos" hasta que el mesero la entrega.
    assert _cocina(client, hc)["comandas"][0]["estado"] == "lista"
    client.post(f"{API}/ordenes/{o['id']}/entregar", headers=h)
    assert _cocina(client, hc)["comandas"] == []


def test_lo_anulado_sale_de_cocina_con_aviso(s):
    client, h, hc, sandwich, gaseosa = s
    o = _orden(client, h, [{"producto_id": sandwich["id"]}, {"producto_id": sandwich["id"]}])
    client.post(f"{API}/ordenes/{o['id']}/items/{o['items'][0]['id']}/anular", headers=h, json={"motivo": "El cliente cambió"})

    datos = _cocina(client, hc)
    items = datos["comandas"][0]["items"]
    assert [i["anulado"] for i in items] == [True, False] and items[0]["anulado_motivo"] == "El cliente cambió"
    assert datos["avisos"][0]["texto"] == f"Orden #{o['numero']}: se quitó 1× Sándwich: El cliente cambió"

    client.post(f"{API}/ordenes/{o['id']}/anular", headers=h, json={"motivo": "Se fue sin pagar"})
    datos = _cocina(client, hc)
    assert datos["comandas"] == []
    assert datos["avisos"][0]["texto"] == f"Orden #{o['numero']} anulada: Se fue sin pagar"
    r = client.post(f"{API}/cocina/comandas/{o['comandas'][0]['id']}/tomar", headers=hc)
    assert r.status_code == 409 and "ya no va" in r.json()["detail"]


def test_el_cocinero_no_toma_pedidos_ni_ve_ordenes(s):
    client, _, hc, sandwich, _ = s
    assert client.post(f"{API}/ordenes", headers=hc, json={"tipo": "llevar", "items": [{"producto_id": sandwich["id"]}]}).status_code == 403
    assert client.get(f"{API}/ordenes", headers=hc).status_code == 403
    assert client.get(f"{API}/inventario/insumos", headers=hc).status_code == 403


def test_otra_empresa_no_ve_ni_mueve_las_comandas(s, client, tenant_factory, usuario_factory, auth_headers_factory):
    _, h, hc, sandwich, _ = s
    o = _orden(client, h, [{"producto_id": sandwich["id"]}])
    ajena = auth_headers_factory(usuario_factory(tenant_factory()))
    assert _cocina(client, ajena)["comandas"] == []
    assert client.post(f"{API}/cocina/comandas/{o['comandas'][0]['id']}/tomar", headers=ajena).status_code == 404
    assert _cocina(client, hc)["comandas"][0]["estado"] == "entrante"
