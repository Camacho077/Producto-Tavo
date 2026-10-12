"""
Regresión para un bug real: las respuestas de error NO traían
Access-Control-Allow-Origin (el navegador reportaba "CORS Failed" en vez
del error real). La causa: un handler registrado para la clase `Exception`
(catch-all de 500) queda fuera de CORSMiddleware por diseño de Starlette
—ver la nota en app/core/error_handlers.py—, sin importar el orden de
`add_middleware`. Se corrigió moviendo ese catch-all a un middleware ASGI
propio (CatchAllExceptionsMiddleware) agregado antes que CORSMiddleware.

Estos tests golpean la app real (vía TestClient, que atraviesa todo el
stack ASGI incluido CORSMiddleware) forzando cada tipo de error y
verifican explícitamente el header, para que este bug no pueda volver a
colarse en silencio.
"""
import pytest

from app.core.config import settings
from app.core.deps import get_current_usuario
from app.main import app

ORIGIN = "http://localhost:5175"


def test_error_401_trae_header_cors(client):
    resp = client.get("/api/v1/seguridad/usuarios", headers={"Origin": ORIGIN})

    assert resp.status_code == 401
    assert resp.headers.get("access-control-allow-origin") == ORIGIN


def test_error_422_trae_header_cors(client):
    resp = client.post(
        "/api/v1/seguridad/login",
        headers={"Origin": ORIGIN},
        json={"email": "no-es-un-email", "password": ""},
    )

    assert resp.status_code == 422
    assert resp.headers.get("access-control-allow-origin") == ORIGIN


ORIGIN_PUERTO_DINAMICO = "http://localhost:5176"


