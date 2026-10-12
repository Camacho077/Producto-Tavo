from datetime import datetime, timezone

from sqlalchemy import Index, Column, String, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid


class Rol(Base, TenantMixin, TimestampMixin):
    """
    Roles definidos por cada empresa (tenant): ej. Administrador, Cajero, Bodega.
    Cada rol agrupa permisos sobre los módulos del sistema.
    """
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="uq_roles_tenant_nombre"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)

    # Permisos por módulo, ej: {"productos": ["ver","crear"], "ventas": ["ver"]}.
    # El catálogo de módulos y acciones está en app/core/catalogo_permisos.py.
    permisos = Column(JSON, default=dict, nullable=False, server_default="{}")

    # El rol Administrador tiene TODOS los permisos siempre (sus `permisos` se
    # ignoran), no se puede eliminar y solo otro administrador puede asignarlo:
    # así nadie deja a su empresa sin acceso ni se sube de privilegios.
    es_administrador = Column(Boolean, default=False, nullable=False, server_default="false")

    usuarios = relationship("Usuario", back_populates="rol")


class Usuario(Base, TenantMixin, TimestampMixin):
    __tablename__ = "usuarios"
    __table_args__ = (
        # Conteo de usuarios por rol y bloqueo al eliminar un rol.
        Index("ix_usuarios_rol", "rol_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre_completo = Column(String, nullable=False)
    # El login busca el usuario solo por email (sin selector de tenant previo),
    # por lo que el email debe ser único a nivel global, no solo por tenant.
    email = Column(String, nullable=False, unique=True, index=True)
    hashed_password = Column(String, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)

    rol_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    rol = relationship("Rol", back_populates="usuarios")


def _ahora_utc():
    return datetime.now(timezone.utc)


class AceptacionLegal(Base, TenantMixin):
    """
    Prueba de la autorización de tratamiento de datos y de la aceptación de
    los términos (Ley 1581 de 2012, art. 9; Decreto 1377 de 2013, art. 7):
    quién aceptó, qué documento, qué VERSIÓN y en qué fecha y hora (UTC).

    Solo se agregan filas, nunca se editan: si un documento cambia de
    versión, la aceptación nueva es otra fila y la vieja queda como prueba.
    """
    __tablename__ = "aceptaciones_legales"
    __table_args__ = (Index("ix_aceptaciones_legales_usuario", "usuario_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    # SET NULL + copia del correo: si después se elimina el usuario, la prueba
    # de que la empresa aceptó (y quién) NO se borra con él.
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    email = Column(String, nullable=False)
    documento = Column(String(40), nullable=False)  # app/core/legal.py: politica_datos | terminos
    version = Column(String(40), nullable=False)
    aceptada_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)
