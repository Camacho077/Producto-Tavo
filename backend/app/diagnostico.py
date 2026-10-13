"""
Diagnóstico del entorno de desarrollo: dice qué está bien y qué falta, con
el arreglo concreto para cada cosa.

Uso (desde backend/, con el venv):
    python -m app.diagnostico                      # informe legible
    python -m app.diagnostico --origen http://192.168.1.50:5175
                                                   # ¿ese origen pasa CORS?
    python -m app.diagnostico --json               # para scripts

Con el backend corriendo en desarrollo también está en
GET http://localhost:8002/diagnostico (en producción responde 404: expone
configuración).

Revisa: archivos .env, variables cargadas (sin mostrar secretos), conexión a
Postgres, migraciones al día, orígenes CORS permitidos, frontend/.env y los
puertos (incluida la reserva de Windows sobre el 8000/8002). Sale con código
1 si hay algún error, así sirve también en scripts (setup.ps1 / setup.sh).
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
RAIZ = BACKEND_DIR.parent
# Mapa de puertos del Producto Tavo (docs/DECISIONES.md §1). Ninguno se
# repite con el Producto JS (5173 / 4173 / 8001 / 5432), que corre a la vez.
PUERTO_BACKEND = 8002
PUERTO_FRONTEND = 5175
PUERTO_POSTGRES = 5433

OK, AVISO, ERROR = "ok", "aviso", "error"


def _item(estado: str, titulo: str, detalle: str = "", arreglo: str = "") -> dict:
    return {"estado": estado, "titulo": titulo, "detalle": detalle, "arreglo": arreglo}


def _ocultar_clave_url(url: str) -> str:
    return re.sub(r"(://[^:/@]+:)[^@]*@", r"\1****@", url)


def _puerto_escucha(host: str, puerto: int) -> bool:
    try:
        with socket.create_connection((host, puerto), timeout=0.5):
            return True
    except OSError:
        return False


def _leer_env(archivo: Path) -> dict:
    datos = {}
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                clave, valor = linea.split("=", 1)
                datos[clave.strip()] = valor.strip()
    return datos


# ---------------------------------------------------------------- revisiones
def revisar_archivos_env() -> list[dict]:
    items = []
    for carpeta in ("backend", "frontend"):
        env = RAIZ / carpeta / ".env"
        if env.exists():
            items.append(_item(OK, f"{carpeta}/.env existe", str(env)))
        else:
            items.append(
                _item(
                    ERROR,
                    f"No existe {carpeta}/.env",
                    "Los .env no se versionan: cada máquina crea el suyo.",
                    f"Copy-Item {carpeta}\\.env.example {carpeta}\\.env   (o corre automatizaciones/setup.ps1)",
                )
            )
    return items


def revisar_variables(settings) -> list[dict]:
    from app.core.config import SECRET_KEY_DE_EJEMPLO

    en_archivo = _leer_env(BACKEND_DIR / ".env")
    items = []
    for nombre in type(settings).model_fields:
        valor = getattr(settings, nombre)
        origen = "entorno" if nombre in os.environ else ".env" if nombre in en_archivo else "valor por defecto"
        if nombre == "SECRET_KEY":
            mostrado = f"definida ({len(valor)} caracteres)"
            if valor == SECRET_KEY_DE_EJEMPLO:
                items.append(
                    _item(
                        AVISO,
                        "SECRET_KEY es el valor de ejemplo",
                        "Sirve en desarrollo; en producción el backend no arranca con ella.",
                        'python -c "import secrets; print(secrets.token_urlsafe(48))"  y pégala en backend/.env',
                    )
                )
        elif "DATABASE_URL" in nombre:
            mostrado = _ocultar_clave_url(valor)
        else:
            mostrado = str(valor)
        items.append(_item(OK, f"{nombre} = {mostrado}", f"origen: {origen}"))
    return items


def revisar_base_de_datos(settings) -> list[dict]:
    from sqlalchemy import create_engine, text

    url = settings.DATABASE_URL
    destino = urlparse(url)
    host, puerto, base = destino.hostname or "localhost", destino.port or 5432, destino.path.lstrip("/")
    engine = create_engine(url, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SHOW server_version")).scalar()
        return [_item(OK, f"Conexión a Postgres ({host}:{puerto}/{base})", f"Postgres {version}")]
    except Exception as exc:  # noqa: BLE001 — se traduce a un arreglo concreto
        texto = str(exc).lower()
        if "does not exist" in texto and "database" in texto:
            arreglo = (
                f'Crea la base: psql -U postgres -c "CREATE DATABASE {base} OWNER {destino.username};"'
                "  (setup.ps1 lo intenta solo)"
            )
            causa = f"La base '{base}' no existe en el servidor."
        elif "password authentication failed" in texto or "role" in texto and "does not exist" in texto:
            arreglo = "Revisa usuario y clave en DATABASE_URL (backend/.env) o crea el usuario en Postgres."
            causa = "Postgres rechazó las credenciales."
        elif not _puerto_escucha(host, puerto):
            arreglo = (
                "Arranca Postgres. Con Docker:  docker compose -f infra/docker-compose.yml up -d db   "
                "(o inicia el servicio de PostgreSQL de Windows)."
            )
            causa = f"Nada escucha en {host}:{puerto}."
        else:
            arreglo = "Revisa DATABASE_URL en backend/.env."
            causa = str(exc).splitlines()[0]
        return [_item(ERROR, f"Sin conexión a Postgres ({host}:{puerto}/{base})", causa, arreglo)]
    finally:
        engine.dispose()


def revisar_migraciones(settings) -> list[dict]:
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = set(script.get_heads())
    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            actuales = set(MigrationContext.configure(conn).get_current_heads())
    except Exception:  # noqa: BLE001
        return [_item(AVISO, "Migraciones: no se pudieron revisar", "No hay conexión a la base (ver arriba).")]
    finally:
        engine.dispose()
    if actuales == heads:
        return [_item(OK, "Migraciones al día", f"revisión {', '.join(sorted(heads))}")]
    pendientes = []
    for rev in script.walk_revisions():
        if rev.revision in actuales:
            break
        pendientes.append(rev.revision)
    return [
        _item(
            ERROR,
            f"Migraciones pendientes: {len(pendientes)}",
            f"Base en {', '.join(sorted(actuales)) or 'ninguna (vacía)'}; el código está en {', '.join(sorted(heads))}.",
            "cd backend  y  venv\\Scripts\\python -m alembic upgrade head",
        )
    ]


def revisar_cors(settings, origen_a_probar: str | None) -> list[dict]:
    from app.core.cors import DEV_ORIGIN_REGEX

    items = [_item(OK, f"CORS_ORIGINS explícitos: {', '.join(settings.cors_origins)}")]
    if settings.ENV == "development":
        items.append(
            _item(
                OK,
                "ENV=development: además se acepta cualquier origen local en cualquier puerto",
                "localhost, 127.0.0.1, [::1], red privada (10.x, 172.16–31.x, 192.168.x) y túneles de demo",
            )
        )
    else:
        items.append(
            _item(
                AVISO,
                f"ENV={settings.ENV}: solo se aceptan los CORS_ORIGINS explícitos",
                "Si estás en tu máquina, abrir el frontend en otro puerto o IP dará 400 en el OPTIONS del login.",
                "En desarrollo usa ENV=development en backend/.env",
            )
        )
    if origen_a_probar:
        origen = origen_a_probar.rstrip("/")
        pasa = origen in settings.cors_origins or (
            settings.ENV == "development" and re.fullmatch(DEV_ORIGIN_REGEX, origen) is not None
        )
        items.append(
            _item(
                OK if pasa else ERROR,
                f"Origen {origen}: {'PERMITIDO' if pasa else 'RECHAZADO (el preflight responderá 400)'}",
                "",
                "" if pasa else f'Agrégalo a CORS_ORIGINS en backend/.env, p. ej. CORS_ORIGINS=["{origen}"]',
            )
        )
    return items


def revisar_frontend() -> list[dict]:
    env = _leer_env(RAIZ / "frontend" / ".env")
    url = env.get("VITE_API_URL")
    if not url:
        return [
            _item(
                ERROR,
                "frontend/.env no define VITE_API_URL",
                "",
                "Copy-Item frontend\\.env.example frontend\\.env",
            )
        ]
    puerto = urlparse(url).port
    if puerto != PUERTO_BACKEND:
        return [
            _item(
                AVISO,
                f"VITE_API_URL={url} no apunta al puerto {PUERTO_BACKEND}",
                f"El backend de desarrollo corre en el {PUERTO_BACKEND} (start-backend.ps1).",
                f"VITE_API_URL=http://localhost:{PUERTO_BACKEND}/api/v1",
            )
        ]
    return [_item(OK, f"VITE_API_URL={url}")]


def _rangos_reservados_windows() -> list[tuple[int, int]]:
    if sys.platform != "win32":
        return []
    try:
        salida = subprocess.run(
            ["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    return [(int(a), int(b)) for a, b in re.findall(r"^\s*(\d+)\s+(\d+)", salida, re.MULTILINE)]


def revisar_puertos() -> list[dict]:
    items = []
    reservados = _rangos_reservados_windows()
    for puerto, quien in ((8000, "puerto por defecto de uvicorn"), (PUERTO_BACKEND, "backend")):
        rango = next(((a, b) for a, b in reservados if a <= puerto <= b), None)
        if rango:
            estado = ERROR if puerto == PUERTO_BACKEND else AVISO
            items.append(
                _item(
                    estado,
                    f"El puerto {puerto} ({quien}) está RESERVADO por Windows (rango {rango[0]}-{rango[1]})",
                    "Hyper-V/WSL/Docker reservan rangos al arrancar; uvicorn falla con WinError 10013.",
                    f"Por eso el proyecto usa el {PUERTO_BACKEND}. Si el {PUERTO_BACKEND} también cae en un rango: "
                    "net stop winnat  y  net start winnat  (PowerShell como administrador).",
                )
            )
    for puerto, nombre, comando in (
        (PUERTO_BACKEND, "Backend", "automatizaciones\\dev\\start-backend.ps1"),
        (PUERTO_FRONTEND, "Frontend", "automatizaciones\\dev\\start-frontend.ps1"),
        (PUERTO_POSTGRES, "Postgres", "docker compose -f infra/docker-compose.yml up -d db"),
    ):
        if _puerto_escucha("127.0.0.1", puerto):
            items.append(_item(OK, f"{nombre}: algo escucha en el puerto {puerto}"))
        else:
            items.append(
                _item(AVISO, f"{nombre}: nada escucha en el puerto {puerto}", "Si no lo has arrancado, es normal.", comando)
            )
    return items


def revisar_usuarios(settings) -> list[dict]:
    from sqlalchemy import create_engine, text

    engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 3})
    try:
        with engine.connect() as conn:
            usuarios = conn.execute(text("SELECT count(*) FROM usuarios")).scalar()
    except Exception:  # noqa: BLE001 — sin conexión o sin tablas: ya se reportó arriba
        return []
    finally:
        engine.dispose()
    if usuarios:
        return [_item(OK, f"Hay {usuarios} usuario(s) para iniciar sesión")]
    return [
        _item(
            AVISO,
            "No hay ningún usuario todavía",
            "",
            "Regístrate desde la pantalla de registro o corre automatizaciones/setup.ps1 (crea uno de prueba).",
        )
    ]


# ---------------------------------------------------------------- informe
def diagnosticar(origen: str | None = None) -> dict:
    secciones: dict[str, list[dict]] = {"Archivos de configuración": revisar_archivos_env()}
    try:
        from app.core.config import settings
    except SystemExit:
        # config.py ya imprimió qué falta; seguimos con lo que no depende de él.
        secciones["Variables del backend"] = [
            _item(ERROR, "La configuración del backend no carga", "Ver el mensaje de arriba.")
        ]
        settings = None

    if settings is not None:
        secciones["Variables del backend"] = revisar_variables(settings)
        secciones["Base de datos"] = revisar_base_de_datos(settings) + revisar_migraciones(settings) + revisar_usuarios(settings)
        secciones["CORS"] = revisar_cors(settings, origen)
    secciones["Frontend"] = revisar_frontend()
    secciones["Puertos"] = revisar_puertos()
    errores = sum(1 for items in secciones.values() for i in items if i["estado"] == ERROR)
    avisos = sum(1 for items in secciones.values() for i in items if i["estado"] == AVISO)
    return {"ok": errores == 0, "errores": errores, "avisos": avisos, "secciones": secciones}


MARCAS = {OK: "✔", AVISO: "⚠", ERROR: "✘"}


def imprimir(informe: dict) -> None:
    print("\nDiagnóstico del entorno — JS Restaurante (Producto Tavo)\n")
    for seccion, items in informe["secciones"].items():
        print(f"■ {seccion}")
        for i in items:
            print(f"  {MARCAS[i['estado']]} {i['titulo']}")
            if i["detalle"]:
                print(f"      {i['detalle']}")
            if i["arreglo"]:
                print(f"      → {i['arreglo']}")
        print()
    if informe["ok"]:
        print(f"✔ Todo listo ({informe['avisos']} aviso(s)).")
    else:
        print(f"✘ {informe['errores']} error(es) y {informe['avisos']} aviso(s). Arregla los ✘ de arriba.")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description="Diagnóstico del entorno de desarrollo")
    parser.add_argument("--origen", help="Origen a probar contra CORS, p. ej. http://192.168.1.50:5175")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    args = parser.parse_args()
    informe = diagnosticar(args.origen)
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        imprimir(informe)
    return 0 if informe["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
