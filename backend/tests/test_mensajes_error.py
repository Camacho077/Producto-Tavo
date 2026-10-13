"""
Protección de la regla: NINGÚN endpoint devuelve un error genérico.

Cada `detail` que sale del backend es la frase que el usuario lee en la
alerta roja del frontend, así que tiene que nombrar el registro concreto y
explicar la causa. Estos tests recorren los caminos de error reales de cada
módulo y fallan si alguno vuelve a un mensaje sin causa.
"""
import re

import pytest

from tests.nombres import letras

from app.core import mensajes
from tests.conftest import PROVEEDOR_PRUEBA

# Frases que delatan un error sin causa: si un endpoint devuelve algo así,
# el usuario no sabe qué hacer con la alerta.
FRASES_GENERICAS = (
    "no se pudo completar la operación",
    "ocurrió un error",
    "error inesperado",
    "operación fallida",
    "intenta de nuevo",
    "algo salió mal",
    "bad request",
    "internal server error",
)


def assert_util(detail: str, *fragmentos: str):
    """Un mensaje útil: en español, específico, y con los datos esperados."""
    assert isinstance(detail, str) and detail, "el error no trae un detail de texto"
    bajo = detail.lower()
    for generica in FRASES_GENERICAS:
        assert generica not in bajo, f"mensaje genérico: {detail!r}"
    # Una causa concreta siempre trae al menos un dato: un nombre, un código
    # o una cifra. Un mensaje de solo cuatro palabras sin datos no sirve.
    assert len(detail.split()) >= 6, f"mensaje demasiado escueto: {detail!r}"
    for fragmento in fragmentos:
        assert fragmento in detail, f"falta {fragmento!r} en {detail!r}"


# =====================================================================
# Constructores de mensajes (app/core/mensajes.py)
# =====================================================================
def test_plural_y_unidades():
    assert mensajes.plural(1, "producto") == "1 producto"
    assert mensajes.plural(3, "producto") == "3 productos"
    assert mensajes.unidades(1) == "1 unidad"
    assert mensajes.unidades(5) == "5 unidades"


def test_no_se_puede_eliminar_nombra_el_registro_y_la_dependencia():
    texto = mensajes.no_se_puede_eliminar(
        "la categoría", "Celulares", 3, "producto", "productos", "Puedes desactivarla en su lugar."
    )
    assert texto.startswith("No se puede eliminar la categoría Celulares: tiene 3 productos asociados.")


# =====================================================================
# Caminos de error reales, endpoint por endpoint
# =====================================================================
@pytest.fixture()
def sesion(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    return client, auth_headers_factory(admin), admin


def _crear(client, headers, recurso, payload, esperado=201):
    resp = client.post(f"/api/v1/{recurso}", headers=headers, json=payload)
    assert resp.status_code == esperado, resp.json()
    return resp.json()


def test_nombre_duplicado_dice_cual_es_el_nombre(sesion):
    client, headers, _ = sesion
    _crear(client, headers, "catalogo/categorias", {"nombre": "Celulares"})
    resp = client.post("/api/v1/catalogo/categorias", headers=headers, json={"nombre": "Celulares"})
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], "Celulares", "nombre")


def test_sku_duplicado_dice_cual_es_el_sku(sesion):
    client, headers, _ = sesion
    _crear(client, headers, "catalogo/productos", {"nombre": "Teclado", "sku": "TEC-1", "precio": "1000"})
    resp = client.post(
        "/api/v1/catalogo/productos", headers=headers, json={"nombre": "Otro", "sku": "TEC-1", "precio": "1000"}
    )
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], "TEC-1", "código")


def test_eliminar_categoria_con_productos_dice_nombre_y_cuantos(sesion):
    client, headers, _ = sesion
    categoria = _crear(client, headers, "catalogo/categorias", {"nombre": "Celulares"})
    for i in range(3):
        _crear(
            client, headers, "catalogo/productos",
            {"nombre": f"Equipo {letras(i)}", "sku": f"EQ-{i}", "precio": "1000", "categoria_id": categoria["id"]},
        )
    resp = client.delete(f"/api/v1/catalogo/categorias/{categoria['id']}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        "No se puede eliminar la categoría Celulares: tiene 3 productos asociados. "
        "Puedes desactivarla en su lugar para conservar el historial."
    )


def test_eliminar_rol_con_usuarios_dice_nombre_y_cuantos(sesion, db_session, usuario_factory, rol_factory):
    client, headers, admin = sesion
    # Un rol normal con un usuario (el Administrador ni siquiera se puede
    # eliminar: tiene su propio mensaje, probado en test_permisos.py).
    tenant = _tenant(db_session, admin.tenant_id)
    cajero = rol_factory(tenant, nombre="Cajero", permisos={"ventas": ["ver"]})
    usuario_factory(tenant, rol=cajero)
    resp = client.delete(f"/api/v1/seguridad/roles/{cajero.id}", headers=headers)
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], "Cajero", "1 usuario asociado", "Reasígnalos a otro rol")


def _tenant(db_session, tenant_id):
    from app.db.models import Tenant

    return db_session.get(Tenant, tenant_id)


