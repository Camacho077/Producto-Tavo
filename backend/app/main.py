from fastapi import FastAPI

from app.core.arranque import exigir_puerto_del_proyecto
from app.core.config import settings
from app.core.cors import configure_cors
from app.core.error_handlers import CatchAllExceptionsMiddleware, register_exception_handlers
from app.core.logging_config import configure_logging
from app.modules.dashboard.router import router as dashboard_router
from app.modules.compras.router import router as compras_router
from app.modules.ventas.router import router as ventas_router
from app.modules.seguridad.router import router as seguridad_router
from app.modules.ia.router import router as ia_router
from app.modules.ajustes.router import router as ajustes_router
from app.modules.imagenes.router import router as imagenes_router
from app.core.branding import NOMBRE_PRODUCTO, EMPRESA_PROVEEDORA

configure_logging()

# `uvicorn app.main:app` a secas escucharía en el 8000: se detiene con un
# mensaje claro en vez de arrancar en un puerto que nadie llama.
exigir_puerto_del_proyecto(settings.PORT)

app = FastAPI(
    title=settings.APP_NAME,
    description=f"Backend de {NOMBRE_PRODUCTO} — {EMPRESA_PROVEEDORA}",
    version="0.1.0",
)

# =============================================================================
# CONFIGURACIÓN CRÍTICA — NO ELIMINAR en limpiezas de código.
#  Sin esto el frontend no puede autenticarse (bloqueo CORS).
#
# Las tres líneas de abajo (handlers de error + catch-all de 500 + CORS) son
# configuración ACTIVA del proyecto aunque ninguna otra parte del código las
# referencie. Ya se borraron una vez por parecer "código no usado" y el login
# y el registro dejaron de funcionar desde el navegador.
#
# - configure_cors(): en ENV=development acepta cualquier puerto de
#   localhost/127.0.0.1 (regex); en cualquier otro ENV solo la lista explícita
#   de CORS_ORIGINS. Siempre allow_credentials=True, methods=* y headers=*.
#   Detalle en app/core/cors.py.
# - Orden importante: en Starlette, el middleware agregado AL FINAL queda más
#   externo (envuelve a los anteriores). CatchAllExceptionsMiddleware debe ir
#   ANTES que configure_cors() para que CORSMiddleware lo envuelva y las
#   respuestas de ERROR (400/401/409/422/500) también traigan
#   Access-Control-Allow-Origin. NO reemplazar el catch-all por
#   app.add_exception_handler(Exception, ...): Starlette instala ese handler
#   en ServerErrorMiddleware, que queda por fuera de CORS, y el 500 pierde el
#   header (comprobado; ver nota en app/core/error_handlers.py).
#
# Protegido por tests/test_cors.py y tests/test_cors_config.py: si esto se
# quita o se reordena, la suite falla.
# =============================================================================
register_exception_handlers(app)
app.add_middleware(CatchAllExceptionsMiddleware)
configure_cors(app, settings)

# Cada módulo del catálogo (sección 2 del brief) = un router independiente.
# Así se pueden activar/desactivar por cliente sin tocar los demás.
app.include_router(seguridad_router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_V1_PREFIX)
app.include_router(compras_router, prefix=settings.API_V1_PREFIX)
app.include_router(ventas_router, prefix=settings.API_V1_PREFIX)
app.include_router(ia_router, prefix=settings.API_V1_PREFIX)
app.include_router(ajustes_router, prefix=settings.API_V1_PREFIX)
app.include_router(imagenes_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["Sistema"])
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}


# Diagnóstico del entorno (el mismo informe que `python -m app.diagnostico`).
# SOLO en desarrollo: enseña la configuración cargada (sin secretos, pero
# con hosts, orígenes y puertos), así que en producción la ruta no existe.
if settings.ENV == "development":

    @app.get("/diagnostico", tags=["Sistema"])
    def diagnostico(origen: str | None = None):
        from app.diagnostico import diagnosticar

        return diagnosticar(origen)


# Arranque directo:  cd backend  ->  venv\Scripts\python -m app.main
# Usa el puerto de la configuración (PORT, 8002 por defecto) en vez del 8000
# que pone `uvicorn app.main:app` cuando nadie le pasa --port. En desarrollo
# recarga al guardar.
if __name__ == "__main__":
    import uvicorn

    print(f"Backend en http://localhost:{settings.PORT} (docs: http://localhost:{settings.PORT}/docs)", flush=True)
    uvicorn.run("app.main:app", host="127.0.0.1", port=settings.PORT, reload=settings.ENV == "development")
