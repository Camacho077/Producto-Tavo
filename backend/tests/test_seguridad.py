def test_login_ok(client, tenant_factory, usuario_factory):
    tenant = tenant_factory()
    usuario_factory(tenant, email="admin@empresa.com", password="clave-segura-123")

    resp = client.post(
        "/api/v1/seguridad/login",
        json={"email": "admin@empresa.com", "password": "clave-segura-123"},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_sin_recordarme_da_sesion_corta(client, tenant_factory, usuario_factory):
    from datetime import datetime, timedelta, timezone

    from app.core.security import decode_access_token

    tenant = tenant_factory()
    usuario_factory(tenant, email="corta@empresa.com", password="clave-segura-123")

    resp = client.post(
        "/api/v1/seguridad/login",
        json={"email": "corta@empresa.com", "password": "clave-segura-123"},
    )

    assert resp.status_code == 200
    exp = datetime.fromtimestamp(decode_access_token(resp.json()["access_token"])["exp"], timezone.utc)
    restante = exp - datetime.now(timezone.utc)
    # 8 horas por defecto: claramente menos de un día
    assert timedelta(hours=7) < restante < timedelta(hours=9)


def test_login_con_recordarme_da_sesion_larga(client, tenant_factory, usuario_factory):
    from datetime import datetime, timedelta, timezone

    from app.core.security import decode_access_token

    tenant = tenant_factory()
    usuario_factory(tenant, email="larga@empresa.com", password="clave-segura-123")

    resp = client.post(
        "/api/v1/seguridad/login",
        json={"email": "larga@empresa.com", "password": "clave-segura-123", "recordarme": True},
    )

    assert resp.status_code == 200
    exp = datetime.fromtimestamp(decode_access_token(resp.json()["access_token"])["exp"], timezone.utc)
    restante = exp - datetime.now(timezone.utc)
    assert timedelta(days=29) < restante < timedelta(days=31)


def test_login_credenciales_invalidas(client, tenant_factory, usuario_factory):
    tenant = tenant_factory()
    usuario_factory(tenant, email="admin@empresa.com", password="clave-segura-123")

    resp = client.post(
        "/api/v1/seguridad/login",
        json={"email": "admin@empresa.com", "password": "clave-incorrecta"},
    )

    assert resp.status_code == 401


def test_login_usuario_inactivo(client, tenant_factory, usuario_factory):
    tenant = tenant_factory()
    usuario_factory(tenant, email="inactivo@empresa.com", password="clave-segura-123", activo=False)

    resp = client.post(
        "/api/v1/seguridad/login",
        json={"email": "inactivo@empresa.com", "password": "clave-segura-123"},
    )

    assert resp.status_code == 403


def test_login_validacion_email_invalido(client):
    resp = client.post(
        "/api/v1/seguridad/login",
        json={"email": "no-es-un-email", "password": "clave-segura-123"},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Los datos enviados no son válidos"


def test_listar_usuarios_sin_token(client):
    resp = client.get("/api/v1/seguridad/usuarios")
    assert resp.status_code == 401


def test_listar_usuarios_aisla_por_tenant(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    usuario_a = usuario_factory(tenant_a, email="a@empresa.com")
    usuario_factory(tenant_b, email="b@empresa.com")

    resp = client.get("/api/v1/seguridad/usuarios", headers=auth_headers_factory(usuario_a))

    assert resp.status_code == 200
    emails = [u["email"] for u in resp.json()["items"]]
    assert emails == ["a@empresa.com"]


def test_crear_usuario_ok(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, email="admin@empresa.com")
    rol = rol_factory(tenant, nombre="Cajero")

    resp = client.post(
        "/api/v1/seguridad/usuarios",
        headers=auth_headers_factory(admin),
        json={
            "nombre_completo": "Nuevo Empleado",
            "email": "empleado@empresa.com",
            "password": "clave-segura-123",
            "rol_id": str(rol.id),
        },
    )

    assert resp.status_code == 201
    assert resp.json()["email"] == "empleado@empresa.com"


def test_crear_usuario_con_rol_de_otro_tenant_falla(
    client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory
):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    admin_a = usuario_factory(tenant_a, email="admin@empresa.com")
    rol_de_b = rol_factory(tenant_b, nombre="Cajero")

    resp = client.post(
        "/api/v1/seguridad/usuarios",
        headers=auth_headers_factory(admin_a),
        json={
            "nombre_completo": "Nuevo Empleado",
            "email": "empleado2@empresa.com",
            "password": "clave-segura-123",
            "rol_id": str(rol_de_b.id),
        },
    )

    assert resp.status_code == 404


def test_crear_usuario_email_duplicado(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, email="admin@empresa.com")
    rol = rol_factory(tenant)

    resp = client.post(
        "/api/v1/seguridad/usuarios",
        headers=auth_headers_factory(admin),
        json={
            "nombre_completo": "Otro",
            "email": "admin@empresa.com",
            "password": "clave-segura-123",
            "rol_id": str(rol.id),
        },
    )

    assert resp.status_code == 409


def test_crear_usuario_password_muy_corta(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, email="admin@empresa.com")
    rol = rol_factory(tenant)

    resp = client.post(
        "/api/v1/seguridad/usuarios",
        headers=auth_headers_factory(admin),
        json={
            "nombre_completo": "Otro",
            "email": "otro@empresa.com",
            "password": "123",
            "rol_id": str(rol.id),
        },
    )

    assert resp.status_code == 422


def test_crear_rol_duplicado_en_mismo_tenant(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, email="admin@empresa.com")
    rol_factory(tenant, nombre="Cajero")

    resp = client.post(
        "/api/v1/seguridad/roles",
        headers=auth_headers_factory(admin),
        json={"nombre": "Cajero"},
    )

    assert resp.status_code == 409


def test_me_devuelve_usuario_y_tenant(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory(nombre_empresa="Mi Empresa")
    usuario = usuario_factory(tenant, email="admin@empresa.com")

    resp = client.get("/api/v1/seguridad/me", headers=auth_headers_factory(usuario))

    assert resp.status_code == 200
    body = resp.json()
    assert body["usuario"]["email"] == "admin@empresa.com"
    assert body["tenant"]["nombre_empresa"] == "Mi Empresa"


def test_token_invalido_rechazado(client):
    resp = client.get("/api/v1/seguridad/usuarios", headers={"Authorization": "Bearer token-invalido"})
    assert resp.status_code == 401


def test_rol_con_permisos_y_bloqueo_por_usuarios(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)

    resp = client.post(
        "/api/v1/seguridad/roles",
        headers=headers,
        json={"nombre": "Cajero", "permisos": {"ventas": ["ver", "crear"], "compras": ["ver"]}},
    )
    assert resp.status_code == 201
    rol = resp.json()
    assert rol["permisos"] == {"ventas": ["ver", "crear"], "compras": ["ver"]}

    # Módulo desconocido -> 422 con mensaje en español.
    resp = client.post(
        "/api/v1/seguridad/roles", headers=headers, json={"nombre": "Raro", "permisos": {"nomina": ["ver"]}}
    )
    assert resp.status_code == 422

    # Un usuario asignado bloquea la eliminación del rol.
    client.post(
        "/api/v1/seguridad/usuarios",
        headers=headers,
        json={"nombre_completo": "Cajera Uno", "email": "caja1@empresa.com", "password": "clave-segura-123", "rol_id": rol["id"]},
    )
    resp = client.delete(f"/api/v1/seguridad/roles/{rol['id']}", headers=headers)
    assert resp.status_code == 409

    # Editar permisos.
    resp = client.put(f"/api/v1/seguridad/roles/{rol['id']}", headers=headers, json={"permisos": {"ventas": ["ver"]}})
    assert resp.status_code == 200
    assert resp.json()["permisos"] == {"ventas": ["ver"]}
    assert resp.json()["usuarios_count"] == 1


def test_usuario_editar_estado_y_no_autodesactivarse(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)
    otro = usuario_factory(tenant, email="otro@empresa.com")

    resp = client.put(
        f"/api/v1/seguridad/usuarios/{otro.id}", headers=headers, json={"nombre_completo": "Otro Nombre"}
    )
    assert resp.status_code == 200
    assert resp.json()["nombre_completo"] == "Otro Nombre"

    resp = client.patch(f"/api/v1/seguridad/usuarios/{otro.id}/estado", headers=headers, json={"activo": False})
    assert resp.status_code == 200
    assert resp.json()["activo"] is False

    resp = client.patch(f"/api/v1/seguridad/usuarios/{admin.id}/estado", headers=headers, json={"activo": False})
    assert resp.status_code == 409

    resp = client.delete(f"/api/v1/seguridad/usuarios/{admin.id}", headers=headers)
    assert resp.status_code == 409

    resp = client.delete(f"/api/v1/seguridad/usuarios/{otro.id}", headers=headers)
    assert resp.status_code == 204
