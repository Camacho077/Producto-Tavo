"""
EXPORTAR A CSV — `?formato=csv` en los nueve listados (app/core/exportar.py).

Es el MISMO endpoint del listado: misma consulta, mismos filtros, misma
búsqueda, mismo permiso y mismos campos ocultos. Se prueba que así sea.
"""
import csv
import io
from datetime import datetime
from decimal import Decimal

import pytest

from app.core.exportar import _celda
from tests.conftest import PROVEEDOR_PRUEBA

API = "/api/v1"

LISTADOS = [
    "/compras/categorias",
    "/compras/marcas",
    "/compras/proveedores",
    "/compras/productos",
    "/compras/compras",
    "/ventas/ventas",
    "/ventas/pedidos",
    "/seguridad/usuarios",
    "/seguridad/roles",
]


def leer_csv(resp):
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]
    texto = resp.content.decode("utf-8")
    assert texto.startswith("﻿"), "sin BOM, Excel lee mal las tildes"
    return list(csv.reader(io.StringIO(texto[1:]), delimiter=";"))


@pytest.fixture()
def empresa(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h = auth_headers_factory(usuario_factory(tenant, nombre_completo="Ana Admin"))
    return client, h, tenant


def crear_producto(client, h, nombre, sku, precio="1000"):
    r = client.post(f"{API}/compras/productos", headers=h, json={"nombre": nombre, "sku": sku, "precio": precio})
    assert r.status_code == 201, r.json()
    return r.json()["id"]


@pytest.mark.parametrize("ruta", LISTADOS)
def test_cada_listado_exporta_csv_con_encabezado(empresa, ruta):
    client, h, _ = empresa
    filas = leer_csv(client.get(f"{API}{ruta}?formato=csv", headers=h))
    assert len(filas) >= 1 and filas[0], ruta


def test_respeta_la_busqueda_y_trae_todas_las_paginas(empresa):
    client, h, _ = empresa
    for i, nombre in enumerate(["Arroz", "Aceite", "Azucar", "Leche"] * 4):
        client.post(f"{API}/compras/categorias", headers=h, json={"nombre": f"{nombre} {'abcdefghijklmnop'[i]}"})
    filas = leer_csv(client.get(f"{API}/compras/categorias?formato=csv&q=a&por_pagina=2&pagina=3", headers=h))
    nombres = [f[0] for f in filas[1:]]
    # La paginación de la pantalla NO recorta el archivo; la búsqueda sí filtra.
    assert len(nombres) == 12 and all(n[0] == "A" for n in nombres)


def test_respeta_los_filtros(empresa):
    client, h, _ = empresa
    a = client.post(f"{API}/compras/marcas", headers=h, json={"nombre": "Activa"}).json()
    b = client.post(f"{API}/compras/marcas", headers=h, json={"nombre": "Pausada"}).json()
    assert client.patch(f"{API}/compras/marcas/{b['id']}/estado", headers=h, json={"activo": False}).status_code == 200
    filas = leer_csv(client.get(f"{API}/compras/marcas?formato=csv&activo=true", headers=h))
    assert [f[0] for f in filas[1:]] == [a["nombre"]]


def test_formato_de_numeros_fechas_y_estados(empresa):
    client, h, _ = empresa
    pid = crear_producto(client, h, "Cafe", "CAF-1", precio="12500.5")
    prov = client.post(f"{API}/compras/proveedores", headers=h, json=PROVEEDOR_PRUEBA).json()["id"]
    client.post(f"{API}/compras/compras", headers=h, json={
        "proveedor_id": prov, "fecha": "2026-03-10T20:30:00", "confirmar": True,
        "items": [{"producto_id": pid, "cantidad": 3, "precio_unitario": "1000"}],
    })
    filas = leer_csv(client.get(f"{API}/compras/compras?formato=csv", headers=h))
    encabezado, fila = filas[0], filas[1]
    dato = dict(zip(encabezado, fila))
    assert dato["Fecha"] == "2026-03-10 15:30"  # 20:30 UTC = 15:30 en Colombia
    assert dato["Total"] == "3000,00"  # coma decimal (Excel es-CO)
    assert dato["Productos"] == "Cafe × 3"
    assert dato["Estado"] == "confirmada"
    productos = leer_csv(client.get(f"{API}/compras/productos?formato=csv", headers=h))
    assert dict(zip(productos[0], productos[1]))["Precio de venta"] == "12500,50"


def test_el_costo_solo_lo_exporta_quien_lo_ve(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h_admin = auth_headers_factory(usuario_factory(tenant))
    pid = crear_producto(client, h_admin, "Cafe", "CAF-1")
    prov = client.post(f"{API}/compras/proveedores", headers=h_admin, json=PROVEEDOR_PRUEBA).json()["id"]
    client.post(f"{API}/compras/compras", headers=h_admin, json={
        "proveedor_id": prov, "fecha": "2026-03-10T09:00:00", "confirmar": True,
        "items": [{"producto_id": pid, "cantidad": 3, "precio_unitario": "777"}],
    })
    assert "Costo" in leer_csv(client.get(f"{API}/compras/productos?formato=csv", headers=h_admin))[0]

    cajero = rol_factory(tenant, nombre="Cajero", permisos={"productos": ["ver"]})
    r = client.get(f"{API}/compras/productos?formato=csv", headers=auth_headers_factory(usuario_factory(tenant, rol=cajero)))
    assert "Costo" not in leer_csv(r)[0]
    assert "777" not in r.text


def test_sin_permiso_de_ver_no_exporta(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    rol = rol_factory(tenant, nombre="Ventas", permisos={"ventas": ["ver"]})
    h = auth_headers_factory(usuario_factory(tenant, rol=rol))
    r = client.get(f"{API}/compras/compras?formato=csv", headers=h)
    assert r.status_code == 403
    assert "no tiene permiso para ver compras" in r.json()["detail"]


def test_nunca_exporta_datos_de_otra_empresa(client, tenant_factory, usuario_factory, auth_headers_factory):
    a, b = tenant_factory(), tenant_factory()
    h_a, h_b = auth_headers_factory(usuario_factory(a)), auth_headers_factory(usuario_factory(b))
    crear_producto(client, h_a, "Secreto", "SEC-1")
    client.post(f"{API}/compras/categorias", headers=h_a, json={"nombre": "Reservada"})
    for ruta in LISTADOS:
        r = client.get(f"{API}{ruta}?formato=csv", headers=h_b)
        assert "Secreto" not in r.text and "Reservada" not in r.text, ruta


def test_formato_desconocido_es_422(empresa):
    client, h, _ = empresa
    assert client.get(f"{API}/compras/marcas?formato=xlsx", headers=h).status_code == 422


def test_sin_formato_el_listado_sigue_siendo_json_paginado(empresa):
    client, h, _ = empresa
    cuerpo = client.get(f"{API}/compras/marcas", headers=h).json()
    assert set(cuerpo) == {"items", "total", "pagina", "por_pagina", "paginas"}


def test_celdas_que_parecen_formulas_se_neutralizan():
    assert _celda("=HYPERLINK(\"http://x\")") == "'=HYPERLINK(\"http://x\")"
    assert _celda("+57 300") == "'+57 300"
    assert _celda("@SUMA") == "'@SUMA"
    assert _celda("-algo") == "'-algo"
    assert _celda("-5") == "-5"
    assert _celda(Decimal("1234.5")) == "1234,50"
    assert _celda(True) == "Sí"
    assert _celda(datetime(2026, 1, 1, 3, 0)) == "2025-12-31 22:00"
