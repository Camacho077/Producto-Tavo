"""
CARTA (fase 2, 2026-10-12): platos con receta, costo y margen; modificadores;
combos con vigencia; "agotado hoy"; foto del plato; permisos de costos.
"""
import io
from decimal import Decimal

import pytest
from PIL import Image

from tests.conftest import API_V1 as API, comprar, crear_insumo, crear_plato

D = Decimal


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h = auth_headers_factory(usuario_factory(tenant))
    insumos = {
        "pan": crear_insumo(client, h, "Pan", "unidad", costo="600"),
        "carne": crear_insumo(client, h, "Carne", "kg", costo="24000"),
        "queso": crear_insumo(client, h, "Queso", "kg", costo="30000"),
        "tomate": crear_insumo(client, h, "Tomate", "kg", costo="4000"),
    }
    return client, h, insumos, tenant


def _hamburguesa(client, h, i, **extra):
    return crear_plato(
        client, h, "Hamburguesa clásica", "16200",
        receta=[(i["pan"]["id"], "1", "unidad"), (i["carne"]["id"], "150", "g"), (i["queso"]["id"], "30", "g"), (i["tomate"]["id"], "40", "g", "25")],
        **extra,
    )


def test_el_costo_sale_de_la_receta_y_el_margen_es_sin_impuesto(s):
    client, h, i, _ = s
    plato = _hamburguesa(client, h, i)
    # 600 + 0,15 × 24.000 + 0,03 × 30.000 + 0,05 × 4.000 (40 g con 25 % de merma)
    assert D(plato["costo"]) == D("5300")
    assert D(plato["precio_neto"]) == D("15000")  # 16.200 / 1,08 (impuesto incluido)
    assert D(plato["margen"]) == D("9700")
    assert D(plato["porcentaje_costo"]) == D("35.33")
    assert plato["tiene_receta"] is True
    assert [D(l["costo"]) for l in plato["receta"]] == [D("600"), D("3600"), D("900"), D("200")]


def test_cuando_sube_un_insumo_el_plato_se_recosta_solo(s):
    client, h, i, _ = s
    plato = _hamburguesa(client, h, i)
    comprar(client, h, [(i["carne"]["id"], "10", "kg", "32000")])  # sin existencia previa: el costo pasa a 32.000
    actualizado = client.get(f"{API}/catalogo/productos/{plato['id']}", headers=h).json()
    assert D(actualizado["costo"]) == D("5300") + D("0.15") * (32000 - 24000)
    usan = client.get(f"{API}/catalogo/productos", headers=h, params={"insumo_id": i["carne"]["id"]}).json()["items"]
    assert [p["nombre"] for p in usan] == ["Hamburguesa clásica"]


def test_sin_impuesto_incluido_el_precio_neto_es_el_de_la_carta(s):
    client, h, i, _ = s
    config = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    config["impuesto_consumo"]["incluido_en_precio"] = False
    client.put(f"{API}/ajustes/restaurante", headers=h, json=config)
    plato = _hamburguesa(client, h, i)
    assert D(plato["precio_neto"]) == D("16200") and D(plato["margen"]) == D("10900")


def test_un_plato_sin_receta_no_inventa_un_costo(s):
    client, h, _, _ = s
    plato = crear_plato(client, h, "Plato nuevo", "10000")
    assert plato["costo"] is None and plato["margen"] is None and plato["tiene_receta"] is False


def test_la_receta_valida_unidades_y_no_repite_insumos(s):
    client, h, i, _ = s
    r = client.post(f"{API}/catalogo/productos", headers=h, json={
        "nombre": "Raro", "precio": "1000", "receta": [{"insumo_id": i["pan"]["id"], "cantidad": "100", "unidad": "g"}],
    })
    assert r.status_code == 409 and "Pan se lleva en unidad y no se puede escribir en g" in r.json()["detail"]
    r = client.post(f"{API}/catalogo/productos", headers=h, json={
        "nombre": "Raro", "precio": "1000",
        "receta": [{"insumo_id": i["pan"]["id"], "cantidad": "1", "unidad": "unidad"}, {"insumo_id": i["pan"]["id"], "cantidad": "1", "unidad": "unidad"}],
    })
    assert r.status_code == 409 and "repite el insumo Pan" in r.json()["detail"]
    r = client.post(f"{API}/catalogo/productos", headers=h, json={
        "nombre": "Raro", "precio": "1000", "receta": [{"insumo_id": i["pan"]["id"], "cantidad": "1", "unidad": "unidad", "merma_porcentaje": "95"}],
    })
    assert r.status_code == 422


