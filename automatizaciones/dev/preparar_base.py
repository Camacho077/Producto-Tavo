"""
Deja lista la base de datos de desarrollo antes de `alembic upgrade head`:
comprueba que Postgres responda y crea la base de DATABASE_URL si no existe.
Lo usan automatizaciones/setup.ps1 y setup.sh; se puede correr solo:

    cd backend
    venv\\Scripts\\python ..\\automatizaciones\\dev\\preparar_base.py

Sale con código 0 si la base queda disponible y 1 (con el arreglo concreto)
si no: Postgres apagado, credenciales malas o usuario sin permiso CREATEDB.
"""
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.stdout.reconfigure(encoding="utf-8")
sys.path.append(str(Path(__file__).resolve().parents[2] / "backend"))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.exc import OperationalError, ProgrammingError  # noqa: E402

from app.core.config import settings  # noqa: E402  (si falta el .env, aquí sale el mensaje claro)


def conectar(url: str, intentos: int = 15):
    """Postgres recién levantado en Docker tarda unos segundos en aceptar."""
    ultimo = None
    for _ in range(intentos):
        engine = create_engine(url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 3})
        try:
            conn = engine.connect()
            return engine, conn
        except OperationalError as exc:
            engine.dispose()
            ultimo = exc
            if "password authentication failed" in str(exc) or "does not exist" in str(exc):
                break
            time.sleep(1)
    raise ultimo


def main() -> int:
    destino = urlparse(settings.DATABASE_URL)
    base, usuario = destino.path.lstrip("/"), destino.username
    host = f"{destino.hostname}:{destino.port or 5432}"
    mantenimiento = settings.DATABASE_URL.rsplit("/", 1)[0] + "/postgres"

    try:
        engine, conn = conectar(mantenimiento)
    except OperationalError as exc:
        texto = str(exc)
        if "password authentication failed" in texto or ("role" in texto and "does not exist" in texto):
            print(f"✘ Postgres ({host}) rechazó al usuario '{usuario}'.")
            print("  → Revisa usuario/clave de DATABASE_URL en backend/.env, o crea el usuario:")
            print(f"    psql -U postgres -c \"CREATE ROLE {usuario} LOGIN PASSWORD '{destino.password}' CREATEDB;\"")
        else:
            print(f"✘ No hay un Postgres escuchando en {host}.")
            print("  → Con Docker Desktop:  docker compose -f infra/docker-compose.yml up -d db")
            print("  → Sin Docker: instala PostgreSQL 16 (https://www.postgresql.org/download/windows/) y créale")
            print(f"    el usuario '{usuario}' con la clave de DATABASE_URL y permiso CREATEDB.")
        return 1

    try:
        existe = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :b"), {"b": base}).first()
        if existe:
            print(f"✔ La base '{base}' ya existe en {host}")
            return 0
        try:
            conn.execute(text(f'CREATE DATABASE "{base}"'))
        except ProgrammingError:
            print(f"✘ La base '{base}' no existe y el usuario '{usuario}' no tiene permiso para crearla.")
            print(f"  → psql -U postgres -c \"CREATE DATABASE {base} OWNER {usuario};\"")
            return 1
        print(f"✔ Base '{base}' creada en {host}")
        return 0
    finally:
        conn.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
