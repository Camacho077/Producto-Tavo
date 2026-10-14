"""
Elige los puertos del Producto Tavo en ESTA máquina y los deja escritos en
todos los archivos que los usan. Lo corren automatizaciones/setup.ps1 y
setup.sh; también se puede correr solo (desde la raíz del repositorio):

    python automatizaciones/dev/puertos.py            # decide y escribe
    python automatizaciones/dev/puertos.py --revisar  # solo informa

Por qué existe (2026-10-13): un compañero clonó el repo y el login fallaba
con ERR_CONNECTION_REFUSED contra el 8002. Los rangos de puertos que Windows
se reserva (Hyper-V / WSL / Docker) cambian de una máquina a otra, y el 8002
puede estar reservado u ocupado por otro programa. Antes el puerto estaba
fijo: si no se podía usar, nada arrancaba y el frontend llamaba a la nada.

Reglas, para cada servicio (Postgres, backend, frontend):
  * Se intenta el puerto que ya está configurado (o el del mapa: 5433 /
    8002 / 5175, docs/DECISIONES.md §1).
  * Sirve si está libre y Windows no lo tiene reservado, o si lo ocupa ESTE
    producto: su propio contenedor (<proyecto>-db, -backend, -frontend) o un
    proceso cuya línea de comando lleva la ruta de esta carpeta.
  * Si no, se toma el siguiente libre hacia arriba, sin pisar nunca los del
    Producto JS (5173 / 4173 / 8001 / 5432), y se AVISA.
  * El resultado se escribe en backend/.env (PORT y el puerto de
    DATABASE_URL), frontend/.env (VITE_API_URL) e infra/.env (los puertos
    que publica Docker y el nombre del proyecto). Así backend y frontend
    leen SIEMPRE el mismo puerto.

Solo usa la biblioteca estándar: corre antes de que exista el venv.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:  # pragma: no cover
    pass

RAIZ = Path(__file__).resolve().parents[2]

# Mapa del producto (docs/DECISIONES.md §1) y puertos del Producto JS, que
# corre a la vez en la máquina del dueño: nunca se eligen.
PREDETERMINADOS = {"db": 5433, "backend": 8002, "frontend": 5175}
PRODUCTO_JS = {5173, 4173, 8001, 5432}
OTROS_DEL_MAPA = {4175, 5679}  # vista previa y n8n de este producto
NOMBRES = {"db": "Postgres", "backend": "Backend", "frontend": "Frontend"}
PROYECTO_POR_DEFECTO = "tavo"
MAX_SALTOS = 200


# ---------------------------------------------------------------------------
# Lectura y escritura de los .env (sin dependencias)
# ---------------------------------------------------------------------------
def leer_env(ruta: Path) -> dict[str, str]:
    datos = {}
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", linea)
            if m:
                datos[m.group(1)] = m.group(2).strip()
    return datos


def escribir_variables(ruta: Path, valores: dict[str, str], encabezado: str = "") -> bool:
    """Reemplaza (o agrega al final) cada VARIABLE=valor sin tocar el resto
    del archivo: comentarios, orden y demás variables quedan iguales."""
    texto = ruta.read_text(encoding="utf-8-sig") if ruta.exists() else encabezado
    original = texto
    for clave, valor in valores.items():
        patron = re.compile(rf"(?m)^{re.escape(clave)}=.*$")
        if patron.search(texto):
            texto = patron.sub(lambda _m: f"{clave}={valor}", texto)
        else:
            texto = texto.rstrip("\n") + ("\n" if texto.strip() else "") + f"{clave}={valor}\n"
    if texto != original:
        ruta.write_text(texto, encoding="utf-8", newline="\n")
        return True
    return False


def puerto_de_url(url: str | None) -> int | None:
    m = re.search(r"://[^/]*:(\d+)", url or "")
    return int(m.group(1)) if m else None


def cambiar_puerto_url(url: str, puerto: int) -> str:
    return re.sub(r"(://[^/@]*@?[^/:]+):\d+", rf"\g<1>:{puerto}", url, count=1)


# ---------------------------------------------------------------------------
# Estado de un puerto en esta máquina
# ---------------------------------------------------------------------------
def rangos_reservados() -> list[tuple[int, int]]:
    """Rangos que Windows se reserva (nadie escucha, pero no se pueden abrir:
    WinError 10013). En Linux/macOS no existen."""
    if platform.system() != "Windows":
        return []
    try:
        salida = subprocess.run(["netsh", "interface", "ipv4", "show", "excludedportrange", "protocol=tcp"],
                                capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [(int(a), int(b)) for a, b in re.findall(r"(?m)^\s*(\d+)\s+(\d+)", salida)]


def reservado(puerto: int, rangos: list[tuple[int, int]]) -> tuple[int, int] | None:
    return next(((a, b) for a, b in rangos if a <= puerto <= b), None)


def escucha_alguien(puerto: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def se_puede_abrir(puerto: int) -> bool:
    """Prueba real: abrir el puerto un instante (Windows puede negarlo aunque
    no figure en los rangos reservados)."""
    for host in ("0.0.0.0", "127.0.0.1"):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if platform.system() == "Windows":
                s.setsockopt(socket.SOL_SOCKET, getattr(socket, "SO_EXCLUSIVEADDRUSE", 0xFFFFFFFB), 1)
            try:
                s.bind((host, puerto))
            except OSError:
                return False
    return True


def contenedor_en_puerto(puerto: int) -> str | None:
    try:
        r = subprocess.run(["docker", "ps", "--filter", f"publish={puerto}", "--format", "{{.Names}}"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    nombres = [n for n in r.stdout.split() if n]
    return nombres[0] if r.returncode == 0 and nombres else None


def linea_de_comando_en_puerto(puerto: int) -> str | None:
    """Línea de comando del proceso que escucha en el puerto (o None)."""
    try:
        if platform.system() == "Windows":
            ps = ("$c = Get-NetTCPConnection -LocalPort %d -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; "
                  "if ($c) { (Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\").CommandLine }") % puerto
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=20)
            return r.stdout.strip() or None
        r = subprocess.run(["lsof", "-nP", f"-iTCP:{puerto}", "-sTCP:LISTEN", "-t"], capture_output=True, text=True, timeout=10)
        pid = r.stdout.split()[0] if r.stdout.split() else None
        if not pid:
            return None
        return subprocess.run(["ps", "-o", "command=", "-p", pid], capture_output=True, text=True, timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass
class Estado:
    puerto: int
    situacion: str  # libre | propio | reservado | ocupado
    detalle: str = ""


def estado_puerto(puerto: int, servicio: str, proyecto: str, rangos, raiz: Path = RAIZ) -> Estado:
    rango = reservado(puerto, rangos)
    if rango:
        return Estado(puerto, "reservado", f"Windows lo reservó (rango {rango[0]}-{rango[1]})")
    if not escucha_alguien(puerto) and se_puede_abrir(puerto):
        return Estado(puerto, "libre")
    contenedor = contenedor_en_puerto(puerto)
    if contenedor:
        if contenedor == f"{proyecto}-{servicio}":
            return Estado(puerto, "propio", f"su contenedor {contenedor}")
        return Estado(puerto, "ocupado", f"lo usa el contenedor Docker '{contenedor}'")
    linea = linea_de_comando_en_puerto(puerto)
    if linea and str(raiz).lower().replace("\\", "/") in linea.lower().replace("\\", "/"):
        return Estado(puerto, "propio", "un proceso de esta misma carpeta")
    if not escucha_alguien(puerto):
        return Estado(puerto, "ocupado", "el sistema no deja abrirlo")
    resumen = " ".join((linea or "proceso desconocido").split())[:90]
    return Estado(puerto, "ocupado", f"lo usa otro programa: {resumen}")


def elegir(servicio: str, deseado: int, proyecto: str, rangos, evitar: set[int], consultar=estado_puerto) -> tuple[Estado, Estado]:
    """(estado del deseado, estado del elegido). Si el deseado no sirve,
    busca hacia arriba el primero libre que no esté en `evitar`."""
    inicial = consultar(deseado, servicio, proyecto, rangos)
    if inicial.situacion in ("libre", "propio") and deseado not in evitar:
        return inicial, inicial
    candidato = deseado
    for _ in range(MAX_SALTOS):
        candidato += 1
        if candidato in evitar or candidato > 65535:
            continue
        e = consultar(candidato, servicio, proyecto, rangos)
        if e.situacion == "libre":
            return inicial, e
    raise SystemExit(f"✘ No encontré un puerto libre para {NOMBRES[servicio]} entre {deseado} y {candidato}.")


# ---------------------------------------------------------------------------
# Programa
# ---------------------------------------------------------------------------
def configuracion_actual(raiz: Path) -> tuple[str, dict[str, int]]:
    infra = leer_env(raiz / "infra" / ".env")
    back = leer_env(raiz / "backend" / ".env")
    front = leer_env(raiz / "frontend" / ".env")
    proyecto = os.environ.get("TAVO_PROYECTO") or infra.get("TAVO_PROYECTO") or PROYECTO_POR_DEFECTO
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", proyecto):
        raise SystemExit(f"✘ TAVO_PROYECTO='{proyecto}' no es válido: solo minúsculas, números, - y _.")
    deseados = {
        "db": int(infra.get("DB_PORT") or puerto_de_url(back.get("DATABASE_URL")) or PREDETERMINADOS["db"]),
        "backend": int(back.get("PORT") or infra.get("BACKEND_PORT") or puerto_de_url(front.get("VITE_API_URL")) or PREDETERMINADOS["backend"]),
        "frontend": int(infra.get("FRONTEND_PORT") or PREDETERMINADOS["frontend"]),
    }
    return proyecto, deseados


def escribir(raiz: Path, proyecto: str, puertos: dict[str, int]) -> list[str]:
    cambiados = []
    infra = raiz / "infra" / ".env"
    encabezado = ("# Puertos y nombre de proyecto de Docker en ESTA máquina. Lo escribe\n"
                  "# automatizaciones/dev/puertos.py (setup.ps1 / setup.sh); no se versiona.\n")
    if escribir_variables(infra, {"TAVO_PROYECTO": proyecto, "DB_PORT": str(puertos["db"]),
                                  "BACKEND_PORT": str(puertos["backend"]), "FRONTEND_PORT": str(puertos["frontend"])}, encabezado):
        cambiados.append("infra/.env")
    back = raiz / "backend" / ".env"
    if back.exists():
        datos = leer_env(back)
        nuevos = {"PORT": str(puertos["backend"])}
        for clave in ("DATABASE_URL", "TEST_DATABASE_URL"):
            if datos.get(clave) and puerto_de_url(datos[clave]) not in (None, puertos["db"]) and "localhost" in datos[clave]:
                nuevos[clave] = cambiar_puerto_url(datos[clave], puertos["db"])
        if escribir_variables(back, nuevos):
            cambiados.append("backend/.env")
    front = raiz / "frontend" / ".env"
    if front.exists():
        url = leer_env(front).get("VITE_API_URL") or f"http://localhost:{PREDETERMINADOS['backend']}/api/v1"
        if "localhost" in url or "127.0.0.1" in url:
            if escribir_variables(front, {"VITE_API_URL": cambiar_puerto_url(url, puertos["backend"])}):
                cambiados.append("frontend/.env")
    return cambiados


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Elige y escribe los puertos del Producto Tavo en esta máquina")
    parser.add_argument("--revisar", action="store_true", help="solo informa; no escribe nada")
    parser.add_argument("--json", action="store_true", help="imprime el resultado como JSON en la última línea")
    parser.add_argument("--raiz", default=str(RAIZ), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    raiz = Path(args.raiz).resolve()

    proyecto, deseados = configuracion_actual(raiz)
    rangos = rangos_reservados()
    elegidos: dict[str, int] = {}
    estados: dict[str, str] = {}
    avisos = []
    for servicio in ("db", "backend", "frontend"):
        evitar = PRODUCTO_JS | OTROS_DEL_MAPA | set(elegidos.values())
        inicial, final = elegir(servicio, deseados[servicio], proyecto, rangos, evitar,
                                consultar=lambda p, s, pr, r: estado_puerto(p, s, pr, r, raiz))
        elegidos[servicio], estados[servicio] = final.puerto, final.situacion
        if final.puerto != inicial.puerto:
            avisos.append(f"{NOMBRES[servicio]}: el {inicial.puerto} no se puede usar ({inicial.detalle}); uso el {final.puerto}.")
            print(f"  ! {NOMBRES[servicio]:9} {inicial.puerto} → {final.puerto}  ({inicial.detalle})")
        else:
            extra = f" — {final.detalle}" if final.detalle else ""
            print(f"  ✔ {NOMBRES[servicio]:9} {final.puerto} {final.situacion}{extra}")

    cambiados = [] if args.revisar else escribir(raiz, proyecto, elegidos)
    for archivo in cambiados:
        print(f"    actualizado {archivo}")
    if avisos and not args.revisar:
        print("  ! Puertos cambiados en esta máquina: backend y frontend quedaron apuntando al mismo puerto.")
    if args.json:
        print(json.dumps({"proyecto": proyecto, "puertos": elegidos, "estados": estados, "avisos": avisos, "cambiados": cambiados}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
