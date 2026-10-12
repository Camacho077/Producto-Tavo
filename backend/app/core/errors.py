"""
Jerarquía de excepciones de negocio. Los routers y servicios lanzan estas
excepciones en vez de HTTPException directamente, y `error_handlers.py` las
traduce a una respuesta HTTP consistente (nunca se expone un stack trace).
"""


class AppError(Exception):
    status_code = 500
    detail = "Error interno del servidor"

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class AuthError(AppError):
    status_code = 401
    detail = "No autenticado"


class ForbiddenError(AppError):
    status_code = 403
    detail = "No tiene permisos para realizar esta acción"


class NotFoundError(AppError):
    status_code = 404
    detail = "Recurso no encontrado"


class ConflictError(AppError):
    status_code = 409
    detail = "La operación entra en conflicto con el estado actual del recurso"
