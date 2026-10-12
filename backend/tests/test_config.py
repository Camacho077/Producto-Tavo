import pytest
from pydantic import ValidationError

from app.core.config import ConfiguracionInvalida, Settings, cargar_settings


def test_cors_origins_formato_json_valido():
    s = Settings(CORS_ORIGINS='["http://localhost:5175", "http://localhost:3000"]')
    assert s.cors_origins == ["http://localhost:5175", "http://localhost:3000"]


def test_cors_origins_formato_separado_por_comas():
    s = Settings(CORS_ORIGINS="http://localhost:5175,http://localhost:3000")
    assert s.cors_origins == ["http://localhost:5175", "http://localhost:3000"]


def test_cors_origins_json_malformado_da_error_claro_en_espanol():
    with pytest.raises(ValidationError) as exc_info:
        Settings(CORS_ORIGINS="[http://localhost:5175]")

    mensaje = str(exc_info.value)
    assert "no es una lista JSON válida" in mensaje
    assert 'CORS_ORIGINS=["http://localhost:5175"]' in mensaje


def test_cors_origins_vacio_da_error_claro_en_espanol():
    with pytest.raises(ValidationError) as exc_info:
        Settings(CORS_ORIGINS="")

    assert "no puede estar vacío" in str(exc_info.value)


def test_cors_origins_lista_json_con_no_strings_falla():
    with pytest.raises(ValidationError) as exc_info:
        Settings(CORS_ORIGINS="[1, 2]")

    assert "lista de URLs de texto" in str(exc_info.value)


# ---------- Arranque con .env ausente o incompleto (mensaje claro) ----------
@pytest.fixture
def sin_variables(monkeypatch):
    for nombre in ("DATABASE_URL", "SECRET_KEY", "ENV", "CORS_ORIGINS"):
        monkeypatch.delenv(nombre, raising=False)


def test_sin_archivo_env_dice_que_archivo_copiar(sin_variables, tmp_path):
    with pytest.raises(ConfiguracionInvalida) as exc_info:
        cargar_settings(tmp_path / "no-existe.env")
    mensaje = str(exc_info.value)
    assert "No existe el archivo" in mensaje
    assert "Copy-Item backend\\.env.example backend\\.env" in mensaje
    assert "cp backend/.env.example backend/.env" in mensaje
    assert "Falta la variable DATABASE_URL" in mensaje
    assert "Falta la variable SECRET_KEY" in mensaje
    # Nada del texto críptico de pydantic.
    assert "validation error" not in mensaje.lower()
    assert "Field required" not in mensaje


def test_env_sin_una_variable_obligatoria_la_nombra(sin_variables, tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text("SECRET_KEY=algo\n", encoding="utf-8")
    with pytest.raises(ConfiguracionInvalida) as exc_info:
        cargar_settings(archivo)
    mensaje = str(exc_info.value)
    assert "Falta la variable DATABASE_URL" in mensaje
    assert "Falta la variable SECRET_KEY" not in mensaje
    assert "No existe el archivo" not in mensaje


def test_env_mal_escrito_no_apaga_cors_de_desarrollo_en_silencio(sin_variables, tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text("SECRET_KEY=algo\nDATABASE_URL=postgresql://a@b/c\nENV=develop\n", encoding="utf-8")
    with pytest.raises(ConfiguracionInvalida) as exc_info:
        cargar_settings(archivo)
    assert "ENV='develop' no es válido" in str(exc_info.value)


def test_produccion_rechaza_la_secret_key_de_ejemplo(sin_variables, tmp_path):
    archivo = tmp_path / ".env"
    archivo.write_text(
        "SECRET_KEY=cambiar-esto-en-produccion\nDATABASE_URL=postgresql://a@b/c\nENV=production\n", encoding="utf-8"
    )
    with pytest.raises(ConfiguracionInvalida) as exc_info:
        cargar_settings(archivo)
    assert "SECRET_KEY de producción insegura" in str(exc_info.value)


def test_el_env_se_busca_en_backend_aunque_se_arranque_desde_otra_carpeta():
    from app.core import config

    assert config.ENV_FILE == config.BACKEND_DIR / ".env"
    assert config.ENV_FILE.is_absolute()


def test_arrancar_sin_env_termina_con_codigo_1_y_mensaje_en_espanol(tmp_path):
    """Proceso real: se copia config.py a <tmp>/backend/app/core/ (una carpeta
    backend SIN .env) y se importa en un intérprete limpio. Debe salir con
    código 1 y el texto que dice qué copiar, no con un traceback de pydantic."""
    import os
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    origen = Path(__file__).resolve().parents[1] / "app" / "core" / "config.py"
    core = tmp_path / "backend" / "app" / "core"
    core.mkdir(parents=True)
    (tmp_path / "backend" / "app" / "__init__.py").write_text("")
    (core / "__init__.py").write_text("")
    shutil.copy(origen, core / "config.py")

    entorno = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "SECRET_KEY", "ENV", "CORS_ORIGINS")}
    entorno["PYTHONIOENCODING"] = "utf-8"
    proceso = subprocess.run(
        [sys.executable, "-c", "import app.core.config"],
        cwd=tmp_path / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=entorno,
    )
    assert proceso.returncode == 1, proceso.stdout + proceso.stderr
    assert "ERROR DE CONFIGURACIÓN" in proceso.stderr
    assert "cp backend/.env.example backend/.env" in proceso.stderr
    assert "Traceback" not in proceso.stderr


