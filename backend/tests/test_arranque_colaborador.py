"""
Arranque en una máquina nueva (2026-10-13): un compañero clonó el repo y el
login daba ERR_CONNECTION_REFUSED contra el 8002 (puerto reservado u ocupado
en su Windows, backend en otro puerto) y, ya conectado, su base estaba vacía.

Aquí se prueba la lógica que lo evita:
  * automatizaciones/dev/puertos.py elige un puerto que sirva y deja backend y
    frontend apuntando al MISMO;
  * app/inicio_docker.py espera a Postgres y, si no llega, dice por qué en
    español en vez de dejar el contenedor mudo.
"""
import importlib.util
import socket
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def puertos():
    spec = importlib.util.spec_from_file_location("puertos", RAIZ / "automatizaciones" / "dev" / "puertos.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["puertos"] = modulo  # las dataclass lo buscan ahí
    spec.loader.exec_module(modulo)
    return modulo


# ---------------------------------------------------------------- elegir
def _consulta(estados, Estado):
    def consultar(puerto, servicio, proyecto, rangos):
        return estados.get(puerto, Estado(puerto, "libre"))
    return consultar


def test_si_el_puerto_sirve_se_queda(puertos):
    inicial, final = puertos.elegir("backend", 8002, "tavo", [], set(), consultar=_consulta({}, puertos.Estado))
    assert inicial.puerto == final.puerto == 8002


def test_el_puerto_propio_se_conserva(puertos):
    propio = {8002: puertos.Estado(8002, "propio", "su contenedor tavo-backend")}
    _, final = puertos.elegir("backend", 8002, "tavo", [], set(), consultar=_consulta(propio, puertos.Estado))
    assert final.puerto == 8002


def test_reservado_u_ocupado_salta_al_siguiente_libre_sin_pisar_el_producto_js(puertos):
    estados = {
        8000: puertos.Estado(8000, "reservado", "rango 7990-8000"),
        8002: puertos.Estado(8002, "ocupado", "otro programa"),
        8003: puertos.Estado(8003, "reservado", "rango 8003-8003"),
    }
    inicial, final = puertos.elegir("backend", 8000, "tavo", [], {8001}, consultar=_consulta(estados, puertos.Estado))
    assert inicial.situacion == "reservado"
    assert final.puerto == 8004  # 8001 es del Producto JS, 8002 ocupado, 8003 reservado


def test_un_puerto_ocupado_de_verdad_se_detecta(puertos):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        puerto = s.getsockname()[1]
        estado = puertos.estado_puerto(puerto, "backend", "proyecto-que-no-existe", [], raiz=RAIZ / "no-es-esta-carpeta")
    assert estado.situacion == "ocupado"


def test_un_rango_reservado_de_windows_se_detecta(puertos):
    estado = puertos.estado_puerto(8002, "backend", "tavo", [(7990, 8089)])
    assert estado.situacion == "reservado" and "7990-8089" in estado.detalle


# ---------------------------------------------------------------- .env
def test_urls_cambian_solo_el_puerto(puertos):
    assert puertos.cambiar_puerto_url("postgresql://tavo_admin:tavo_admin@localhost:5433/tavo_erp", 5434) == \
        "postgresql://tavo_admin:tavo_admin@localhost:5434/tavo_erp"
    assert puertos.cambiar_puerto_url("http://localhost:8002/api/v1", 8003) == "http://localhost:8003/api/v1"
    assert puertos.puerto_de_url("postgresql://u:p@localhost:5433/x") == 5433
    assert puertos.puerto_de_url("http://localhost:8002/api/v1") == 8002


def test_escribe_el_mismo_puerto_en_backend_frontend_e_infra(puertos, tmp_path):
    for carpeta in ("backend", "frontend", "infra"):
        (tmp_path / carpeta).mkdir()
    (tmp_path / "backend" / ".env").write_text(
        "# comentario que se conserva\nSECRET_KEY=abc\nPORT=8002\n"
        "DATABASE_URL=postgresql://tavo_admin:tavo_admin@localhost:5433/tavo_erp\n"
        "TEST_DATABASE_URL=postgresql://tavo_admin:tavo_admin@localhost:5433/tavo_erp_test\n", encoding="utf-8")
    (tmp_path / "frontend" / ".env").write_text("VITE_API_URL=http://localhost:8002/api/v1\n", encoding="utf-8")

    cambiados = puertos.escribir(tmp_path, "tavo", {"db": 5434, "backend": 8003, "frontend": 5176})

    assert set(cambiados) == {"infra/.env", "backend/.env", "frontend/.env"}
    back = puertos.leer_env(tmp_path / "backend" / ".env")
    assert back["PORT"] == "8003" and back["SECRET_KEY"] == "abc"
    assert back["DATABASE_URL"].endswith("@localhost:5434/tavo_erp")
    assert back["TEST_DATABASE_URL"].endswith("@localhost:5434/tavo_erp_test")
    assert "# comentario que se conserva" in (tmp_path / "backend" / ".env").read_text(encoding="utf-8")
    assert puertos.leer_env(tmp_path / "frontend" / ".env")["VITE_API_URL"] == "http://localhost:8003/api/v1"
    infra = puertos.leer_env(tmp_path / "infra" / ".env")
    assert infra == {"TAVO_PROYECTO": "tavo", "DB_PORT": "5434", "BACKEND_PORT": "8003", "FRONTEND_PORT": "5176"}
    # Volver a escribir lo mismo no toca nada.
    assert puertos.escribir(tmp_path, "tavo", {"db": 5434, "backend": 8003, "frontend": 5176}) == []


def test_la_configuracion_actual_sale_de_los_env(puertos, tmp_path, monkeypatch):
    monkeypatch.delenv("TAVO_PROYECTO", raising=False)
    for carpeta in ("backend", "frontend", "infra"):
        (tmp_path / carpeta).mkdir()
    proyecto, deseados = puertos.configuracion_actual(tmp_path)
    assert proyecto == "tavo" and deseados == {"db": 5433, "backend": 8002, "frontend": 5175}
    (tmp_path / "backend" / ".env").write_text("PORT=8010\nDATABASE_URL=postgresql://u:p@localhost:5440/x\n", encoding="utf-8")
    (tmp_path / "infra" / ".env").write_text("TAVO_PROYECTO=tavo-prueba\nFRONTEND_PORT=5180\n", encoding="utf-8")
    assert puertos.configuracion_actual(tmp_path) == ("tavo-prueba", {"db": 5440, "backend": 8010, "frontend": 5180})


def test_nunca_elige_los_puertos_del_producto_js(puertos):
    assert puertos.PRODUCTO_JS == {5173, 4173, 8001, 5432}
    assert not set(puertos.PREDETERMINADOS.values()) & puertos.PRODUCTO_JS


# ---------------------------------------------------------------- Docker
def test_si_postgres_no_llega_el_backend_dice_por_que_en_espanol(capsys):
    from app import inicio_docker

    with pytest.raises(SystemExit) as salida:
        inicio_docker.esperar_base("postgresql://nadie:nada@127.0.0.1:1/ninguna", espera_maxima=0, pausa=0)
    assert salida.value.code == 1
    texto = capsys.readouterr().out
    assert "✘ El backend no arrancó: Postgres no respondió en 127.0.0.1:1" in texto
    assert "→" in texto and "docker compose" in texto


# ---------------------------------------------------------------- scripts
@pytest.mark.parametrize("script", ["setup.ps1", "setup.sh"])
def test_el_setup_comprueba_de_verdad_antes_de_decir_listo(script):
    texto = (RAIZ / "automatizaciones" / script).read_text(encoding="utf-8-sig")
    for pieza in ("dev/puertos.py" if script.endswith(".sh") else r"dev\puertos.py", "estado_base.py", "seed_demo.py",
                  "/health", "seguridad/login", "admin@dondetavo.demo", "--wait", "production"):
        assert pieza in texto, f"{script} perdió: {pieza}"
    for cuenta in ("caja@dondetavo.demo", "mesero@dondetavo.demo", "cocina@dondetavo.demo"):
        assert cuenta in texto
    # "Listo" solo después del login comprobado.
    assert texto.index("seguridad/login") < texto.index("Listo: el backend responde")


def test_los_ps1_nuevos_llevan_bom_y_el_diagnostico_revisa_todo():
    for ruta in ("setup.ps1", "dev/diagnostico.ps1", "dev/start-backend.ps1"):
        assert (RAIZ / "automatizaciones" / ruta).read_bytes().startswith(b"\xef\xbb\xbf"), ruta  # PowerShell 5.1 y las tildes
    texto = (RAIZ / "automatizaciones" / "dev" / "diagnostico.ps1").read_text(encoding="utf-8-sig")
    for pieza in ("docker info", "VITE_API_URL", "puertos.py", "docker inspect", "/health", "estado_base.py", "seguridad/login"):
        assert pieza in texto, pieza
