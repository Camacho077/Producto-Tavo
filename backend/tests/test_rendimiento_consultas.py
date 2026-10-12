"""
Protección contra N+1 en los listados.

Un listado paginado tiene que costar un número FIJO de consultas, sin
importar cuántas filas devuelva: si crece con el número de filas, alguien
quitó un `joinedload` y el listado se degrada solo al llenarse de datos.

Cada test pide el mismo endpoint con 1 fila y con 10, y exige que el conteo
de consultas sea el mismo.
"""
import pytest

from tests.nombres import letras
from sqlalchemy import event

from app.core.validaciones import digito_verificacion_nit
from tests.conftest import PROVEEDOR_PRUEBA

# Nombres sin dígitos: el validador de nombre de persona solo admite letras.
ORDINALES = ["Uno", "Dos", "Tres", "Cuatro", "Cinco", "Seis", "Siete", "Ocho", "Nueve", "Diez", "Once", "Doce"]


class ContadorDeConsultas:
    """Cuenta los SELECT que salen hacia Postgres durante un bloque."""

    def __init__(self, db_session):
        self.conexion = db_session.get_bind()
        self.consultas = []

    def __enter__(self):
        event.listen(self.conexion, "before_cursor_execute", self._registrar)
        return self

    def __exit__(self, *_):
        event.remove(self.conexion, "before_cursor_execute", self._registrar)

    def _registrar(self, conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            self.consultas.append(statement)

    def __len__(self):
        return len(self.consultas)


@pytest.fixture()
def sesion(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    return client, auth_headers_factory(admin)


def _producto(client, headers, i):
    return client.post(
        "/api/v1/compras/productos",
        headers=headers,
        json={"nombre": f"Producto {letras(i)}", "sku": f"SKU-{i}", "precio": "1000", "categoria_id": None},
    ).json()


def _nit(i):
    """NIT con el dígito de verificación real de la DIAN (el backend lo exige)."""
    base = f"9001234{i:02d}"
    return f"{base}-{digito_verificacion_nit(base)}"


def _proveedor(client, headers, i):
    datos = dict(PROVEEDOR_PRUEBA, razon_social=f"Proveedor {ORDINALES[i]}", nit=_nit(i))
    resp = client.post("/api/v1/compras/proveedores", headers=headers, json=datos)
    assert resp.status_code == 201, resp.json()
    return resp.json()


def _compra(client, headers, proveedor_id, producto_id):
    return client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor_id,
            "fecha": "2026-01-01T09:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto_id, "cantidad": 5, "precio_unitario": "500"}],
        },
    ).json()


def _venta(client, headers, producto_id):
    return client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Carlos Cliente",
            "fecha": "2026-01-02T09:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto_id, "cantidad": 1, "precio_unitario": "1000"}],
        },
    ).json()


def _pedido(client, headers, producto_id):
    return client.post(
        "/api/v1/ventas/pedidos",
        headers=headers,
        json={
            "cliente_nombre": "Carlos Cliente",
            "fecha": "2026-01-02T09:00:00",
            "items": [{"producto_id": producto_id, "cantidad": 1, "precio_unitario": "1000"}],
        },
    ).json()


def _consultas_de(client, db_session, url, headers):
    # por_pagina=50 para que las 10 filas quepan en UNA página: si se
    # quedaran fuera por el tope de 10 por defecto, el listado parecería
    # constante solo porque nunca llegó a serializar las filas de más.
    separador = "&" if "?" in url else "?"
    with ContadorDeConsultas(db_session) as contador:
        resp = client.get(f"{url}{separador}por_pagina=50", headers=headers)
        assert resp.status_code == 200, resp.json()
    return len(contador), resp.json()


def _comparar(client, db_session, headers, url, sembrar, primera=1, resto=9, ya_existentes=0):
    """Siembra `primera` filas, mide; siembra `resto` más, vuelve a medir."""
    for i in range(primera):
        sembrar(i)
    pocas, cuerpo_pocas = _consultas_de(client, db_session, url, headers)

    for i in range(primera, primera + resto):
        sembrar(i)
    muchas, cuerpo_muchas = _consultas_de(client, db_session, url, headers)

    assert len(cuerpo_pocas["items"]) == primera + ya_existentes
    assert len(cuerpo_muchas["items"]) == primera + resto + ya_existentes
    assert muchas == pocas, (
        f"{url} hace N+1: {pocas} consultas con {primera} fila(s) y {muchas} con "
        f"{primera + resto}. Falta un joinedload/selectinload."
    )
    return pocas


def test_listado_de_compras_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session):
    client, headers = sesion
    productos = [_producto(client, headers, i) for i in range(10)]
    proveedor = _proveedor(client, headers, 0)
    _comparar(client, db_session, headers, "/api/v1/compras/compras", lambda i: _compra(client, headers, proveedor["id"], productos[i]["id"]))


def test_listado_de_ventas_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session):
    client, headers = sesion
    productos = [_producto(client, headers, i) for i in range(10)]
    proveedor = _proveedor(client, headers, 0)
    for p in productos:
        _compra(client, headers, proveedor["id"], p["id"])
    _comparar(client, db_session, headers, "/api/v1/ventas/ventas", lambda i: _venta(client, headers, productos[i]["id"]))


def test_listado_de_pedidos_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session):
    client, headers = sesion
    productos = [_producto(client, headers, i) for i in range(10)]
    _comparar(client, db_session, headers, "/api/v1/ventas/pedidos", lambda i: _pedido(client, headers, productos[i]["id"]))


def test_listado_de_productos_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session):
    client, headers = sesion
    _comparar(client, db_session, headers, "/api/v1/compras/productos", lambda i: _producto(client, headers, i))


def test_listado_de_proveedores_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session):
    client, headers = sesion
    _comparar(client, db_session, headers, "/api/v1/compras/proveedores", lambda i: _proveedor(client, headers, i))


def test_listado_de_categorias_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session):
    client, headers = sesion
    _comparar(
        client, db_session, headers, "/api/v1/compras/categorias",
        lambda i: client.post("/api/v1/compras/categorias", headers=headers, json={"nombre": f"Categoria {letras(i)}"}),
    )


def test_listado_de_usuarios_cuesta_lo_mismo_con_1_que_con_10(sesion, db_session, usuario_factory):
    client, headers = sesion
    rol = client.post("/api/v1/seguridad/roles", headers=headers, json={"nombre": "Vendedor", "permisos": {}}).json()

    def crear(i):
        resp = client.post(
            "/api/v1/seguridad/usuarios",
            headers=headers,
            json={
                "nombre_completo": f"Persona {ORDINALES[i]}",
                "email": f"persona{i}@test.com",
                "password": "clave-segura-123",
                "rol_id": rol["id"],
            },
        )
        assert resp.status_code == 201, resp.json()

    # Ya existe el admin de la sesión, así que la primera medición trae 2 filas.
    _comparar(client, db_session, headers, "/api/v1/seguridad/usuarios", crear, primera=1, resto=9, ya_existentes=1)


def test_el_panel_de_avisos_no_crece_con_el_numero_de_productos(sesion, db_session):
    client, headers = sesion
    _producto(client, headers, 0)
    pocas, _ = _consultas_de(client, db_session, "/api/v1/dashboard/avisos", headers)
    for i in range(1, 15):
        _producto(client, headers, i)
    muchas, _ = _consultas_de(client, db_session, "/api/v1/dashboard/avisos", headers)
    assert muchas == pocas, f"/dashboard/avisos hace N+1: {pocas} → {muchas} consultas"
