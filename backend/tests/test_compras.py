from tests.nombres import letras


def test_listar_categorias_sin_token(client):
    resp = client.get("/api/v1/compras/categorias")
    assert resp.status_code == 401


def test_crud_categoria(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    resp = client.post("/api/v1/compras/categorias", headers=headers, json={"nombre": "Bebidas"})
    assert resp.status_code == 201
    categoria_id = resp.json()["id"]

    resp = client.get("/api/v1/compras/categorias", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert len(resp.json()["items"]) == 1

    resp = client.put(
        f"/api/v1/compras/categorias/{categoria_id}",
        headers=headers,
        json={"nombre": "Bebidas y snacks"},
    )
    assert resp.status_code == 200
    assert resp.json()["nombre"] == "Bebidas y snacks"

    resp = client.delete(f"/api/v1/compras/categorias/{categoria_id}", headers=headers)
    assert resp.status_code == 204


def test_categoria_nombre_duplicado(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    client.post("/api/v1/compras/categorias", headers=headers, json={"nombre": "Bebidas"})
    resp = client.post("/api/v1/compras/categorias", headers=headers, json={"nombre": "Bebidas"})

    assert resp.status_code == 409


def test_crear_producto_ok(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    resp = client.post(
        "/api/v1/compras/productos",
        headers=headers,
        json={"nombre": "Gaseosa Litro", "sku": "GAS-001", "precio": "5000", "stock_inicial": 10},
    )

    assert resp.status_code == 201
    body = resp.json()
    # El stock ya no se escribe al crear: nace en 0 aunque el cliente mande stock_inicial.
    assert body["stock"] == 0
    assert body["activo"] is True


def test_crear_producto_precio_negativo(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    resp = client.post(
        "/api/v1/compras/productos",
        headers=headers,
        json={"nombre": "Gaseosa Litro", "sku": "GAS-001", "precio": "-100"},
    )

    assert resp.status_code == 422


def test_crear_producto_sku_duplicado(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    client.post(
        "/api/v1/compras/productos",
        headers=headers,
        json={"nombre": "Gaseosa Litro", "sku": "GAS-001", "precio": "5000"},
    )
    resp = client.post(
        "/api/v1/compras/productos",
        headers=headers,
        json={"nombre": "Otra gaseosa", "sku": "GAS-001", "precio": "6000"},
    )

    assert resp.status_code == 409


def test_producto_de_otro_tenant_no_es_visible(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    admin_a = usuario_factory(tenant_a)
    admin_b = usuario_factory(tenant_b)

    client.post(
        "/api/v1/compras/productos",
        headers=auth_headers_factory(admin_a),
        json={"nombre": "Producto A", "sku": "A-001", "precio": "1000"},
    )

    resp = client.get("/api/v1/compras/productos", headers=auth_headers_factory(admin_b))
    assert resp.status_code == 200
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 0


def _crear_producto(client, headers, sku="SKU-1", precio="1000"):
    resp = client.post(
        "/api/v1/compras/productos",
        headers=headers,
        json={"nombre": "Producto", "sku": sku, "precio": precio},
    )
    return resp.json()


def _crear_proveedor(client, headers):
    resp = client.post(
        "/api/v1/compras/proveedores",
        headers=headers,
        json={"tipo_persona": "juridica", "nit": "900123456-8", "razon_social": "Proveedor SAS", "representante_nombre": "Pedro Pérez"},
    )
    return resp.json()


def test_crear_compra_confirmar_suma_stock(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers)
    proveedor = _crear_proveedor(client, headers)

    resp = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 5, "precio_unitario": "1000"}],
        },
    )
    assert resp.status_code == 201
    compra = resp.json()
    assert compra["estado"] == "pendiente"
    assert compra["total"] == "5000.00"

    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/confirmar", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "confirmada"

    resp = client.get("/api/v1/compras/productos", headers=headers)
    assert resp.json()["items"][0]["stock"] == 5


def test_confirmar_compra_dos_veces_falla(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers)
    proveedor = _crear_proveedor(client, headers)

    compra = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 2, "precio_unitario": "1000"}],
        },
    ).json()

    client.post(f"/api/v1/compras/compras/{compra['id']}/confirmar", headers=headers)
    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/confirmar", headers=headers)

    assert resp.status_code == 409


def test_crear_compra_producto_de_otro_tenant_falla(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    admin_a = usuario_factory(tenant_a)
    admin_b = usuario_factory(tenant_b)

    producto_b = _crear_producto(client, auth_headers_factory(admin_b))
    proveedor_a = _crear_proveedor(client, auth_headers_factory(admin_a))

    resp = client.post(
        "/api/v1/compras/compras",
        headers=auth_headers_factory(admin_a),
        json={
            "proveedor_id": proveedor_a["id"],
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto_b["id"], "cantidad": 1, "precio_unitario": "1000"}],
        },
    )

    assert resp.status_code == 404


def test_crear_compra_cantidad_invalida(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers)
    proveedor = _crear_proveedor(client, headers)

    resp = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 0, "precio_unitario": "1000"}],
        },
    )

    assert resp.status_code == 422


def test_cancelar_compra_confirmada_falla(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers)
    proveedor = _crear_proveedor(client, headers)

    compra = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 1, "precio_unitario": "1000"}],
        },
    ).json()
    client.post(f"/api/v1/compras/compras/{compra['id']}/confirmar", headers=headers)

    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/cancelar", headers=headers)
    assert resp.status_code == 409


def test_busqueda_y_paginacion_de_productos(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)
    for i in range(12):
        client.post(
            "/api/v1/compras/productos",
            headers=headers,
            json={"nombre": f"Producto {letras(i)}", "sku": f"SKU-{i:02d}", "precio": "100"},
        )

    pagina1 = client.get("/api/v1/compras/productos", headers=headers, params={"por_pagina": 5}).json()
    assert pagina1["total"] == 12
    assert pagina1["paginas"] == 3
    assert len(pagina1["items"]) == 5

    pagina3 = client.get("/api/v1/compras/productos", headers=headers, params={"por_pagina": 5, "pagina": 3}).json()
    assert len(pagina3["items"]) == 2

    busqueda = client.get("/api/v1/compras/productos", headers=headers, params={"q": "sku-1"}).json()
    assert busqueda["total"] == 2  # SKU-10 y SKU-11
