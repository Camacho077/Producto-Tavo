"""Los scripts que usa quien clona el repo deben correr en el PowerShell
que trae Windows (5.1). El 2026-09-27, en una copia limpia, start-backend.ps1
y start-frontend.ps1 no arrancaban: exigían `#requires -version 7`. Además
llevan BOM: sin él, PowerShell 5.1 lee las tildes y ✘ como basura."""
from pathlib import Path

import pytest

AUTOMATIZACIONES = Path(__file__).resolve().parents[2] / "automatizaciones"
SCRIPTS = ["setup.ps1", "dev/start-backend.ps1", "dev/start-frontend.ps1"]


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_de_arranque_corre_en_windows_powershell_5_1(script):
    contenido = (AUTOMATIZACIONES / script).read_bytes()
    assert contenido.startswith(b"\xef\xbb\xbf"), f"{script} debe guardarse en UTF-8 con BOM"
    assert b"#requires -version 7" not in contenido.lower(), f"{script} no puede exigir PowerShell 7"


def test_setup_sh_usa_finales_de_linea_unix():
    assert b"\r\n" not in (AUTOMATIZACIONES / "setup.sh").read_bytes()


def test_alta_tenant_no_impone_un_color_de_marca():
    """La paleta es monocromática (2026-10-01): una empresa creada con
    alta_tenant.py (y la demo de setup.ps1/setup.sh) nace en grises. Antes el
    valor por defecto era un azul y la demo se veía azul frente al cliente."""
    from pathlib import Path

    texto = (Path(__file__).resolve().parents[2] / "automatizaciones" / "deploy" / "alta_tenant.py").read_text(encoding="utf-8")
    assert '"--color-primario", default=None' in texto
    assert "#1E3A5F" not in texto.split("--color-primario", 1)[1].split("\n", 1)[0]
