"""
Configuración central de la aplicación.
Todos los valores sensibles se leen de variables de entorno (.env),
nunca se hardcodean en el código.

El archivo se busca SIEMPRE en backend/.env (ruta absoluta), no en la carpeta
desde la que se lanza el proceso: antes, arrancar uvicorn desde la raíz del
repo ignoraba el .env en silencio y el backend corría con valores por
defecto, y el síntoma aparecía lejos (401, CORS, base equivocada).

Si falta el .env o una variable obligatoria, el arranque se detiene con un
mensaje en español que dice qué archivo copiar (ver `cargar_settings`), en
vez del ValidationError de pydantic.

Plantilla con TODAS las variables y su explicación: backend/.env.example.
"""
import json
import sys
from pathlib import Path

from pydantic import Field, PrivateAttr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"

# Valor de ejemplo de SECRET_KEY en .env.example: sirve para desarrollo, pero
# con él cualquiera puede firmar tokens, así que fuera de desarrollo se rechaza.
SECRET_KEY_DE_EJEMPLO = "cambiar-esto-en-produccion"
ENTORNOS = ("development", "production")

# Qué hace cada variable obligatoria: se usa en el mensaje de error.
OBLIGATORIAS = {
    "DATABASE_URL": "cadena de conexión a Postgres, p. ej. postgresql://tavo_admin:tavo_admin@localhost:5433/tavo_erp",
    "SECRET_KEY": "clave con la que se firman los tokens de sesión (JWT)",
}


