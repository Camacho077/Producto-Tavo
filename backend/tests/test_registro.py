from app.core.config import settings
from app.db.models import Tenant
from app.modules.seguridad.models import Usuario


def test_registro_ok_crea_tenant_rol_usuario_y_devuelve_token(client, db_session):
    resp = client.post(
        "/api/v1/seguridad/registro",
        json={
            "nombre_empresa": "Mi Negocio Nuevo",
            "email": "fundador@minegocio.com",
            "password": "clave-segura-123",
            "acepta_condiciones": True,
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    usuario = db_session.query(Usuario).filter(Usuario.email == "fundador@minegocio.com").first()
    assert usuario is not None
    assert usuario.activo is True

    tenant = db_session.query(Tenant).filter(Tenant.id == usuario.tenant_id).first()
    assert tenant.nombre_empresa == "Mi Negocio Nuevo"
    # El plan inicial es configurable (settings.PLAN_POR_DEFECTO); hoy nace con
    # el plan completo para que el sidebar muestre todos los módulos.
    assert tenant.plan == settings.PLAN_POR_DEFECTO


def test_registro_permite_loguear_automaticamente_con_el_token(client):
    resp = client.post(
        "/api/v1/seguridad/registro",
        json={
            "nombre_empresa": "Otro Negocio",
            "email": "otro-fundador@negocio.com",
            "password": "clave-segura-123",
            "acepta_condiciones": True,
        },
    )
    token = resp.json()["access_token"]

    me = client.get("/api/v1/seguridad/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200
    assert me.json()["usuario"]["email"] == "otro-fundador@negocio.com"
    assert me.json()["tenant"]["nombre_empresa"] == "Otro Negocio"


def test_registro_email_duplicado_da_409_y_no_deja_nada_a_medias(client, db_session):
    client.post(
        "/api/v1/seguridad/registro",
        json={
            "nombre_empresa": "Negocio Uno",
            "email": "duplicado@negocio.com",
            "password": "clave-segura-123",
            "acepta_condiciones": True,
        },
    )
    tenants_antes = db_session.query(Tenant).count()

    resp = client.post(
        "/api/v1/seguridad/registro",
        json={
            "nombre_empresa": "Negocio Dos (no debería crearse)",
            "email": "duplicado@negocio.com",
            "password": "otra-clave-123",
            "acepta_condiciones": True,
        },
    )

    assert resp.status_code == 409
    assert "Ya existe una cuenta" in resp.json()["detail"]

    tenants_despues = db_session.query(Tenant).count()
    assert tenants_despues == tenants_antes, "no debe quedar un Tenant huérfano si el registro falla"
    assert (
        db_session.query(Tenant).filter(Tenant.nombre_empresa == "Negocio Dos (no debería crearse)").first() is None
    )


def test_registro_email_invalido_da_422(client):
    resp = client.post(
        "/api/v1/seguridad/registro",
        json={"nombre_empresa": "Negocio X", "email": "no-es-un-email", "password": "clave-segura-123", "acepta_condiciones": True},
    )

    assert resp.status_code == 422


def test_registro_password_muy_corta_da_422(client):
    resp = client.post(
        "/api/v1/seguridad/registro",
        json={"nombre_empresa": "Negocio X", "email": "valido@negocio.com", "password": "123", "acepta_condiciones": True},
    )

    assert resp.status_code == 422


def test_registro_nombre_empresa_vacio_da_422(client):
    resp = client.post(
        "/api/v1/seguridad/registro",
        json={"nombre_empresa": "", "email": "valido2@negocio.com", "password": "clave-segura-123", "acepta_condiciones": True},
    )

    assert resp.status_code == 422