def test_modificadores_sin_y_extra_con_su_insumo(s):
    client, h, i, _ = s
    plato = _hamburguesa(client, h, i, modificadores=[
        {"tipo": "sin", "nombre": "Tomate", "insumo_id": i["tomate"]["id"]},
        {"tipo": "extra", "nombre": "Queso", "precio": "2500", "insumo_id": i["queso"]["id"], "cantidad": "30", "unidad": "g"},
    ])
    mods = {m["nombre"]: m for m in plato["modificadores"]}
    assert D(mods["Queso"]["costo"]) == D("900") and mods["Tomate"]["costo"] is None

    # Un «sin» con precio, o que quita algo que no está en la receta, no pasa.
    r = client.put(f"{API}/catalogo/productos/{plato['id']}", headers=h, json={"modificadores": [{"tipo": "sin", "nombre": "Cebolla", "precio": "500"}]})
    assert r.status_code == 422
    otro = crear_insumo(client, h, "Cebolla", "kg")
    r = client.put(f"{API}/catalogo/productos/{plato['id']}", headers=h, json={"modificadores": [{"tipo": "sin", "nombre": "Cebolla", "insumo_id": otro["id"]}]})
    assert r.status_code == 409 and "no está en la receta" in r.json()["detail"]

    # Editar conserva el id del modificador.
    mods_in = [{**{k: m[k] for k in ("id", "tipo", "nombre", "precio", "insumo_id", "cantidad", "unidad")}} for m in plato["modificadores"]]
    next(m for m in mods_in if m["tipo"] == "extra")["precio"] = "3000"
    r = client.put(f"{API}/catalogo/productos/{plato['id']}", headers=h, json={"modificadores": mods_in})
    assert r.status_code == 200, r.json()
    assert {m["id"] for m in r.json()["modificadores"]} == {m["id"] for m in plato["modificadores"]}


def test_combo_con_vigencia_y_su_costo(s):
    client, h, i, _ = s
    hamburguesa = _hamburguesa(client, h, i)
    gaseosa_insumo = crear_insumo(client, h, "Gaseosa", "unidad", costo="1900")
    gaseosa = crear_plato(client, h, "Gaseosa", "3500", receta=[(gaseosa_insumo["id"], "1", "unidad")], va_a_cocina=False)
    r = client.post(f"{API}/catalogo/productos", headers=h, json={
        "tipo": "combo", "nombre": "Combo estudiante", "precio": "18000",
        "componentes": [{"producto_id": hamburguesa["id"], "cantidad": 1}, {"producto_id": gaseosa["id"], "cantidad": 1}],
        "vigente_desde": "2020-01-01", "vigente_hasta": "2099-12-31",
    })
    assert r.status_code == 201, r.json()
    combo = r.json()
    assert D(combo["costo"]) == D("5300") + D("1900")
    assert combo["va_a_cocina"] is True and combo["vigente"] is True

    r = client.post(f"{API}/catalogo/productos", headers=h, json={"tipo": "combo", "nombre": "Combo vacío", "precio": "1000"})
    assert r.status_code == 422
    r = client.post(f"{API}/catalogo/productos", headers=h, json={
        "tipo": "combo", "nombre": "Combo de combos", "precio": "1000", "componentes": [{"producto_id": combo["id"]}],
    })
    assert r.status_code == 409 and "es un combo" in r.json()["detail"]
    r = client.post(f"{API}/catalogo/productos", headers=h, json={
        "tipo": "combo", "nombre": "Promo vieja", "precio": "1000", "componentes": [{"producto_id": gaseosa["id"]}],
        "vigente_desde": "2020-01-01", "vigente_hasta": "2020-02-01",
    })
    assert r.json()["vigente"] is False and r.json()["disponible"] is False

    # Un plato que está en un combo no se elimina.
    r = client.delete(f"{API}/catalogo/productos/{gaseosa['id']}", headers=h)
    assert r.status_code == 409 and "Combo estudiante" in r.json()["detail"]


