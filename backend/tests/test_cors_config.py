"""
Pruebas aisladas de app/core/cors.py — no dependen de la app real ni de la
base de datos, arman una mini app FastAPI de prueba para cada caso.

Cubre el bug reportado: Vite cambia de puerto (5173 -> 5174 -> ...) cuando
el anterior sigue ocupado, y perseguir el puerto exacto en CORS_ORIGINS a
mano es frágil. En desarrollo se acepta cualquier puerto en
localhost/127.0.0.1; en producción NO, ahí manda solo la lista explícita.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.cors import configure_cors

# Producción exige una SECRET_KEY de 32+ caracteres (ver config._validar_entorno).
CLAVE_PRODUCCION = "clave-de-prueba-solo-para-tests-0123456789"

def _app_de_prueba(settings: Settings) -> TestClient:
    app = FastAPI()
    configure_cors(app, settings)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


def test_dev_acepta_cualquier_puerto_de_localhost():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    for puerto in (5173, 5174, 5999, 3000):
        resp = client.get("/ping", headers={"Origin": f"http://localhost:{puerto}"})
        assert resp.headers.get("access-control-allow-origin") == f"http://localhost:{puerto}", (
            f"puerto {puerto} debería estar permitido en desarrollo"
        )


def test_dev_acepta_cualquier_puerto_de_127_0_0_1():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    resp = client.get("/ping", headers={"Origin": "http://127.0.0.1:5174"})
    assert resp.headers.get("access-control-allow-origin") == "http://127.0.0.1:5174"


def test_dev_no_acepta_un_origen_externo_arbitrario():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    resp = client.get("/ping", headers={"Origin": "http://sitio-malicioso.com"})
    assert "access-control-allow-origin" not in resp.headers


def test_produccion_solo_acepta_la_lista_explicita_sin_regex():
    settings = Settings(ENV="production", SECRET_KEY=CLAVE_PRODUCCION, CORS_ORIGINS='["https://app.jscompany.co"]')
    client = _app_de_prueba(settings)

    resp_permitido = client.get("/ping", headers={"Origin": "https://app.jscompany.co"})
    assert resp_permitido.headers.get("access-control-allow-origin") == "https://app.jscompany.co"

    # En producción, cualquier puerto de localhost NO debe colarse por el regex de dev.
    resp_localhost = client.get("/ping", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in resp_localhost.headers


# ---------------------------------------------------------------------------
# Túneles para compartir la demo por internet (localtunnel, ngrok, Cloudflare).
# Si se borra ese tramo del regex en app/core/cors.py, estos tests fallan.
# ---------------------------------------------------------------------------
ORIGENES_TUNEL = (
    "https://silly-cats-jump.loca.lt",
    "https://a1b2-190-25-3-4.ngrok-free.app",
    "https://quiet-river-demo.trycloudflare.com",
)


def test_dev_acepta_dominios_de_tunel_con_cualquier_subdominio():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    for origen in ORIGENES_TUNEL:
        resp = client.get("/ping", headers={"Origin": origen})
        assert resp.headers.get("access-control-allow-origin") == origen, f"{origen} debería pasar en desarrollo"


def test_dev_preflight_desde_tunel_responde_200_con_header():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)
    origen = ORIGENES_TUNEL[0]

    resp = client.options(
        "/ping",
        headers={"Origin": origen, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,bypass-tunnel-reminder"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origen


def test_dev_no_acepta_tunel_por_http_ni_dominios_parecidos():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    for origen in ("http://demo.loca.lt", "https://loca.lt.malicioso.com", "https://demo.ngrok-free.app.evil.io"):
        resp = client.get("/ping", headers={"Origin": origen})
        assert "access-control-allow-origin" not in resp.headers, f"{origen} NO debería pasar"


def test_produccion_no_acepta_dominios_de_tunel():
    settings = Settings(ENV="production", SECRET_KEY=CLAVE_PRODUCCION, CORS_ORIGINS='["https://app.jscompany.co"]')
    client = _app_de_prueba(settings)

    for origen in ORIGENES_TUNEL:
        resp = client.get("/ping", headers={"Origin": origen})
        assert "access-control-allow-origin" not in resp.headers, f"{origen} NO debería pasar en producción"


def test_dev_acepta_ipv6_sin_puerto_y_red_local():
    """El caso del compañero que clonó el repo (2026-09-27): abrir el
    frontend por [::1], sin puerto o por la URL "Network" que imprime Vite
    (server.host: true) daba 400 "Disallowed CORS origin" en el OPTIONS."""
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    for origen in (
        "http://[::1]:5173",
        "http://localhost",
        "http://127.0.0.1",
        "http://192.168.1.50:5173",
        "http://10.0.0.7:5173",
        "http://172.20.4.2:5180",
    ):
        resp = client.options(
            "/ping",
            headers={
                "Origin": origen,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200, f"{origen}: preflight respondió {resp.status_code} {resp.text}"
        assert resp.headers.get("access-control-allow-origin") == origen


def test_dev_no_acepta_ips_publicas_ni_hosts_disfrazados():
    settings = Settings(ENV="development", CORS_ORIGINS='["http://localhost:5173"]')
    client = _app_de_prueba(settings)

    for origen in (
        "http://172.32.1.1:5173",
        "http://8.8.8.8",
        "http://localhost.evil.com",
        "http://192.168.1.50.evil.com",
        "https://localhost:5173",
    ):
        resp = client.get("/ping", headers={"Origin": origen})
        assert "access-control-allow-origin" not in resp.headers, f"{origen} NO debería pasar"


def test_produccion_no_acepta_origenes_locales_ni_de_red():
    settings = Settings(ENV="production", SECRET_KEY=CLAVE_PRODUCCION, CORS_ORIGINS='["https://app.jscompany.co"]')
    client = _app_de_prueba(settings)

    for origen in ("http://localhost:5173", "http://[::1]:5173", "http://192.168.1.50:5173"):
        resp = client.get("/ping", headers={"Origin": origen})
        assert "access-control-allow-origin" not in resp.headers, f"{origen} NO debería pasar en producción"