class Settings(BaseSettings):
    # App
    APP_NAME: str = "JS Company - ERP"
    # development: CORS acepta además cualquier origen local (ver
    # app/core/cors.py). production: solo la lista explícita CORS_ORIGINS.
    # Se valida: un valor mal escrito ("dev", "develop") apagaba el regex de
    # desarrollo en silencio y el preflight del login respondía 400.
    ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    # Puerto del backend. 8002: el 8001 es del Producto JS, que corre en la
    # misma máquina al mismo tiempo, y el 8000 suele quedar reservado por
    # Hyper-V/WSL (WinError 10013). Mapa completo de puertos: docs/DECISIONES.md
    # §1. Lo usan `python -m app.main` y automatizaciones/dev/start-backend.ps1;
    # `uvicorn app.main:app` a secas no lo lee, así que app/main.py se niega a
    # arrancar si uvicorn va a escuchar en otro puerto (app/core/arranque.py).
    PORT: int = Field(default=8002, ge=1, le=65535)
    # Plan con el que nace un tenant creado por el registro self-service
    # (basico | estandar | pro_ia). Mientras el producto se vende por
    # catálogo, todo registro nuevo entra con el plan completo y el plan
    # real se ajusta al cerrar la venta; con "basico" el sidebar ocultaba
    # Compras y Ventas y parecía que los módulos no existían.
    PLAN_POR_DEFECTO: str = "pro_ia"

    # Seguridad / JWT — SECRET_KEY es OBLIGATORIA (sin valor por defecto).
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 horas
    # Duración del token cuando el usuario marca "Recordarme" en el login.
    ACCESS_TOKEN_RECORDARME_DIAS: int = 30

    # Base de datos — OBLIGATORIA (sin valor por defecto).
    DATABASE_URL: str

    # Base de datos usada por la suite de pytest (separada de la de desarrollo)
    TEST_DATABASE_URL: str = "postgresql://tavo_admin:tavo_admin@localhost:5433/tavo_erp_test"

    # CORS - dominios permitidos para el frontend.
    # Se guarda como texto crudo (a propósito NO como list[str]): si el
    # campo fuera list[str], pydantic-settings intenta decodificarlo como
    # JSON ANTES de que corra cualquier validador nuestro, y un valor mal
    # escrito revienta con un SettingsError críptico ("error parsing value
    # for field...") sin decir qué está mal. Aquí lo validamos nosotros a
    # mano en _validar_cors_origins y damos un mensaje claro en español.
    # Acepta tanto CORS_ORIGINS=["http://localhost:5175"] (JSON) como
    # CORS_ORIGINS=http://localhost:5175,http://localhost:3000 (comas).
    CORS_ORIGINS: str = '["http://localhost:5175"]'

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    _cors_origins_parsed: list[str] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def _validar_entorno(self) -> "Settings":
        if self.ENV not in ENTORNOS:
            raise ValueError(
                f"ENV='{self.ENV}' no es válido: usa ENV=development en tu máquina o ENV=production en el servidor."
            )
        if self.ENV != "development" and (self.SECRET_KEY == SECRET_KEY_DE_EJEMPLO or len(self.SECRET_KEY) < 32):
            raise ValueError(
                "SECRET_KEY de producción insegura: debe tener al menos 32 caracteres y no ser el valor de "
                "ejemplo. Genera una con: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        if not self.SECRET_KEY.strip():
            raise ValueError("SECRET_KEY no puede estar vacía.")
        return self

    @model_validator(mode="after")
    def _validar_cors_origins(self) -> "Settings":
        texto = self.CORS_ORIGINS.strip()
        ejemplo = (
            'Configúralo en backend/.env con el formato CORS_ORIGINS=["http://localhost:5175"] '
            "(lista JSON, con comillas dobles) o separado por comas: "
            "CORS_ORIGINS=http://localhost:5175,http://localhost:3000"
        )

        if not texto:
            raise ValueError(f"CORS_ORIGINS no puede estar vacío. {ejemplo}")

        if texto.startswith("["):
            try:
                origenes = json.loads(texto)
            except json.JSONDecodeError as exc:
                raise ValueError(f"CORS_ORIGINS='{texto}' no es una lista JSON válida. {ejemplo}") from exc
            if not isinstance(origenes, list) or not all(isinstance(o, str) and o.strip() for o in origenes):
                raise ValueError(f"CORS_ORIGINS debe ser una lista de URLs de texto no vacías. {ejemplo}")
        else:
            origenes = [o.strip() for o in texto.split(",") if o.strip()]

        if not origenes:
            raise ValueError(f"CORS_ORIGINS no puede quedar vacío. {ejemplo}")

        self._cors_origins_parsed = origenes
        return self

    @property
    def cors_origins(self) -> list[str]:
        return self._cors_origins_parsed


class ConfiguracionInvalida(Exception):
    """La configuración no permite arrancar; el mensaje ya viene listo para
    mostrarse tal cual, en español y con el arreglo concreto."""


def _explicar(exc: ValidationError, env_file: Path) -> str:
    lineas = ["", "=" * 78, "ERROR DE CONFIGURACIÓN: el backend no puede arrancar.", "=" * 78]
    if not env_file.exists():
        lineas += [
            f"No existe el archivo {env_file}.",
            "Créalo a partir de la plantilla (trae todas las variables comentadas):",
            "    Windows (PowerShell):  Copy-Item backend\\.env.example backend\\.env",
            "    Linux / macOS:         cp backend/.env.example backend/.env",
            "O corre el arranque automático, que lo hace por ti:",
            "    Windows: .\\automatizaciones\\setup.ps1      Linux/macOS: ./automatizaciones/setup.sh",
            "",
        ]
    for error in exc.errors():
        campo = str(error["loc"][0]) if error.get("loc") else ""
        if error["type"] == "missing":
            lineas.append(f"- Falta la variable {campo}: {OBLIGATORIAS.get(campo, 'obligatoria')}.")
        else:
            mensaje = str(error["msg"]).removeprefix("Value error, ")
            lineas.append(f"- {campo + ': ' if campo else ''}{mensaje}")
    if env_file.exists():
        lineas += ["", f"Revisa {env_file} (compáralo con backend/.env.example)."]
    lineas += ["Diagnóstico completo:  cd backend  y luego  python -m app.diagnostico", "=" * 78, ""]
    return "\n".join(lineas)


def cargar_settings(env_file: Path = ENV_FILE, **valores) -> Settings:
    """Construye Settings o lanza ConfiguracionInvalida con un mensaje claro.
    `valores` permite sobrescribir variables (pruebas)."""
    try:
        return Settings(_env_file=env_file, **valores)
    except ValidationError as exc:
        raise ConfiguracionInvalida(_explicar(exc, env_file)) from None


try:
    settings = cargar_settings()
except ConfiguracionInvalida as _exc:
    # Se escribe en stderr y se sale con código 1: uvicorn, alembic y los
    # scripts muestran este texto en vez de un traceback de pydantic.
    try:
        print(_exc, file=sys.stderr)
    except UnicodeEncodeError:  # consola sin UTF-8: se ve sin tildes, pero se ve
        print(str(_exc).encode("ascii", "replace").decode(), file=sys.stderr)
    raise SystemExit(1)
