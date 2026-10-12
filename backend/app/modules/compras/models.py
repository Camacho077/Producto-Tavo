from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.modules.inventario import models as _inventario  # noqa: F401  (tabla de las FK a insumos)

# Relación muchos a muchos (2026-10-12): un proveedor surte varios INSUMOS y
# un insumo puede venir de varios proveedores. Lleva tenant_id como toda
# tabla de negocio. Al registrar una compra se ofrecen los insumos del
# proveedor elegido.
proveedor_insumos = Table(
    "proveedor_insumos",
    Base.metadata,
    Column("proveedor_id", UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="CASCADE"), primary_key=True),
    Column("insumo_id", UUID(as_uuid=True), ForeignKey("insumos.id", ondelete="CASCADE"), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True),
    Index("ix_proveedor_insumos_insumo", "insumo_id"),
)

# pendiente: registrada, todavía no afecta existencias. confirmada: las
# existencias subieron y el costo se actualizó. cancelada: se descartó
# estando pendiente. anulada: se revirtió una compra confirmada.
ESTADOS_COMPRA = ("pendiente", "confirmada", "cancelada", "anulada")


class Proveedor(Base, TenantMixin, TimestampMixin):
    __tablename__ = "proveedores"
    __table_args__ = (
        # El listado ordena por nombre dentro de la empresa.
        Index("ix_proveedores_tenant_nombre", "tenant_id", "nombre"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    # Nombre para mostrar: razón social (jurídica) o nombres + apellidos
    # (natural). Lo calcula el backend al guardar; no lo escribe el cliente.
    nombre = Column(String, nullable=False)
    tipo_persona = Column(String, nullable=False, default="juridica", server_default="juridica")
    # Persona natural
    tipo_documento = Column(String, nullable=True)  # CC | CE | PA | TI
    numero_documento = Column(String, nullable=True)
    nombres = Column(String, nullable=True)
    apellidos = Column(String, nullable=True)
    # Persona jurídica
    nit = Column(String, nullable=True)  # 900123456-7, con dígito de verificación validado
    razon_social = Column(String, nullable=True)
    representante_nombre = Column(String, nullable=True)
    representante_documento = Column(String, nullable=True)
    # Contacto
    telefono = Column(String, nullable=True)
    email = Column(String, nullable=True)
    direccion = Column(String, nullable=True)
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    compras = relationship("Compra", back_populates="proveedor")
    # Solo lectura: la tabla intermedia lleva tenant_id y se escribe a mano
    # en services.sincronizar_insumos_proveedor.
    insumos = relationship("Insumo", secondary=proveedor_insumos, viewonly=True, order_by="Insumo.nombre")


class Compra(Base, TenantMixin, TimestampMixin):
    __tablename__ = "compras"
    __table_args__ = (
        # El listado filtra por estado y el dashboard suma por rango de fecha.
        Index("ix_compras_tenant_estado_fecha", "tenant_id", "estado", "fecha"),
        # El listado ordena por consecutivo descendente.
        Index("ix_compras_tenant_numero", "tenant_id", "numero"),
        Index("ix_compras_proveedor", "proveedor_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    # Consecutivo legible por tenant (COM-000001) para el PDF y el buscador.
    numero = Column(Integer, nullable=False, default=0, server_default="0")
    proveedor_id = Column(UUID(as_uuid=True), ForeignKey("proveedores.id"), nullable=False)
    fecha = Column(DateTime, nullable=False)
    estado = Column(String, nullable=False, default="pendiente")
    total = Column(Numeric(12, 2), nullable=False, default=0)
    notas = Column(String, nullable=True)

    proveedor = relationship("Proveedor", back_populates="compras")
    items = relationship("CompraItem", back_populates="compra", cascade="all, delete-orphan")


class CompraItem(Base, TenantMixin):
    """Una línea de la compra: cuánto de un insumo, en la unidad en que se
    compró (kg aunque el insumo se lleve en g), y a qué precio POR ESA
    unidad. Al confirmar se convierte a la unidad del insumo."""
    __tablename__ = "compra_items"
    __table_args__ = (
        Index("ix_compra_items_compra", "compra_id"),
        Index("ix_compra_items_insumo", "insumo_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    compra_id = Column(UUID(as_uuid=True), ForeignKey("compras.id"), nullable=False)
    insumo_id = Column(UUID(as_uuid=True), ForeignKey("insumos.id"), nullable=False)
    cantidad = Column(Numeric(14, 3), nullable=False)
    unidad = Column(String(10), nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)

    compra = relationship("Compra", back_populates="items")
    insumo = relationship("Insumo")
