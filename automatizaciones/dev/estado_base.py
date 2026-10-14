"""
Estado de la base de datos de desarrollo, en una línea JSON. Lo usan
automatizaciones/setup.ps1, setup.sh y dev/diagnostico.ps1:

    cd backend
    venv\\Scripts\\python ..\\automatizaciones\\dev\\estado_base.py

Responde: si Postgres contesta, la migración aplicada y la última del código,
cuántos usuarios hay (0 = base vacía: el setup carga la demo) y cuáles de las
cuentas demo existen. Nunca escribe nada.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
BACKEND = Path(__file__).resolve().parents[2] / "backend"
sys.path.append(str(BACKEND))

CUENTAS_DEMO = ["admin@dondetavo.demo", "caja@dondetavo.demo", "mesero@dondetavo.demo", "cocina@dondetavo.demo"]


def main() -> int:
    from app.core.config import settings  # si falta el .env, aquí sale el mensaje claro

    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine, inspect, text

    estado = {"env": settings.ENV, "conecta": False, "migracion": None, "ultima": None, "al_dia": False,
              "usuarios": None, "cuentas_demo": []}
    estado["ultima"] = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini"))).get_current_head()
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            estado["conecta"] = True
            tablas = set(inspect(conn).get_table_names())
            if "alembic_version" in tablas:
                estado["migracion"] = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            estado["al_dia"] = estado["migracion"] == estado["ultima"]
            if "usuarios" in tablas:
                estado["usuarios"] = conn.execute(text("SELECT count(*) FROM usuarios")).scalar()
                filas = conn.execute(text("SELECT email FROM usuarios WHERE email = ANY(:c)"), {"c": CUENTAS_DEMO}).scalars()
                estado["cuentas_demo"] = sorted(filas)
    except Exception as exc:  # noqa: BLE001 — se informa, no se cae
        estado["error"] = str(exc).splitlines()[0][:200]
    finally:
        engine.dispose()
    print(json.dumps(estado, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
