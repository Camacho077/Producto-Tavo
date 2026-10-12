from sqlalchemy import Index, Column, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid

# pendiente: registrada sin descontar stock. completada: stock descontado.
# cancelada: descartada estando pendiente. anulada: se revirtió una venta
# completada (el stock vuelve a subir).
ESTADOS_VENTA = ("pendiente", "completada", "cancelada", "anulada")


class Venta(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ventas"
    __table_args__ = (
        # El dashboard y los avisos suman ventas completadas por rango de
        # fecha; el listado filtra por estado. Es la consulta más caliente.
        Index("ix_ventas_tenant_estado_fecha", "tenant_id", "estado", "fecha"),
        Index("ix_ventas_tenant_numero", "tenant_id", "numero"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    numero = Column(Integer, nullable=False, default=0, server_default="0")
    cliente_nombre = Column(String, nullable=False)
    cliente_documento = Column(String, nullable=True)
    fecha = Column(DateTime, nullable=False)
    estado = Column(String, nullable=False, default="pendiente")
    total = Column(Numeric(12, 2), nullable=False, default=0)
    notas = Column(String, nullable=True)

    items = relationship("VentaItem", back_populates="venta", cascade="all, delete-orphan")


class VentaItem(Base, TenantMixin):
    __tablename__ = "venta_items"
    __table_args__ = (
        Index("ix_venta_items_venta", "venta_id"),
        # "Más vendidos" agrupa por producto sobre esta columna.
        Index("ix_venta_items_producto", "producto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venta_id = Column(UUID(as_uuid=True), ForeignKey("ventas.id"), nullable=False)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    # Costo de UNA unidad por su receta en el momento de la venta (2026-10-12):
    # el margen de ese día no cambia aunque después suba un insumo. None si
    # el plato no tenía receta.
    costo_unitario = Column(Numeric(12, 2), nullable=True)

    venta = relationship("Venta", back_populates="items")
    producto = relationship("Producto")
