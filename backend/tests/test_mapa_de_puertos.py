"""Mapa de puertos del Producto Tavo (docs/DECISIONES.md §1).

CONFIGURACIÓN CRÍTICA: este producto corre AL MISMO TIEMPO que el Producto JS
en la misma máquina. Cada puerto vive en varios archivos (Vite, .env, Docker,
scripts, launch.json) y basta que uno se desalinee para volver a los errores
de "CORS" que en realidad eran un puerto equivocado. Esta prueba cruza todos
los archivos y además comprueba que ninguno reutilice un puerto, contenedor o
volumen del Producto JS.
"""
import json
import re
from pathlib import Path

import pytest

from app.core.config import Settings

RAIZ = Path(__file__).resolve().parents[2]

TAVO = {"frontend": 5175, "preview": 4175, "backend": 8002, "postgres": 5433, "n8n": 5679}
PRODUCTO_JS = {"frontend": 5173, "preview": 4173, "backend": 8001, "postgres": 5432}


def leer(ruta: str) -> str:
    return (RAIZ / ruta).read_text(encoding="utf-8-sig")


def test_los_puertos_no_se_repiten_con_el_producto_js():
    assert not set(TAVO.values()) & set(PRODUCTO_JS.values())
    assert len(set(TAVO.values())) == len(TAVO)


def test_backend_settings_y_env_example():
    assert Settings.model_fields["PORT"].default == TAVO["backend"]
    env = leer("backend/.env.example")
    assert re.search(r"(?m)^PORT=8002$", env)
    assert re.search(r"(?m)^DATABASE_URL=postgresql://tavo_admin:tavo_admin@localhost:5433/tavo_erp$", env)
    assert re.search(r"(?m)^TEST_DATABASE_URL=postgresql://[^@]+@localhost:5433/tavo_erp_test$", env)


def test_frontend_vite_y_env_example():
    vite = leer("frontend/vite.config.js")
    servidor = vite.split("server: {", 1)[1].split("},", 1)[0]
    vista = vite.split("preview: {", 1)[1].split("},", 1)[0]
    assert re.search(r"port:\s*5175,", servidor) and "strictPort: true" in servidor
    assert re.search(r"port:\s*4175,", vista) and "strictPort: true" in vista
    assert re.search(r"(?m)^VITE_API_URL=http://localhost:8002/api/v1$", leer("frontend/.env.example"))
    assert '"predev": "node scripts/liberar-puerto.mjs 5175"' in leer("frontend/package.json")
    assert 'localhost:8002/api/v1' in leer("frontend/src/lib/api.js")


def test_docker_compose_aislado_del_producto_js():
    compose = leer("infra/docker-compose.yml")
    # Sin nombre propio, Docker usaría el de la carpeta ("infra"), el mismo
    # que el compose del Producto JS: compartirían contenedores y volumen.
    # Desde el 2026-10-13 nombre y puertos publicados se pueden cambiar por
    # máquina (infra/.env, lo escribe automatizaciones/dev/puertos.py), pero
    # SIN ese archivo deben valer exactamente los del mapa.
    assert re.search(r"(?m)^name: \$\{TAVO_PROYECTO:-tavo\}$", compose)
    for servicio in ("db", "backend", "n8n", "frontend"):
        assert f"container_name: ${{TAVO_PROYECTO:-tavo}}-{servicio}" in compose
    for volumen in ("tavo_db_data", "tavo_n8n_data"):
        sufijo = volumen.removeprefix("tavo_")
        assert re.search(rf"(?m)^  {volumen}:\n    name: \$\{{TAVO_PROYECTO:-tavo\}}_{sufijo}$", compose)
    publicados = dict(re.findall(r'-\s*"\$\{(\w+):-(\d+)\}:\d+"', compose))
    assert {k: int(v) for k, v in publicados.items()} == {
        "DB_PORT": TAVO["postgres"], "BACKEND_PORT": TAVO["backend"], "N8N_PORT": TAVO["n8n"], "FRONTEND_PORT": TAVO["frontend"]}
    assert not re.findall(r'-\s*"\d+:\d+"', compose), "ningún puerto publicado fijo: todos con su variable y su valor del mapa"
    assert "POSTGRES_DB: tavo_erp" in compose and "POSTGRES_USER: tavo_admin" in compose
    assert "js_company_erp" not in compose and "js_admin" not in compose
    # Dentro de Docker el backend habla con Postgres por el nombre del servicio
    # y escucha SIEMPRE en el 8002 (arranque.py exige uvicorn == Settings.PORT).
    assert "@db:5432/tavo_erp" in compose
    assert 'PORT: "8002"' in compose and '"${BACKEND_PORT:-8002}:8002"' in compose
    assert "http://localhost:${BACKEND_PORT:-8002}/api/v1" in compose


def test_backend_en_docker_espera_migra_y_tiene_healthcheck():
    compose = leer("infra/docker-compose.yml")
    backend = compose.split("\n  backend:", 1)[1].split("\n  n8n:", 1)[0]
    assert 'command: ["python", "-m", "app.inicio_docker"]' in backend
    assert "healthcheck:" in backend and "8002/health" in backend
    assert "condition: service_healthy" in backend  # espera a que Postgres esté listo
    assert "required: false" in backend  # sin backend/.env: mensaje en español, no error de Docker
    inicio = leer("backend/app/inicio_docker.py")
    assert '"alembic", "upgrade", "head"' in inicio and '"--port", str(settings.PORT)' in inicio


def test_scripts_y_lanzadores():
    comun = leer("automatizaciones/dev/comun.ps1")
    for servicio, puerto in TAVO.items():
        assert re.search(rf"{servicio}\s*=\s*@\{{ Puerto = {puerto};", comun), servicio
    lanzador = json.loads(leer(".claude/launch.json"))
    puertos = {c["name"]: c["port"] for c in lanzador["configurations"]}
    assert puertos == {"tavo-frontend-dev": 5175, "tavo-backend": 8002, "tavo-frontend-preview": 4175}
    assert "--port\", \"8002\"" in leer(".vscode/launch.json")


@pytest.mark.parametrize("script", ["dev/start-backend.ps1", "dev/start-frontend.ps1", "demo/start-demo-tunel.ps1"])
def test_los_scripts_no_cierran_procesos_del_otro_producto(script):
    """Antes se cerraba 'todo python con uvicorn' y 'todo node con vite':
    arrancar un producto tumbaba al otro."""
    texto = leer(f"automatizaciones/{script}")
    assert '-like "*multiprocessing.spawn*"' not in texto
    assert '-like "*uvicorn*app.main*"' not in texto
    if "Name='node.exe'" in texto:
        assert "$frontend" in texto, "los node de vite se reconocen por la ruta de este frontend"


def test_verificar_puertos_existe_y_revisa_reservas():
    texto = leer("automatizaciones/dev/verificar-puertos.ps1")
    assert "Get-RangosReservados" in texto and "Get-Ocupantes" in texto
    assert (RAIZ / "automatizaciones/dev/verificar-puertos.ps1").read_bytes().startswith(b"\xef\xbb\xbf")