def test_env_example_documenta_todas_las_variables_de_settings():
    """backend/.env.example es la referencia para quien clona el repo: cada
    variable de Settings debe estar ahí (con su comentario)."""
    from pathlib import Path

    plantilla = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    definidas = {linea.split("=", 1)[0].strip() for linea in plantilla.splitlines() if "=" in linea and not linea.lstrip().startswith("#")}
    faltantes = set(Settings.model_fields) - definidas
    assert not faltantes, f"Faltan en backend/.env.example: {sorted(faltantes)}"


def test_env_example_carga_sin_errores(tmp_path):
    """Copiar la plantilla tal cual debe dar un entorno de desarrollo válido."""
    from pathlib import Path

    plantilla = Path(__file__).resolve().parents[1] / ".env.example"
    s = cargar_settings(plantilla)
    assert s.ENV == "development"
    assert s.DATABASE_URL.startswith("postgresql://")


# ---------- Puerto del backend: 8002 por defecto (Producto Tavo; 8001 es del Producto JS) ----------
def test_puerto_por_defecto_es_8002(sin_variables, monkeypatch, tmp_path):
    """El frontend llama al 8002 (VITE_API_URL); el 8001 es del Producto JS
    y el 8000 lo reserva Windows."""
    monkeypatch.delenv("PORT", raising=False)
    archivo = tmp_path / ".env"
    archivo.write_text("SECRET_KEY=algo\nDATABASE_URL=postgresql://a@b/c\n", encoding="utf-8")
    assert cargar_settings(archivo).PORT == 8002


def test_puerto_se_lee_del_env(sin_variables, monkeypatch, tmp_path):
    monkeypatch.delenv("PORT", raising=False)
    archivo = tmp_path / ".env"
    archivo.write_text("SECRET_KEY=algo\nDATABASE_URL=postgresql://a@b/c\nPORT=8123\n", encoding="utf-8")
    assert cargar_settings(archivo).PORT == 8123


def test_puerto_fuera_de_rango_no_arranca(sin_variables, monkeypatch, tmp_path):
    monkeypatch.delenv("PORT", raising=False)
    archivo = tmp_path / ".env"
    archivo.write_text("SECRET_KEY=algo\nDATABASE_URL=postgresql://a@b/c\nPORT=70000\n", encoding="utf-8")
    with pytest.raises(ConfiguracionInvalida) as exc_info:
        cargar_settings(archivo)
    assert "PORT" in str(exc_info.value)


def test_arranques_usan_el_puerto_de_la_configuracion():
    """`python -m app.main` y start-backend.ps1 toman el puerto de Settings,
    no del 8000 por defecto de uvicorn."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    main = (raiz / "backend" / "app" / "main.py").read_text(encoding="utf-8")
    bloque = main.split('if __name__ == "__main__":', 1)[1]
    assert "port=settings.PORT" in bloque
    script = (raiz / "automatizaciones" / "dev" / "start-backend.ps1").read_text(encoding="utf-8-sig")
    assert "settings.PORT" in script
    assert "--port $PUERTO --reload" in script