def test_preflight_desde_puerto_dinamico_responde_200_con_header(client):
    """Vite puede arrancar en 5176/5177/... si el 5175 está ocupado. Ese
    origen NO está en CORS_ORIGINS: debe pasar igual por el regex de dev.
    Cuando esto falla, el preflight responde 400 sin header y el navegador
    lo reporta como 'CORS Failed'."""
    resp = client.options(
        "/api/v1/seguridad/registro",
        headers={
            "Origin": ORIGIN_PUERTO_DINAMICO,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ORIGIN_PUERTO_DINAMICO


def test_error_desde_puerto_dinamico_trae_header_cors(client):
    """El caso que se rompía: error (401) pedido desde un puerto que no está
    en CORS_ORIGINS. Sin el header, el navegador oculta el error real."""
    resp = client.get("/api/v1/seguridad/usuarios", headers={"Origin": ORIGIN_PUERTO_DINAMICO})

    assert resp.status_code == 401
    assert resp.headers.get("access-control-allow-origin") == ORIGIN_PUERTO_DINAMICO


def test_registro_con_email_duplicado_desde_puerto_dinamico_trae_header_cors(
    client, tenant_factory, usuario_factory
):
    """Endpoint y error exactos del reporte: POST /seguridad/registro con un
    correo ya registrado, desde un origen con puerto dinámico."""
    tenant = tenant_factory()
    usuario_factory(tenant, email="ya-registrado@negocio.com")

    resp = client.post(
        "/api/v1/seguridad/registro",
        headers={"Origin": ORIGIN_PUERTO_DINAMICO},
        json={
            "nombre_empresa": "Empresa Nueva",
            "email": "ya-registrado@negocio.com",
            "password": "clave-segura-123",
            "acepta_condiciones": True,
        },
    )

    assert resp.status_code == 409
    assert resp.headers.get("access-control-allow-origin") == ORIGIN_PUERTO_DINAMICO


def test_error_500_no_controlado_trae_header_cors(client):
    def _dependencia_que_falla():
        raise RuntimeError("boom - forzado por el test para simular un error no controlado")

    # Toda ruta de negocio pasa por get_current_usuario (debajo de la
    # verificación de permisos): forzar su fallo simula un error no controlado.
    app.dependency_overrides[get_current_usuario] = _dependencia_que_falla
    try:
        resp = client.get("/api/v1/compras/categorias", headers={"Origin": ORIGIN})
    finally:
        app.dependency_overrides.pop(get_current_usuario, None)

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Error interno del servidor"}
    assert resp.headers.get("access-control-allow-origin") == ORIGIN


# ---------------------------------------------------------------------------
# Los dos errores exactos que el usuario ve en el navegador al autenticarse:
# credenciales malas en /login y correo duplicado en /registro, ambos desde
# el origen fijo del frontend (5175). Si CORS se elimina o se reordena en
# app/main.py, estos tests fallan.
# ---------------------------------------------------------------------------
def test_login_con_credenciales_malas_trae_header_cors(client, tenant_factory, usuario_factory):
    tenant = tenant_factory()
    usuario_factory(tenant, email="dueno@negocio.com", password="clave-correcta-123")

    resp = client.post(
        "/api/v1/seguridad/login",
        headers={"Origin": ORIGIN},
        json={"email": "dueno@negocio.com", "password": "clave-equivocada"},
    )

    assert resp.status_code == 401
    assert resp.json() == {"detail": "Credenciales inválidas"}
    assert resp.headers.get("access-control-allow-origin") == ORIGIN


def test_registro_con_email_duplicado_trae_header_cors(client, tenant_factory, usuario_factory):
    tenant = tenant_factory()
    usuario_factory(tenant, email="ya-registrado@negocio.com")

    resp = client.post(
        "/api/v1/seguridad/registro",
        headers={"Origin": ORIGIN},
        json={
            "nombre_empresa": "Empresa Nueva",
            "email": "ya-registrado@negocio.com",
            "password": "clave-segura-123",
            "acepta_condiciones": True,
        },
    )

    assert resp.status_code == 409
    assert resp.headers.get("access-control-allow-origin") == ORIGIN


def test_preflight_registro_desde_5175_responde_200_con_header(client):
    """El OPTIONS que el navegador manda antes del POST de registro."""
    resp = client.options(
        "/api/v1/seguridad/registro",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


# ---------------------------------------------------------------------------
# Verificación ESTRUCTURAL de app/main.py (no necesita base de datos): falla
# si alguien borra configure_cors()/CatchAllExceptionsMiddleware de main.py
# o invierte su orden, aunque los demás tests no se ejecuten por falta de
# Postgres. Es la protección directa contra "limpiar" ese bloque.
# ---------------------------------------------------------------------------
def test_main_registra_cors_envolviendo_al_catch_all():
    from fastapi.middleware.cors import CORSMiddleware

    from app.core.error_handlers import CatchAllExceptionsMiddleware

    clases = [m.cls for m in app.user_middleware]

    assert CORSMiddleware in clases, "app/main.py ya no registra CORSMiddleware (configure_cors)"
    assert CatchAllExceptionsMiddleware in clases, (
        "app/main.py ya no registra CatchAllExceptionsMiddleware"
    )
    # app.user_middleware lista de MÁS externo a MÁS interno: CORS debe ir
    # primero (envolver al catch-all) para que los 500 traigan el header.
    assert clases.index(CORSMiddleware) < clases.index(CatchAllExceptionsMiddleware), (
        "CORSMiddleware debe agregarse DESPUÉS de CatchAllExceptionsMiddleware "
        "(add_middleware invierte el orden)"
    )


def test_main_configura_cors_con_credenciales_y_regex_de_dev():
    from fastapi.middleware.cors import CORSMiddleware

    from app.core.cors import DEV_ORIGIN_REGEX

    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)
    kwargs = cors.kwargs

    assert kwargs["allow_credentials"] is True
    assert kwargs["allow_methods"] == ["*"]
    assert kwargs["allow_headers"] == ["*"]
    assert kwargs["allow_origins"] == settings.cors_origins
    if settings.ENV == "development":
        assert kwargs.get("allow_origin_regex") == DEV_ORIGIN_REGEX
    else:
        assert "allow_origin_regex" not in kwargs


@pytest.mark.parametrize("origen", ["http://[::1]:5175", "http://192.168.1.50:5175", "http://localhost"])
def test_errores_desde_origenes_locales_nuevos_traen_header_cors(client, origen):
    """Preflight del login y respuestas de ERROR (401 y 422) desde IPv6,
    red local y localhost sin puerto: todas con Access-Control-Allow-Origin;
    sin él, el navegador esconde la causa real detrás de un "CORS"."""
    preflight = client.options(
        "/api/v1/seguridad/login",
        headers={
            "Origin": origen,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers.get("access-control-allow-origin") == origen

    no_autorizado = client.get("/api/v1/seguridad/usuarios", headers={"Origin": origen})
    assert no_autorizado.status_code == 401
    assert no_autorizado.headers.get("access-control-allow-origin") == origen

    invalido = client.post("/api/v1/seguridad/login", json={"email": "no-es-correo"}, headers={"Origin": origen})
    assert invalido.status_code == 422
    assert invalido.headers.get("access-control-allow-origin") == origen
