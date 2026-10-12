from tests.conftest import crear_producto, dar_stock, stock_de


def _crear_producto(client, headers, sku="SKU-1", precio="1000", stock_inicial=0):
    """Plato cuya receta gasta una unidad de su insumo base (conftest)."""
    producto = crear_producto(client, headers, "Producto", precio, sku=sku)
    if stock_inicial:
        dar_stock(client, headers, producto["id"], stock_inicial)
    return producto


def test_listar_ventas_sin_token(client):
    resp = client.get("/api/v1/ventas/ventas")
    assert resp.status_code == 401


def test_crear_venta_queda_pendiente_y_no_toca_stock(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers, stock_inicial=10)

    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 3, "precio_unitario": "1000"}],
        },
    )

    assert resp.status_code == 201
    venta = resp.json()
    assert venta["estado"] == "pendiente"
    assert venta["total"] == "3000.00"

    assert stock_de(client, headers, producto["id"]) == 10


def test_pedido_flujo_completo_con_linea_de_tiempo(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers, stock_inicial=10)
    resp = client.post(
        "/api/v1/ventas/pedidos",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "prioridad": "alta",
            "items": [{"producto_id": producto["id"], "cantidad": 2, "precio_unitario": "1000"}],
        },
    )
    assert resp.status_code == 201
    pedido = resp.json()
    assert pedido["estado"] == "pendiente"
    assert pedido["codigo"] == "PED-000001"
    assert pedido["total"] == "2000.00"
    assert [e["estado"] for e in pedido["eventos"]] == ["pendiente"]
    assert pedido["eventos"][0]["usuario_nombre"] == "Ana Admin"

    # Un pedido no toca stock.
    assert stock_de(client, headers, producto["id"]) == 10

    # Transición inválida: pendiente -> entregado no está permitida.
    resp = client.patch(
        f"/api/v1/ventas/pedidos/{pedido['id']}/estado", headers=headers, json={"estado": "entregado"}
    )
    assert resp.status_code == 409

    for estado in ("en_proceso", "listo", "entregado"):
        resp = client.patch(
            f"/api/v1/ventas/pedidos/{pedido['id']}/estado",
            headers=headers,
            json={"estado": estado, "nota": f"paso a {estado}"},
        )
        assert resp.status_code == 200, resp.json()
        assert resp.json()["estado"] == estado

    detalle = client.get(f"/api/v1/ventas/pedidos/{pedido['id']}", headers=headers).json()
    assert [e["estado"] for e in detalle["eventos"]] == ["pendiente", "en_proceso", "listo", "entregado"]

    listado = client.get("/api/v1/ventas/pedidos", headers=headers).json()
    assert listado["total"] == 1
    assert listado["items"][0]["id"] == pedido["id"]

    # Un pedido entregado ya no se edita.
    resp = client.put(f"/api/v1/ventas/pedidos/{pedido['id']}", headers=headers, json={"prioridad": "baja"})
    assert resp.status_code == 409


def test_pedidos_se_ordenan_por_prioridad(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)
    producto = _crear_producto(client, headers, stock_inicial=10)

    for prioridad in ("baja", "urgente", "media"):
        client.post(
            "/api/v1/ventas/pedidos",
            headers=headers,
            json={
                "cliente_nombre": f"Cliente {prioridad}",
                "fecha": "2026-01-01T10:00:00",
                "prioridad": prioridad,
                "items": [{"producto_id": producto["id"], "cantidad": 1, "precio_unitario": "1000"}],
            },
        )

    listado = client.get("/api/v1/ventas/pedidos", headers=headers).json()
    assert [p["prioridad"] for p in listado["items"]] == ["urgente", "media", "baja"]


