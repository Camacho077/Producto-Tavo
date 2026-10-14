"""
Arranque del backend DENTRO de Docker (infra/docker-compose.yml):

    1. Espera a que Postgres acepte conexiones (hasta ESPERA_MAXIMA s).
    2. Corre `alembic upgrade head`.
    3. Recién entonces arranca uvicorn en Settings.PORT.

Si algo falla, el contenedor termina con un mensaje en español que dice la
causa y el arreglo (lo muestran `docker compose logs backend`, el setup y
automatizaciones/dev/diagnostico.ps1), en vez de quedar "Up" sin responder o
de morir con un traceback en inglés. Pasó el 2026-10-13: el backend de un
compañero no arrancaba y desde afuera solo se veía ERR_CONNECTION_REFUSED.

La configuración (.env) se valida al importar app.core.config: si falta
SECRET_KEY o DATABASE_URL, ese módulo ya sale con su mensaje en español.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import NoReturn
from urllib.parse import urlparse

ESPERA_MAXIMA = int(os.environ.get("ESPERA_BASE_SEGUNDOS", "60"))
BACKEND = Path(__file__).resolve().parents[1]


def _linea(texto: str) -> None:
    print(texto, flush=True)


def falla(causa: str, arreglo: str) -> NoReturn:
    _linea("")
    _linea(f"✘ El backend no arrancó: {causa}")
    _linea(f"  → {arreglo}")
    _linea("")
    raise SystemExit(1)


def esperar_base(url: str, espera_maxima: int = ESPERA_MAXIMA, pausa: float = 1.0) -> None:
    """Reintenta conectar hasta que Postgres responda. Credenciales malas o
    una base inexistente no se arreglan esperando: falla de una vez."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import OperationalError

    destino = urlparse(url)
    donde = f"{destino.hostname}:{destino.port or 5432}"
    inicio = time.monotonic()
    ultimo = ""
    intento = 0
    while True:
        intento += 1
        engine = create_engine(url, connect_args={"connect_timeout": 3})
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            _linea(f"✔ Postgres responde en {donde}")
            return
        except OperationalError as exc:
            ultimo = str(exc).splitlines()[0]
            if "password authentication failed" in ultimo:
                falla(f"Postgres ({donde}) rechazó usuario o clave de DATABASE_URL.",
                      "Revisa DATABASE_URL en backend/.env y POSTGRES_USER/POSTGRES_PASSWORD en infra/docker-compose.yml.")
            if "does not exist" in ultimo and "database" in ultimo:
                falla(f"la base '{destino.path.lstrip('/')}' no existe en {donde}.",
                      "Borra el volumen de la base y vuelve a correr el setup: docker compose -f infra/docker-compose.yml down -v")
        finally:
            engine.dispose()
        if time.monotonic() - inicio >= espera_maxima:
            falla(f"Postgres no respondió en {donde} después de {espera_maxima} s ({ultimo}).",
                  "Revisa el contenedor de la base: docker compose -f infra/docker-compose.yml ps db  y  logs db")
        if intento == 1:
            _linea(f"… esperando a Postgres en {donde}")
        time.sleep(pausa)


def migrar() -> None:
    _linea("… aplicando migraciones (alembic upgrade head)")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND)
    if r.returncode != 0:
        falla("la migración de la base falló (el detalle está justo arriba).",
              "Corrige el error de la migración; si la base de desarrollo quedó a medias, recréala con: "
              "docker compose -f infra/docker-compose.yml down -v  y vuelve a correr el setup.")
    _linea("✔ Esquema al día")


def main() -> None:
    from app.core.config import settings  # valida el .env con su mensaje propio

    esperar_base(settings.DATABASE_URL)
    migrar()
    _linea(f"✔ Arrancando el backend en el puerto {settings.PORT}")
    os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(settings.PORT)])


if __name__ == "__main__":
    main()