def _plato(client, headers, nombre, precio):
    """Plato que gasta una unidad del insumo `nombre`; devuelve (plato, insumo)."""
    insumo = _crear(client, headers, "inventario/insumos", {"nombre": nombre, "unidad": "unidad"})
    plato = _crear(client, headers, "catalogo/productos", {
        "nombre": f"Plato de {nombre}", "precio": precio, "receta": [{"insumo_id": insumo["id"], "cantidad": "1", "unidad": "unidad"}],
    })
    return plato, insumo


def _linea(insumo, cantidad, precio):
    return {"insumo_id": insumo["id"], "cantidad": str(cantidad), "unidad": "unidad", "precio_unitario": precio}


def test_venta_sin_existencias_dice_insumo_cuanto_queda_y_cuanto_necesita(sesion):
    client, headers, _ = sesion
    producto, insumo = _plato(client, headers, "Queso", "5000")
    proveedor = _crear(client, headers, "compras/proveedores", PROVEEDOR_PRUEBA)
    _crear(
        client, headers, "compras/compras",
        {
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T09:00:00",
            "confirmar": True,
            "items": [_linea(insumo, 2, "4000")],
        },
    )
    resp = client.post("/api/v1/ordenes", headers=headers, json={"tipo": "llevar", "items": [{"producto_id": producto["id"], "cantidad": 5}]})
    assert resp.status_code == 409
    assert resp.json()["detail"] == "No se pudo enviar la orden: quedan 2 unidades de Queso y la orden necesita 5 unidades."


def test_anular_compra_cuyo_stock_ya_se_vendio_explica_el_negativo(sesion):
    client, headers, _ = sesion
    producto, insumo = _plato(client, headers, "Diadema", "300")
    proveedor = _crear(client, headers, "compras/proveedores", PROVEEDOR_PRUEBA)
    compra = _crear(
        client, headers, "compras/compras",
        {
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T09:00:00",
            "confirmar": True,
            "items": [_linea(insumo, 4, "200")],
        },
    )
    _crear(client, headers, "ordenes", {"tipo": "llevar", "items": [{"producto_id": producto["id"], "cantidad": 3}]})
    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/anular", headers=headers)
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], compra["codigo"], "Diadema", "quedan 1 unidad", "negativo")


def test_estado_invalido_nombra_el_documento_y_los_estados(sesion):
    client, headers, _ = sesion
    producto, insumo = _plato(client, headers, "Mouse", "100")
    proveedor = _crear(client, headers, "compras/proveedores", PROVEEDOR_PRUEBA)
    compra = _crear(
        client, headers, "compras/compras",
        {
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T09:00:00",
            "confirmar": True,
            "items": [_linea(insumo, 1, "80")],
        },
    )
    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/confirmar", headers=headers)
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], compra["codigo"], "confirmada", "pendiente")


def test_entregar_sin_nada_listo_dice_que_comanda_falta(sesion):
    client, headers, _ = sesion
    producto, insumo = _plato(client, headers, "Cable", "100")
    _crear(client, headers, "compras/compras", {
        "proveedor_id": _crear(client, headers, "compras/proveedores", PROVEEDOR_PRUEBA)["id"], "fecha": "2026-01-01T09:00:00",
        "confirmar": True, "items": [_linea(insumo, 5, "80")],
    })
    orden = _crear(client, headers, "ordenes", {"tipo": "llevar", "items": [{"producto_id": producto["id"]}]})
    resp = client.post(f"/api/v1/ordenes/{orden['id']}/entregar", headers=headers)
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], f"#{orden['numero']}", "comanda 1", "por empezar")


def test_registro_inexistente_dice_que_puede_ser_de_otra_empresa(sesion):
    client, headers, _ = sesion
    resp = client.get("/api/v1/catalogo/productos/00000000-0000-0000-0000-000000000001", headers=headers)
    assert resp.status_code == 404
    assert_util(resp.json()["detail"], "producto", "otra empresa")


def test_no_puedes_eliminarte_a_ti_mismo_explica_por_que(sesion):
    client, headers, admin = sesion
    resp = client.delete(f"/api/v1/seguridad/usuarios/{admin.id}", headers=headers)
    assert resp.status_code == 409
    assert_util(resp.json()["detail"], "propio usuario")


# =====================================================================
# Barrido: ningún módulo conserva una frase genérica en el código
# =====================================================================
def test_ningun_raise_del_backend_usa_una_frase_generica():
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1] / "app"
    patron = re.compile(r"(Conflict|NotFound|Forbidden|Auth|App)Error\(\s*(?:f?\"([^\"]*)\")?")
    problemas = []
    for archivo in raiz.rglob("*.py"):
        if archivo.name in ("errors.py", "mensajes.py"):
            continue
        for numero, linea in enumerate(archivo.read_text(encoding="utf-8").splitlines(), 1):
            m = patron.search(linea)
            texto = m.group(2) if m else None
            if not texto:
                continue
            if any(g in texto.lower() for g in FRASES_GENERICAS):
                problemas.append(f"{archivo.name}:{numero} → {texto}")
    assert not problemas, "mensajes genéricos encontrados:\n" + "\n".join(problemas)
