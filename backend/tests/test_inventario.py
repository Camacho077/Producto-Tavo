"""El stock es el resultado de los movimientos: compras suman, ventas restan,
las anulaciones revierten, y el historial siempre explica el stock actual."""
from tests.conftest import PROVEEDOR_PRUEBA


def _preparar(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Bodega")
    headers = auth_headers_factory(admin)
    producto = client.post(
        "/api/v1/compras/productos", headers=headers, json={"nombre": "Martillo", "sku": "MAR-1", "precio": "1000"}
    ).json()
    proveedor = client.post("/api/v1/compras/proveedores", headers=headers, json=PROVEEDOR_PRUEBA).json()
    return headers, producto, proveedor


def _stock(client, headers, producto_id):
    return client.get(f"/api/v1/compras/productos/{producto_id}", headers=headers).json()["stock"]


def _movimientos(client, headers, producto_id):
    return client.get(f"/api/v1/compras/productos/{producto_id}/movimientos", headers=headers).json()["items"]


def _compra(client, headers, proveedor_id, producto_id, cantidad, confirmar=True):
    resp = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor_id,
            "fecha": "2026-01-01T09:00:00",
            "confirmar": confirmar,
            "items": [{"producto_id": producto_id, "cantidad": cantidad, "precio_unitario": "700"}],
        },
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


def test_producto_nace_con_stock_cero_y_el_stock_no_se_edita(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers, producto, _ = _preparar(client, tenant_factory, usuario_factory, auth_headers_factory)
    assert producto["stock"] == 0

    # Un PUT con "stock" no lo cambia: no es un campo editable.
    resp = client.put(f"/api/v1/compras/productos/{producto['id']}", headers=headers, json={"stock": 500, "nombre": "Martillo"})
    assert resp.status_code == 200
    assert resp.json()["stock"] == 0


def test_compra_suma_anular_revierte_y_el_historial_explica_el_stock(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers, producto, proveedor = _preparar(client, tenant_factory, usuario_factory, auth_headers_factory)

    compra = _compra(client, headers, proveedor["id"], producto["id"], 12)
    assert _stock(client, headers, producto["id"]) == 12

    movs = _movimientos(client, headers, producto["id"])
    assert [(m["tipo"], m["cantidad"], m["stock_resultante"]) for m in movs] == [("compra", 12, 12)]
    assert movs[0]["documento_codigo"] == compra["codigo"]
    assert movs[0]["usuario_nombre"] == "Ana Bodega"

    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/anular", headers=headers)
    assert resp.status_code == 200
    assert _stock(client, headers, producto["id"]) == 0  # vuelve a su valor previo

    movs = _movimientos(client, headers, producto["id"])
    assert [(m["tipo"], m["cantidad"]) for m in movs] == [("anulacion_compra", -12), ("compra", 12)]
    assert sum(m["cantidad"] for m in movs) == _stock(client, headers, producto["id"])


def test_venta_resta_anular_devuelve_y_suma_de_movimientos_coincide(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers, producto, proveedor = _preparar(client, tenant_factory, usuario_factory, auth_headers_factory)
    _compra(client, headers, proveedor["id"], producto["id"], 10)

    venta = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-02T10:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto["id"], "cantidad": 4, "precio_unitario": "1000"}],
        },
    ).json()
    assert _stock(client, headers, producto["id"]) == 6

    client.post(f"/api/v1/ventas/ventas/{venta['id']}/anular", headers=headers)
    assert _stock(client, headers, producto["id"]) == 10

    movs = _movimientos(client, headers, producto["id"])
    assert [m["tipo"] for m in movs] == ["anulacion_venta", "venta", "compra"]
    assert sum(m["cantidad"] for m in movs) == 10
    assert movs[0]["stock_resultante"] == 10 and movs[1]["stock_resultante"] == 6


def test_venta_sin_existencias_se_bloquea_y_no_mueve_nada(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers, producto, proveedor = _preparar(client, tenant_factory, usuario_factory, auth_headers_factory)
    _compra(client, headers, proveedor["id"], producto["id"], 3)
    otro = client.post(
        "/api/v1/compras/productos", headers=headers, json={"nombre": "Clavo", "sku": "CLA-1", "precio": "100"}
    ).json()
    _compra(client, headers, proveedor["id"], otro["id"], 50)

    # Dos líneas: la primera cabe, la segunda no. No se descuenta NINGUNA.
    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-02T10:00:00",
            "confirmar": True,
            "items": [
                {"producto_id": otro["id"], "cantidad": 5, "precio_unitario": "100"},
                {"producto_id": producto["id"], "cantidad": 4, "precio_unitario": "1000"},
            ],
        },
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == (
        "No se pudo registrar la venta: el producto Martillo solo tiene 3 unidades y se pidieron 4."
    )
    assert _stock(client, headers, producto["id"]) == 3
    assert _stock(client, headers, otro["id"]) == 50
    assert [m["tipo"] for m in _movimientos(client, headers, otro["id"])] == ["compra"]


def test_anular_compra_con_stock_ya_vendido_se_bloquea(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers, producto, proveedor = _preparar(client, tenant_factory, usuario_factory, auth_headers_factory)
    compra = _compra(client, headers, proveedor["id"], producto["id"], 5)
    client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-02T10:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto["id"], "cantidad": 4, "precio_unitario": "1000"}],
        },
    )
    resp = client.post(f"/api/v1/compras/compras/{compra['id']}/anular", headers=headers)
    assert resp.status_code == 409
    assert _stock(client, headers, producto["id"]) == 1


def test_proveedor_surte_productos_y_el_producto_conoce_sus_proveedores(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers, producto, proveedor = _preparar(client, tenant_factory, usuario_factory, auth_headers_factory)
    otro = client.post(
        "/api/v1/compras/productos", headers=headers, json={"nombre": "Clavo", "sku": "CLA-1", "precio": "100"}
    ).json()

    resp = client.put(
        f"/api/v1/compras/proveedores/{proveedor['id']}",
        headers=headers,
        json={**PROVEEDOR_PRUEBA, "producto_ids": [producto["id"], otro["id"]]},
    )
    assert resp.status_code == 200, resp.json()
    assert sorted(p["sku"] for p in resp.json()["productos"]) == ["CLA-1", "MAR-1"]

    detalle = client.get(f"/api/v1/compras/productos/{producto['id']}", headers=headers).json()
    assert [p["nombre"] for p in detalle["proveedores"]] == ["Proveedor de Pruebas"]

    # Filtro del catálogo por proveedor (para el formulario de compra).
    filtrado = client.get("/api/v1/compras/productos", headers=headers, params={"proveedor_id": proveedor["id"]}).json()
    assert filtrado["total"] == 2

    # Quitar uno no afecta al otro.
    resp = client.put(
        f"/api/v1/compras/proveedores/{proveedor['id']}", headers=headers, json={**PROVEEDOR_PRUEBA, "producto_ids": [otro["id"]]}
    )
    assert [p["sku"] for p in resp.json()["productos"]] == ["CLA-1"]

    # Un producto de OTRO tenant no se puede asociar.
    tenant_b = tenant_factory()
    headers_b = auth_headers_factory(usuario_factory(tenant_b))
    ajeno = client.post("/api/v1/compras/productos", headers=headers_b, json={"nombre": "Ajeno", "sku": "AJ-1", "precio": "1"}).json()
    resp = client.put(
        f"/api/v1/compras/proveedores/{proveedor['id']}", headers=headers, json={**PROVEEDOR_PRUEBA, "producto_ids": [ajeno["id"]]}
    )
    assert resp.status_code == 404
