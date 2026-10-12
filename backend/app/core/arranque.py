"""
Guarda de arranque: el backend solo escucha en SU puerto (Settings.PORT).

El CLI de uvicorn no lee la configuración del proyecto: `uvicorn app.main:app`
a secas escucha en el 8000, y con un `--port` copiado del otro producto
(el Producto JS usa el 8001) chocaría con él. Esta máquina corre los dos
productos a la vez, así que un puerto equivocado no es un detalle: o falla
sin explicación (puerto reservado por Windows) o atiende el frontend del
otro producto.

Por eso, si el proceso lo lanzó el CLI de uvicorn y el puerto efectivo no es
`Settings.PORT`, `app/main.py` se detiene con un mensaje en español que dice
cómo arrancarlo bien. `python -m app.main`, start-backend.ps1, Docker y las
pruebas no se ven afectados (los tres primeros ya pasan el puerto correcto;
las pruebas no pasan por el CLI).
"""
import os
import sys
from pathlib import PurePath

PUERTO_POR_DEFECTO_UVICORN = 8000


def _lanzado_por_cli_de_uvicorn(argv: list[str]) -> bool:
    if not argv:
        return False
    ruta = PurePath(argv[0].replace("\\", "/"))
    # `uvicorn ...` / `uvicorn.exe ...`  o  `python -m uvicorn ...`
    # (en ese caso argv[0] es .../uvicorn/__main__.py).
    return ruta.stem.lower() == "uvicorn" or (ruta.name == "__main__.py" and ruta.parent.name == "uvicorn")


def puerto_de_uvicorn(argv: list[str], env: dict) -> int | None:
    """Puerto TCP en el que escuchará el CLI de uvicorn con estos argumentos,
    o None si el proceso no es el CLI de uvicorn (o escucha por --fd/--uds)."""
    if not _lanzado_por_cli_de_uvicorn(argv):
        return None
    puerto = None
    argumentos = argv[1:]
    for i, arg in enumerate(argumentos):
        if arg in ("--fd", "--uds") or arg.startswith(("--fd=", "--uds=")):
            return None
        if arg == "--port" and i + 1 < len(argumentos):
            puerto = argumentos[i + 1]
        elif arg.startswith("--port="):
            puerto = arg.split("=", 1)[1]
    if puerto is None:
        puerto = env.get("UVICORN_PORT", PUERTO_POR_DEFECTO_UVICORN)
    try:
        return int(puerto)
    except (TypeError, ValueError):
        return None


def exigir_puerto_del_proyecto(puerto_proyecto: int, argv: list[str] | None = None, env: dict | None = None) -> None:
    argv = sys.argv if argv is None else argv
    env = os.environ if env is None else env
    puerto = puerto_de_uvicorn(argv, env)
    if puerto is None or puerto == puerto_proyecto:
        return
    print(
        "\n".join(
            [
                "",
                "=" * 78,
                # Sin símbolos fuera de cp1252: con la salida redirigida,
                # Windows no podría escribirlos y el mensaje se perdería.
                f"ERROR: uvicorn iba a escuchar en el puerto {puerto}, pero este backend usa el {puerto_proyecto}",
                "  (PORT en backend/.env; el frontend llama a ese puerto y el 8001 es del Producto JS).",
                "=" * 78,
                "Arráncalo con cualquiera de estas opciones (desde backend/, con el venv):",
                "    python -m app.main",
                "    powershell -ExecutionPolicy Bypass -File ..\\automatizaciones\\dev\\start-backend.ps1",
                f"    python -m uvicorn app.main:app --port {puerto_proyecto} --reload",
                "=" * 78,
            ]
        ),
        file=sys.stderr,
        flush=True,
    )
    raise SystemExit(1)
