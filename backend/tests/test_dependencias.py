"""Las dependencias de Python van con versión fija: una instalación limpia
debe quedar igual a la probada. Sin esto, un clon nuevo recibió SQLAlchemy
2.1 (driver por defecto psycopg 3, no instalado) y el backend no arrancaba."""
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def test_todas_las_dependencias_tienen_version_fija():
    sueltas = []
    for archivo in ("requirements.txt", "requirements-dev.txt"):
        for linea in (BACKEND / archivo).read_text(encoding="utf-8").splitlines():
            linea = linea.split("#", 1)[0].strip()
            if not linea or linea.startswith("-r"):
                continue
            if not re.match(r"^[A-Za-z0-9_.\-\[\],]+==[0-9][\w.]*$", linea):
                sueltas.append(f"{archivo}: {linea}")
    assert not sueltas, f"Dependencias sin versión fija (==): {sueltas}"