def test_venta_registrada_con_confirmar_descuenta_stock(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)
    producto = _crear_producto(client, headers, stock_inicial=10)

    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto["id"], "cantidad": 3, "precio_unitario": "1000"}],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["estado"] == "completada"
    assert resp.json()["codigo"] == "VEN-000001"
    assert stock_de(client, headers, producto["id"]) == 7

    # Anular devuelve el stock.
    resp = client.post(f"/api/v1/ventas/ventas/{resp.json()['id']}/anular", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "anulada"
    assert stock_de(client, headers, producto["id"]) == 10


def test_pdf_de_venta(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)
    producto = _crear_producto(client, headers, stock_inicial=10)
    venta = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 1, "precio_unitario": "1000"}],
        },
    ).json()
    resp = client.get(f"/api/v1/ventas/ventas/{venta['id']}/pdf", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_confirmar_venta_descuenta_stock(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers, stock_inicial=10)
    venta = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 4, "precio_unitario": "1000"}],
        },
    ).json()

    resp = client.post(f"/api/v1/ventas/ventas/{venta['id']}/confirmar", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["estado"] == "completada"

    assert stock_de(client, headers, producto["id"]) == 6


def test_confirmar_venta_stock_insuficiente(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers, stock_inicial=2)
    venta = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 5, "precio_unitario": "1000"}],
        },
    ).json()

    resp = client.post(f"/api/v1/ventas/ventas/{venta['id']}/confirmar", headers=headers)

    assert resp.status_code == 409
    assert "quedan 2 unidades de Base de Producto y la venta necesita 5 unidades" in resp.json()["detail"]

    assert stock_de(client, headers, producto["id"]) == 2


def test_cancelar_venta_completada_falla(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers, stock_inicial=5)
    venta = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": 1, "precio_unitario": "1000"}],
        },
    ).json()
    client.post(f"/api/v1/ventas/ventas/{venta['id']}/confirmar", headers=headers)

    resp = client.post(f"/api/v1/ventas/ventas/{venta['id']}/cancelar", headers=headers)
    assert resp.status_code == 409


def test_venta_con_producto_de_otro_tenant_falla(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    admin_a = usuario_factory(tenant_a)
    admin_b = usuario_factory(tenant_b)

    producto_b = _crear_producto(client, auth_headers_factory(admin_b))

    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=auth_headers_factory(admin_a),
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto_b["id"], "cantidad": 1, "precio_unitario": "1000"}],
        },
    )

    assert resp.status_code == 404


def test_crear_venta_cantidad_invalida(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    producto = _crear_producto(client, headers, stock_inicial=5)

    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto["id"], "cantidad": -1, "precio_unitario": "1000"}],
        },
    )

    assert resp.status_code == 422


def test_ventas_aisladas_por_tenant(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    admin_a = usuario_factory(tenant_a)
    admin_b = usuario_factory(tenant_b)

    producto_a = _crear_producto(client, auth_headers_factory(admin_a), stock_inicial=5)
    client.post(
        "/api/v1/ventas/ventas",
        headers=auth_headers_factory(admin_a),
        json={
            "cliente_nombre": "Cliente A",
            "fecha": "2026-01-01T10:00:00",
            "items": [{"producto_id": producto_a["id"], "cantidad": 1, "precio_unitario": "1000"}],
        },
    )

    resp = client.get("/api/v1/ventas/ventas", headers=auth_headers_factory(admin_b))
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_sobreventa_al_registrar_no_cita_un_numero_que_nunca_existio(client, tenant_factory, usuario_factory, auth_headers_factory):
    """Registrar y completar de una vez sin stock suficiente: 409 con la causa,
    y el mensaje NO cita el número de venta (la transacción se revierte y ese
    número nunca llega a existir; antes decía "VEN-000002" y el usuario lo
    buscaba sin encontrarlo). No queda ninguna venta ni se mueve el stock."""
    headers = auth_headers_factory(usuario_factory(tenant_factory()))
    producto = _crear_producto(client, headers, sku="SOB-1", stock_inicial=17)
    resp = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": "Cliente Final",
            "fecha": "2026-01-01T10:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto["id"], "cantidad": 1000, "precio_unitario": "1000"}],
        },
    )
    assert resp.status_code == 409
    detalle = resp.json()["detail"]
    assert detalle == "No se pudo registrar la venta: quedan 17 unidades de Base de Producto y la venta necesita 1000 unidades."
    assert "VEN-" not in detalle
    assert client.get("/api/v1/ventas/ventas", headers=headers).json()["total"] == 0
    assert stock_de(client, headers, producto["id"]) == 17
