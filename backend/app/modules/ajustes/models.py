from sqlalchemy import Boolean, Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base


class Zona(Base, TenantMixin, TimestampMixin):
    """Área del local ("Salón", "Terraza", "Segundo piso") que agrupa mesas."""
    __tablename__ = "zonas"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="uq_zonas_tenant_nombre"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String(40), nullable=False)
    # Orden en la cuadrícula "¿Para qué mesa?" (menor primero).
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    mesas = relationship("Mesa", back_populates="zona", order_by="Mesa.nombre")


class Mesa(Base, TenantMixin, TimestampMixin):
    """
    Mesa habilitada para tomar órdenes "en el local". Una mesa inactiva no
    aparece en la cuadrícula del mesero pero conserva su historial. Su estado
    de servicio (libre / ocupada / por cobrar) no se guarda: sale de las
    órdenes abiertas que tiene (fase 4).
    """
    __tablename__ = "mesas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nombre", name="uq_mesas_tenant_nombre"),
        Index("ix_mesas_zona", "zona_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String(20), nullable=False)
    zona_id = Column(UUID(as_uuid=True), ForeignKey("zonas.id"), nullable=True)
    puestos = Column(Integer, nullable=False, default=4, server_default="4")
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    zona = relationship("Zona", back_populates="mesas")
