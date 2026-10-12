"""
VERIFICACIÓN DE PERMISOS POR ROL — la única capa que cuenta.

El frontend oculta lo que un rol no puede hacer, pero eso es comodidad: la
seguridad está aquí. Cada endpoint de negocio declara el permiso que exige:

    tenant_id: uuid.UUID = Depends(tenant_con_permiso("productos", "eliminar"))
    usuario: Usuario = Depends(usuario_con_permiso("usuarios", "editar"))

Si el rol del usuario no lo tiene, responde 403 con la causa concreta ("Tu rol
«Cajero» no tiene permiso para eliminar productos…"), nunca un genérico. Antes
del rol se comprueba el PLAN (2026-10-01): si la empresa no contrató el
módulo, 403 con la causa ("El plan Básico de tu empresa no incluye Compras…").

Cada dependencia lleva la marca `__permiso__ = (modulo, accion)`. El test
`tests/test_permisos.py` recorre TODAS las rutas y falla si alguna ruta de
negocio no la tiene: un endpoint nuevo sin permiso no puede pasar
desapercibido.

El tenant sigue saliendo SIEMPRE del token (a través del usuario), nunca de un
parámetro que el cliente pueda manipular.
"""
import uuid
from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import object_session

from app.core.catalogo_permisos import (
    CATALOGO,
    acciones_de,
    frase_permiso,
    mensaje_no_contratado,
    modulo_contratado,
    permisos_de_rol,
)
from app.core.deps import get_current_usuario
from app.core.errors import ForbiddenError
from app.db.models import Tenant
from app.modules.seguridad.models import Usuario


def permisos_efectivos(usuario: Usuario) -> dict[str, list[str]]:
    rol = usuario.rol
    if rol is None:
        return {}
    return permisos_de_rol(bool(rol.es_administrador), rol.permisos)


def es_administrador(usuario: Usuario) -> bool:
    return bool(usuario.rol and usuario.rol.es_administrador)


def tiene_permiso(usuario: Usuario, modulo: str, accion: str) -> bool:
    return accion in permisos_efectivos(usuario).get(modulo, [])


def exigir_plan(usuario: Usuario, modulo: str) -> None:
    """El módulo tiene que estar en el plan de la empresa (o contratado como
    add-on en `modulos_activos`). Va ANTES que el rol: ni un administrador usa
    lo que su empresa no contrató."""
    sesion = object_session(usuario)
    tenant = sesion.get(Tenant, usuario.tenant_id) if sesion is not None else None
    if tenant is None:
        return
    if not modulo_contratado(tenant.plan, tenant.modulos_activos, modulo):
        raise ForbiddenError(mensaje_no_contratado(tenant.plan, modulo))


def exigir_permiso(usuario: Usuario, modulo: str, accion: str) -> None:
    exigir_plan(usuario, modulo)
    if not tiene_permiso(usuario, modulo, accion):
        nombre_rol = usuario.rol.nombre if usuario.rol else "sin rol"
        raise ForbiddenError(
            f"Tu rol «{nombre_rol}» no tiene permiso para {frase_permiso(modulo, accion)}. "
            "Pídele a un administrador de tu empresa que te lo asigne en Seguridad → Roles."
        )


def _validar_par(modulo: str, accion: str) -> None:
    # Un error de tipeo en un router debe romper al ARRANCAR, no en producción.
    if modulo not in CATALOGO or accion not in acciones_de(modulo):
        raise ValueError(f"Permiso inexistente en el catálogo: {modulo}.{accion}")


def usuario_con_permiso(modulo: str, accion: str) -> Callable[..., Usuario]:
    """Dependencia que devuelve el usuario si su rol tiene el permiso."""
    _validar_par(modulo, accion)

    def _dependencia(usuario: Usuario = Depends(get_current_usuario)) -> Usuario:
        exigir_permiso(usuario, modulo, accion)
        return usuario

    _dependencia.__permiso__ = (modulo, accion)
    _dependencia.__name__ = f"permiso_{modulo}_{accion}"
    return _dependencia


def tenant_con_permiso(modulo: str, accion: str) -> Callable[..., uuid.UUID]:
    """Dependencia que devuelve el tenant_id del usuario si su rol tiene el
    permiso. Reemplaza a `get_current_tenant_id` en los endpoints de negocio."""
    verificar = usuario_con_permiso(modulo, accion)

    def _dependencia(usuario: Usuario = Depends(verificar)) -> uuid.UUID:
        return usuario.tenant_id

    _dependencia.__permiso__ = (modulo, accion)
    _dependencia.__name__ = f"tenant_{modulo}_{accion}"
    return _dependencia
