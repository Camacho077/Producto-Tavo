# CONFIGURACIÓN CRÍTICA — NO ELIMINAR en limpiezas de código.
#  Sin esto el frontend no puede autenticarse (bloqueo CORS).
"""
Handlers de excepciones centralizados para FastAPI. Objetivo: nunca dejar
pasar un stack trace al cliente, responder siempre con un código HTTP
correcto y un mensaje claro en español, y loguear el detalle en el servidor.

Nota sobre CORS y errores 500 (no obvio, no lo cambies sin leer esto):
Starlette extrae de `app.exception_handlers` cualquier handler registrado
para la clase `Exception` (o el status 500) y lo usa como `handler` de
`ServerErrorMiddleware`, que SIEMPRE es la capa MÁS EXTERNA del stack ASGI
— por diseño, queda fuera de cualquier middleware agregado con
`add_middleware`, incluido `CORSMiddleware`, sin importar el orden en que
se registren. Por eso un `@app.exception_handler(Exception)` nunca puede
traer headers de CORS en su respuesta, y reordenar `add_middleware` no lo
arregla. La solución es no usar `@app.exception_handler(Exception)` para
el catch-all: `CatchAllExceptionsMiddleware` de abajo atrapa cualquier
excepción no manejada ANTES de que escape a `ServerErrorMiddleware`, desde
una capa que si queda envuelta por `CORSMiddleware` (ver orden de
`add_middleware` en app/main.py).
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.errors import AppError

logger = logging.getLogger("app.errors")

# Traducción de los tipos de error más comunes de Pydantic v2 a español.
_MENSAJES_POR_TIPO = {
    "missing": "Este campo es obligatorio",
    "string_type": "Debe ser un texto",
    "int_type": "Debe ser un número entero",
    "int_parsing": "Debe ser un número entero válido",
    "float_type": "Debe ser un número",
    "float_parsing": "Debe ser un número válido",
    "decimal_parsing": "Debe ser un número válido",
    "bool_parsing": "Debe ser verdadero o falso",
    "bool_type": "Debe ser verdadero o falso",
    "uuid_parsing": "Debe ser un identificador (UUID) válido",
    "uuid_type": "Debe ser un identificador (UUID) válido",
    "value_error.email": "Debe ser un correo electrónico válido",
    "string_too_short": "Es demasiado corto",
    "string_too_long": "Es demasiado largo",
    "greater_than": "Debe ser mayor que el mínimo permitido",
    "greater_than_equal": "Debe ser mayor o igual al mínimo permitido",
    "less_than": "Debe ser menor que el máximo permitido",
    "less_than_equal": "Debe ser menor o igual al máximo permitido",
    "enum": "El valor no está entre las opciones permitidas",
    "extra_forbidden": "No se admiten campos adicionales",
    "json_invalid": "El cuerpo de la petición no es JSON válido",
}


def _traducir_error(err: dict) -> dict:
    campo = ".".join(str(p) for p in err["loc"] if p != "body")
    tipo = err.get("type", "")
    mensaje = _MENSAJES_POR_TIPO.get(tipo)
    if mensaje is None:
        # Los ValueError lanzados por validadores custom (app/core/validaciones.py)
        # ya vienen en español; Pydantic los prefija con "Value error, " y aquí
        # se quita ese prefijo para mostrarlos tal cual bajo el campo.
        mensaje = err.get("msg", "Valor inválido")
        for prefijo in ("Value error, ", "Assertion failed, "):
            if mensaje.startswith(prefijo):
                mensaje = mensaje[len(prefijo):]
    if "not a valid email" in mensaje.lower():
        mensaje = "Debe ser un correo electrónico válido"
    return {"campo": campo, "mensaje": mensaje}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        contenido = {"detail": exc.detail}
        if exc.datos:
            contenido["datos"] = exc.datos
        return JSONResponse(status_code=exc.status_code, content=contenido)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        errores = [_traducir_error(e) for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content={"detail": "Los datos enviados no son válidos", "errores": errores},
        )

    # Deliberadamente NO se registra un @app.exception_handler(Exception) acá
    # — ver la nota de CORS al inicio del archivo. El catch-all de 500 vive
    # en CatchAllExceptionsMiddleware, agregado como middleware en main.py.


class CatchAllExceptionsMiddleware(BaseHTTPMiddleware):
    """
    Red de seguridad para cualquier excepción no controlada (no es AppError
    ni RequestValidationError, ej. un error de base de datos). Al ser un
    middleware normal (no un exception_handler de la clase Exception), su
    respuesta SÍ pasa por CORSMiddleware siempre que este se agregue
    después en app.add_middleware (ver app/main.py) — así una respuesta
    500 también trae Access-Control-Allow-Origin.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception:
            logger.exception("Error no controlado en %s %s", request.method, request.url.path)
            return JSONResponse(status_code=500, content={"detail": "Error interno del servidor"})
