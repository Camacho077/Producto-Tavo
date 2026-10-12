"""La guarda de app/core/arranque.py: el backend no arranca en un puerto que
no sea el suyo cuando lo lanza el CLI de uvicorn (2026-10-12, Producto Tavo
corre al mismo tiempo que el Producto JS en la misma máquina)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.arranque import exigir_puerto_del_proyecto, puerto_de_uvicorn

BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "argv,env,esperado",
    [
        (["uvicorn", "app.main:app"], {}, 8000),
        (["C:\\venv\\Scripts\\uvicorn.exe", "app.main:app", "--reload"], {}, 8000),
        (["/x/site-packages/uvicorn/__main__.py", "app.main:app", "--port", "8002"], {}, 8002),
        (["uvicorn", "app.main:app", "--port=8001"], {}, 8001),
        (["uvicorn", "app.main:app"], {"UVICORN_PORT": "8002"}, 8002),
        (["uvicorn", "app.main:app", "--port", "8003"], {"UVICORN_PORT": "8002"}, 8003),
        (["uvicorn", "app.main:app", "--uds", "/tmp/x.sock"], {}, None),
        # No es el CLI de uvicorn: python -m app.main, pytest, el hijo de --reload de app.main.
        (["C:\\Tavo\\backend\\app\\main.py"], {}, None),
        (["pytest", "tests"], {}, None),
        ([], {}, None),
    ],
)
def test_puerto_de_uvicorn(argv, env, esperado):
    assert puerto_de_uvicorn(argv, env) == esperado


def test_puerto_correcto_no_detiene_nada():
    exigir_puerto_del_proyecto(8002, ["uvicorn", "app.main:app", "--port", "8002"], {})
    exigir_puerto_del_proyecto(8002, ["pytest"], {})


@pytest.mark.parametrize("argv", [["uvicorn", "app.main:app"], ["uvicorn", "app.main:app", "--port", "8001"]])
def test_puerto_equivocado_detiene_con_mensaje(argv, capsys):
    with pytest.raises(SystemExit) as exc:
        exigir_puerto_del_proyecto(8002, argv, {})
    assert exc.value.code == 1
    mensaje = capsys.readouterr().err
    assert "8002" in mensaje and "python -m app.main" in mensaje


def test_uvicorn_a_secas_no_arranca_de_verdad():
    """De punta a punta: `python -m uvicorn app.main:app` (sin --port) sale con
    código 1 y el mensaje, en vez de quedarse escuchando en el 8000."""
    proceso = subprocess.run(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"],
        cwd=BACKEND,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )
    assert proceso.returncode != 0
    assert "este backend usa el 8002" in proceso.stderr
