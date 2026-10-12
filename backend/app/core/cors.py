# CONFIGURACIÓN CRÍTICA — NO ELIMINAR en limpiezas de código.
#  Sin esto el frontend no puede autenticarse (bloqueo CORS).
"""
Configuración de CORS separada de main.py para poder probarla de forma
aislada (ver tests/test_cors.py) sin levantar toda la app real.

En desarrollo, Vite puede saltar de puerto (5173, 5174, 5175...) si el
anterior sigue ocupado por un proceso viejo que no se cerró. Perseguir el
puerto exacto en CORS_ORIGINS cada vez que eso pasa es frágil y ya causó
el mismo bug reportado dos veces. En vez de eso, en desarrollo se acepta
cualquier origen local (localhost, 127.0.0.1, [::1] y la red privada) en
cualquier puerto vía allow_origin_regex, ADEMÁS de
la lista explícita de CORS_ORIGINS (por si se prueba desde otro origen,
ej. un dispositivo en la LAN). En producción NO se usa ningún regex —
manda únicamente la lista explícita de CORS_ORIGINS.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings

# CONFIGURACIÓN CRÍTICA — NO ELIMINAR en limpiezas de código.
# Solo en desarrollo (ENV=development) se aceptan, además de CORS_ORIGINS:
#  - la propia máquina en CUALQUIER puerto, o sin puerto: localhost,
#    127.0.0.1 y [::1] (localhost por IPv6). Así no importa en qué puerto
#    levante Vite en otra máquina;
#  - IPs de red privada (10.x, 172.16–31.x, 192.168.x) en cualquier puerto:
#    vite.config.js usa `server.host: true` y Vite imprime una URL "Network"
#    (http://192.168.x.x:5173). Quien la abría recibía 400 en el OPTIONS del
#    login ("Disallowed CORS origin") — fue el caso de un compañero que clonó
#    el repo (2026-09-27);
#  - los dominios de túnel con los que se comparte la demo por internet
#    (localtunnel, ngrok, Cloudflare quick tunnels), cualquier subdominio,
#    porque el túnel genera una URL nueva cada vez. Sin esto, el frontend
#    servido desde https://xxxx.loca.lt no puede iniciar sesión (bloqueo
#    CORS). Ver automatizaciones/demo/start-demo-tunel.ps1.
# En producción NO aplica ningún regex: manda solo CORS_ORIGINS.
# Protegido por tests/test_cors_config.py.
HOSTS_LOCALES = r"localhost|127\.0\.0\.1|\[::1\]"
REDES_PRIVADAS = r"10(\.\d{1,3}){3}|192\.168(\.\d{1,3}){2}|172\.(1[6-9]|2\d|3[01])(\.\d{1,3}){2}"
DOMINIOS_TUNEL = (r"loca\.lt", r"ngrok-free\.app", r"trycloudflare\.com")
DEV_ORIGIN_REGEX = (
    r"^(http://(" + HOSTS_LOCALES + "|" + REDES_PRIVADAS + r")(:\d{1,5})?"
    r"|https://[a-z0-9-]+(\.[a-z0-9-]+)*\.(" + "|".join(DOMINIOS_TUNEL) + r"))$"
)


def configure_cors(app: FastAPI, settings: Settings) -> None:
    kwargs = dict(
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if settings.ENV == "development":
        kwargs["allow_origin_regex"] = DEV_ORIGIN_REGEX

    app.add_middleware(CORSMiddleware, **kwargs)
