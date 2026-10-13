"""
Alta de una empresa (tenant): la usan el registro self-service y los datos de
demostración, para que una empresa nazca SIEMPRE igual — rol Administrador,
roles de ejemplo, primer usuario y su aceptación de los documentos legales
vigentes — en una sola transacción.
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.catalogo_permisos import ROLES_DE_EJEMPLO
from app.core.errors import ConflictError
from app.core.legal import VERSIONES as VERSIONES_LEGALES
from app.core.security import hash_password
from app.db.models import Tenant
from app.modules.seguridad import models


def crear_empresa(db: Session, nombre_empresa: str, email: str, password: str, nombre_admin: str = "Administrador", **datos_tenant) -> tuple[Tenant, models.Usuario]:
    tenant = Tenant(nombre_empresa=nombre_empresa, **datos_tenant)
    db.add(tenant)
    try:
        db.flush()  # asigna tenant.id sin cerrar la transacción todavía
        rol_admin = models.Rol(tenant_id=tenant.id, nombre="Administrador", descripcion="Acceso total", es_administrador=True)
        db.add(rol_admin)
        for nombre, (descripcion, permisos) in ROLES_DE_EJEMPLO.items():
            db.add(models.Rol(tenant_id=tenant.id, nombre=nombre, descripcion=descripcion, permisos=permisos))
        db.flush()
        usuario = models.Usuario(
            tenant_id=tenant.id, nombre_completo=nombre_admin, email=email,
            hashed_password=hash_password(password), rol_id=rol_admin.id,
        )
        db.add(usuario)
        db.flush()
        # Prueba de la autorización: documento, versión vigente y fecha/hora.
        for documento, version in VERSIONES_LEGALES.items():
            db.add(models.AceptacionLegal(tenant_id=tenant.id, usuario_id=usuario.id, email=usuario.email, documento=documento, version=version))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError("Ya existe una cuenta registrada con ese correo electrónico")
    return tenant, usuario
