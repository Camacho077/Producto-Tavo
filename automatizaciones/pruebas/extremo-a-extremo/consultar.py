"""Consulta la base de datos REAL de desarrollo y devuelve JSON.
Uso: python consultar.py "<sql con :parametros>" '<json de parámetros>'"""
import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from sqlalchemy import create_engine, text  # noqa: E402

from app.core.config import settings  # noqa: E402


def _json(v):
    if isinstance(v, Decimal):
        return float(v)
    return str(v) if v is not None and not isinstance(v, (int, float, str, bool, list, dict)) else v


motor = create_engine(settings.DATABASE_URL)
with motor.connect() as c:
    filas = c.execute(text(sys.argv[1]), json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}).mappings().all()
print(json.dumps([{k: _json(v) for k, v in f.items()} for f in filas], ensure_ascii=False))
