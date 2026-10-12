"""
COMPORTAMIENTO de los endpoints que solo cubría test_permisos.py (que
comprueba el 403/acceso de las 65 rutas, pero no lo que hacen). Revisión del
2026-10-02: detalle por id, cambio de estado, borrado con historial, edición
de marca y PDF de compras y pedidos.
"""
import uuid

import pytest

from tests.conftest import PROVEEDOR_PRUEBA

API = "/api/v1"
AJENO = str(uuid.uuid4())


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    return client, auth_headers_factory(usuario_factory(tenant, nombre_completo="Ana Admin"))


def crear(client, h, ruta, cuerpo):
    r = client.post(f"{API}{ruta}", headers=h, json=cuerpo)
    assert r.status_code == 201, r.json()
    return r.json()


def producto(client, h, nombre="Cafe", sku="CAF-1"):
    return crear(client, h, "/compras/productos", {"nombre": nombre, "sku": sku, "precio": "1000"})


def compra(client, h, pid, confirmar=True):
    prov = crear(client, h, "/compras/proveedores", PROVEEDOR_PRUEBA)
    return prov, crear(client, h, "/compras/compras", {
        "proveedor_id": prov["id"], "fecha": "2026-03-10T09:00:00", "confirmar": confirmar,
        "items": [{"producto_id": pid, "cantidad": 4, "precio_unitario": "500"}],
    })


# ---------------------------------------------------------------- detalle por id
@pytest.mark.parametrize("ruta,cuerpo,campo", [
    ("/compras/categorias", {"nombre": "Bebidas"}, "nombre"),
    ("/compras/marcas", {"nombre": "Campo Verde"}, "nombre"),
    ("/compras/proveedores", PROVEEDOR_PRUEBA, "razon_social"),
])
def test_el_detalle_devuelve_el_registro_y_404_si_no_existe(s, ruta, cuerpo, campo):
    client, h = s
    creado = crear(client, h, ruta, cuerpo)
    r = client.get(f"{API}{ruta}/{creado['id']}", headers=h)
    assert r.status_code == 200 and r.json()[campo] == cuerpo[campo]
    r = client.get(f"{API}{ruta}/{AJENO}", headers=h)
    assert r.status_code == 404 and r.json()["detail"]


def test_detalle_de_compra_usuario_y_rol(s):
    client, h = s
    pid = producto(client, h)["id"]
    _, c = compra(client, h, pid)
    r = client.get(f"{API}/compras/compras/{c['id']}", headers=h).json()
    assert r["codigo"].startswith("COM-") and r["items"][0]["producto_id"] == pid and r["total"] == "2000.00"
    usuarios = client.get(f"{API}/seguridad/usuarios", headers=h).json()["items"]
    assert client.get(f"{API}/seguridad/usuarios/{usuarios[0]['id']}", headers=h).json()["nombre_completo"] == "Ana Admin"
    roles = client.get(f"{API}/seguridad/roles", headers=h).json()["items"]
    rol = client.get(f"{API}/seguridad/roles/{roles[0]['id']}", headers=h).json()
    assert rol["nombre"] == roles[0]["nombre"]
    for ruta in ("/compras/compras", "/seguridad/usuarios", "/seguridad/roles"):
        assert client.get(f"{API}{ruta}/{AJENO}", headers=h).status_code == 404


# ---------------------------------------------------------------- cambio de estado
@pytest.mark.parametrize("ruta,cuerpo", [
    ("/compras/categorias", {"nombre": "Bebidas"}),
    ("/compras/proveedores", PROVEEDOR_PRUEBA),
    ("/compras/productos", {"nombre": "Cafe", "sku": "CAF-1", "precio": "1000"}),
])
def test_cambiar_estado_desactiva_y_reactiva_y_el_filtro_lo_refleja(s, ruta, cuerpo):
    client, h = s
    creado = crear(client, h, ruta, cuerpo)
    r = client.patch(f"{API}{ruta}/{creado['id']}/estado", headers=h, json={"activo": False})
    assert r.status_code == 200 and r.json()["activo"] is False
    assert client.get(f"{API}{ruta}?activo=true", headers=h).json()["total"] == 0
    assert client.get(f"{API}{ruta}?activo=false", headers=h).json()["total"] == 1
    r = client.patch(f"{API}{ruta}/{creado['id']}/estado", headers=h, json={"activo": True})
    assert r.json()["activo"] is True


# ---------------------------------------------------------------- edición de marca
def test_editar_marca_cambia_el_nombre_y_rechaza_duplicados(s):
    client, h = s
    a = crear(client, h, "/compras/marcas", {"nombre": "Campo Verde"})
    crear(client, h, "/compras/marcas", {"nombre": "Sabana Fresca"})
    r = client.put(f"{API}/compras/marcas/{a['id']}", headers=h, json={"nombre": "Campo Nuevo"})
    assert r.status_code == 200 and r.json()["nombre"] == "Campo Nuevo"
    r = client.put(f"{API}/compras/marcas/{a['id']}", headers=h, json={"nombre": "Sabana Fresca"})
    assert r.status_code == 409 and "Sabana Fresca" in r.json()["detail"]


# ---------------------------------------------------------------- borrado con historial
def test_proveedor_sin_compras_se_elimina_y_con_compras_no(s):
    client, h = s
    libre = crear(client, h, "/compras/proveedores", {**PROVEEDOR_PRUEBA, "razon_social": "Sin Compras"})
    assert client.delete(f"{API}/compras/proveedores/{libre['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/compras/proveedores/{libre['id']}", headers=h).status_code == 404

    pid = producto(client, h)["id"]
    prov, _ = compra(client, h, pid)
    r = client.delete(f"{API}/compras/proveedores/{prov['id']}", headers=h)
    assert r.status_code == 409
    assert "Puedes desactivarlo en su lugar" in r.json()["detail"]


def test_producto_sin_historial_se_elimina_y_con_historial_no(s):
    client, h = s
    libre = producto(client, h, "Termo", "TER-1")
    assert client.delete(f"{API}/compras/productos/{libre['id']}", headers=h).status_code == 204
    assert client.get(f"{API}/compras/productos/{libre['id']}", headers=h).status_code == 404

    usado = producto(client, h)
    compra(client, h, usado["id"])
    r = client.delete(f"{API}/compras/productos/{usado['id']}", headers=h)
    assert r.status_code == 409
    assert "Desactívalo en su lugar" in r.json()["detail"]
    assert client.get(f"{API}/compras/productos/{usado['id']}", headers=h).json()["stock"] == 4


# ---------------------------------------------------------------- PDF
def test_pdf_de_compra_y_de_pedido(s):
    client, h = s
    pid = producto(client, h)["id"]
    _, c = compra(client, h, pid)
    r = client.get(f"{API}/compras/compras/{c['id']}/pdf", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF")

    pedido = crear(client, h, "/ventas/pedidos", {
        "cliente_nombre": "Carlos Cliente", "fecha": "2026-03-10T09:00:00",
        "items": [{"producto_id": pid, "cantidad": 1, "precio_unitario": "1000"}],
    })
    r = client.get(f"{API}/ventas/pedidos/{pedido['id']}/pdf", headers=h)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert client.get(f"{API}/ventas/pedidos/{AJENO}/pdf", headers=h).status_code == 404