def test_vender_un_combo_descuenta_los_insumos_de_sus_platos(s):
    client, h, i, _ = s
    hamburguesa = _hamburguesa(client, h, i)
    comprar(client, h, [(i["pan"]["id"], "10", "unidad", "600"), (i["carne"]["id"], "2", "kg", "24000"),
                        (i["queso"]["id"], "1", "kg", "30000"), (i["tomate"]["id"], "1", "kg", "4000")])
    combo = client.post(f"{API}/catalogo/productos", headers=h, json={
        "tipo": "combo", "nombre": "Combo doble", "precio": "30000", "componentes": [{"producto_id": hamburguesa["id"], "cantidad": 2}],
    }).json()
    r = client.post(f"{API}/ventas/ventas", headers=h, json={
        "cliente_nombre": "Cliente Final", "fecha": "2026-01-02T10:00:00", "confirmar": True,
        "items": [{"producto_id": combo["id"], "cantidad": 1, "precio_unitario": "30000"}],
    })
    assert r.status_code == 201, r.json()
    pan = client.get(f"{API}/inventario/insumos/{i['pan']['id']}", headers=h).json()
    assert D(pan["existencia"]) == 8


def test_agotado_hoy_sin_desactivar(s):
    client, h, i, _ = s
    plato = _hamburguesa(client, h, i)
    r = client.patch(f"{API}/catalogo/productos/{plato['id']}/agotado", headers=h, json={"agotado": True})
    assert r.status_code == 200 and r.json()["agotado_hoy"] is True and r.json()["activo"] is True
    assert r.json()["disponible"] is False
    disponibles = client.get(f"{API}/catalogo/productos", headers=h, params={"disponible": True}).json()["items"]
    assert plato["id"] not in [p["id"] for p in disponibles]
    r = client.patch(f"{API}/catalogo/productos/{plato['id']}/agotado", headers=h, json={"agotado": False})
    assert r.json()["disponible"] is True


def test_agotado_de_ayer_ya_no_cuenta(s, db_session):
    client, h, i, _ = s
    from datetime import timedelta

    from app.modules.catalogo.models import Producto

    plato = _hamburguesa(client, h, i)
    client.patch(f"{API}/catalogo/productos/{plato['id']}/agotado", headers=h, json={"agotado": True})
    obj = db_session.get(Producto, __import__("uuid").UUID(plato["id"]))
    obj.agotado_fecha = obj.agotado_fecha - timedelta(days=1)
    db_session.commit()
    assert client.get(f"{API}/catalogo/productos/{plato['id']}", headers=h).json()["agotado_hoy"] is False


def test_la_foto_del_plato_se_guarda_cuadrada(s):
    client, h, i, _ = s
    plato = _hamburguesa(client, h, i)
    buffer = io.BytesIO()
    Image.new("RGB", (1600, 900), "white").save(buffer, "JPEG")
    r = client.put(f"{API}/catalogo/productos/{plato['id']}/imagen", headers={**h, "Content-Type": "image/jpeg"}, content=buffer.getvalue())
    assert r.status_code == 200 and r.json()["imagen_id"]
    foto = client.get(f"{API}/imagenes/{r.json()['imagen_id']}")
    with Image.open(io.BytesIO(foto.content)) as abierta:
        assert abierta.size == (640, 640)
    r = client.delete(f"{API}/catalogo/productos/{plato['id']}/imagen", headers=h)
    assert r.json()["imagen_id"] is None


def test_nombres_de_la_carta_admiten_numeros(s):
    client, h, _, _ = s
    assert crear_plato(client, h, "Pollo 1/4 (asado)", "12000")["nombre"] == "Pollo 1/4 (asado)"
    r = client.post(f"{API}/catalogo/productos", headers=h, json={"nombre": "Pollo #1", "precio": "1000"})
    assert r.status_code == 422


def test_un_rol_sin_costos_ve_la_carta_sin_costo_ni_margen(s, rol_factory, usuario_factory, auth_headers_factory):
    client, h, i, tenant = s
    _hamburguesa(client, h, i)
    mesero = auth_headers_factory(usuario_factory(tenant, rol=rol_factory(tenant, nombre="Mesero", permisos={"productos": ["ver"]})))
    plato = client.get(f"{API}/catalogo/productos", headers=mesero).json()["items"][0]
    assert plato["costo"] is None and plato["margen"] is None and plato["receta"][0]["costo"] is None
    assert plato["precio"] == "16200.00"
    csv = client.get(f"{API}/catalogo/productos?formato=csv", headers=mesero).text
    assert "Margen" not in csv.splitlines()[0]
