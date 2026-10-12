"""Categorías de la carta, platos (alta básica) y compras de insumos."""
from decimal import Decimal

from tests.conftest import API_V1 as API, PROVEEDOR_PRUEBA, crear_insumo


def test_listar_categorias_sin_token(client):
    assert client.get(f"{API}/catalogo/categorias").status_code == 401


def test_crud_categoria(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    resp = client.post(f"{API}/catalogo/categorias", headers=headers, json={"nombre": "Bebidas", "orden": 2})
    assert resp.status_code == 201 and resp.json()["orden"] == 2
    categoria_id = resp.json()["id"]
    assert client.get(f"{API}/catalogo/categorias", headers=headers).json()["total"] == 1
    resp = client.put(f"{API}/catalogo/categorias/{categoria_id}", headers=headers, json={"nombre": "Bebidas frías"})
    assert resp.json()["nombre"] == "Bebidas frías"
    assert client.delete(f"{API}/catalogo/categorias/{categoria_id}", headers=headers).status_code == 204


def test_categoria_nombre_duplicado_y_bloqueo_por_platos(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    cat = client.post(f"{API}/catalogo/categorias", headers=headers, json={"nombre": "Bebidas"}).json()
    assert client.post(f"{API}/catalogo/categorias", headers=headers, json={"nombre": "Bebidas"}).status_code == 409
    client.post(f"{API}/catalogo/productos", headers=headers, json={"nombre": "Limonada", "precio": "4000", "categoria_id": cat["id"]})
    resp = client.delete(f"{API}/catalogo/categorias/{cat['id']}", headers=headers)
    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        "No se puede eliminar la categoría Bebidas: tiene 1 producto asociado. "
        "Puedes desactivarla en su lugar para conservar el historial."
    )


def test_crear_plato_ok_y_precio_negativo(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    resp = client.post(f"{API}/catalogo/productos", headers=headers, json={"nombre": "Gaseosa 1.5 L", "sku": "gas-001", "precio": "5000"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["sku"] == "GAS-001" and body["tipo"] == "plato" and body["activo"] is True and "stock" not in body
    resp = client.post(f"{API}/catalogo/productos", headers=headers, json={"nombre": "Otra", "precio": "-100"})
    assert resp.status_code == 422


def test_codigo_duplicado(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    client.post(f"{API}/catalogo/productos", headers=headers, json={"nombre": "Gaseosa", "sku": "GAS-001", "precio": "5000"})
    resp = client.post(f"{API}/catalogo/productos", headers=headers, json={"nombre": "Otra gaseosa", "sku": "GAS-001", "precio": "6000"})
    assert resp.status_code == 409 and "GAS-001" in resp.json()["detail"]


def test_plato_de_otro_tenant_no_es_visible(client, tenant_factory, usuario_factory, auth_headers_factory):
    ha = auth_headers_factory(usuario_factory(tenant_factory()))
    hb = auth_headers_factory(usuario_factory(tenant_factory()))
    client.post(f"{API}/catalogo/productos", headers=ha, json={"nombre": "Plato A", "precio": "1000"})
    assert client.get(f"{API}/catalogo/productos", headers=hb).json()["items"] == []


def _preparar(client, headers):
    proveedor = client.post(f"{API}/compras/proveedores", headers=headers, json=PROVEEDOR_PRUEBA).json()
    insumo = crear_insumo(client, headers, "Arroz", "kg")
    return proveedor, insumo


def _compra(client, headers, proveedor, insumo, confirmar, cantidad="5", unidad="kg"):
    return client.post(f"{API}/compras/compras", headers=headers, json={
        "proveedor_id": proveedor["id"], "fecha": "2026-01-01T09:00:00", "confirmar": confirmar,
        "items": [{"insumo_id": insumo["id"], "cantidad": cantidad, "unidad": unidad, "precio_unitario": "4000"}],
    })


def test_compra_pendiente_no_mueve_y_confirmar_suma(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    proveedor, insumo = _preparar(client, headers)
    resp = _compra(client, headers, proveedor, insumo, False)
    assert resp.status_code == 201
    compra = resp.json()
    assert compra["estado"] == "pendiente" and compra["codigo"].startswith("COM-") and compra["total"] == "20000.00"
    assert Decimal(client.get(f"{API}/inventario/insumos/{insumo['id']}", headers=headers).json()["existencia"]) == 0
    resp = client.post(f"{API}/compras/compras/{compra['id']}/confirmar", headers=headers)
    assert resp.json()["estado"] == "confirmada"
    assert Decimal(client.get(f"{API}/inventario/insumos/{insumo['id']}", headers=headers).json()["existencia"]) == 5
    # Confirmar dos veces y cancelar una confirmada: 409.
    assert client.post(f"{API}/compras/compras/{compra['id']}/confirmar", headers=headers).status_code == 409
    assert client.post(f"{API}/compras/compras/{compra['id']}/cancelar", headers=headers).status_code == 409


def test_compra_con_insumo_de_otro_tenant_falla(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    proveedor, _ = _preparar(client, headers)
    ajeno = crear_insumo(client, auth_headers_factory(usuario_factory(tenant_factory())), "Ajeno")
    assert _compra(client, headers, proveedor, ajeno, True, unidad="unidad").status_code == 404


def test_compra_cantidad_invalida(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    proveedor, insumo = _preparar(client, headers)
    for cantidad in ("0", "-1", "1.2345"):
        assert _compra(client, headers, proveedor, insumo, True, cantidad=cantidad).status_code == 422


def test_compra_repite_un_insumo(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    proveedor, insumo = _preparar(client, headers)
    linea = {"insumo_id": insumo["id"], "cantidad": "1", "unidad": "kg", "precio_unitario": "4000"}
    resp = client.post(f"{API}/compras/compras", headers=headers, json={
        "proveedor_id": proveedor["id"], "fecha": "2026-01-01T09:00:00", "confirmar": True, "items": [linea, linea],
    })
    assert resp.status_code == 409 and "repite el insumo Arroz" in resp.json()["detail"]


def test_busqueda_y_paginacion_de_platos(client, tenant_factory, usuario_factory, auth_headers_factory):
    from tests.nombres import letras

    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    for i in range(12):
        client.post(f"{API}/catalogo/productos", headers=headers, json={"nombre": f"Plato {letras(i)}", "sku": f"SKU-{i:02d}", "precio": "100"})
    pagina1 = client.get(f"{API}/catalogo/productos", headers=headers, params={"por_pagina": 5}).json()
    assert pagina1["total"] == 12 and pagina1["paginas"] == 3 and len(pagina1["items"]) == 5
    pagina3 = client.get(f"{API}/catalogo/productos", headers=headers, params={"por_pagina": 5, "pagina": 3}).json()
    assert len(pagina3["items"]) == 2
    busqueda = client.get(f"{API}/catalogo/productos", headers=headers, params={"q": "sku-1"}).json()
    assert busqueda["total"] == 2  # SKU-10 y SKU-11
