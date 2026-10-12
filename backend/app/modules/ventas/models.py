from sqlalchemy import Index, Column, String, Integer, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid

# pendiente: registrada sin descontar stock. completada: stock descontado.
# cancelada: descartada estando pendiente. anulada: se revirtió una venta
# completada (el stock vuelve a subir).
ESTADOS_VENTA = ("pendiente", "completada", "cancelada", "anulada")

# Flujo de un pedido. Cada cambio queda registrado en PedidoEvento para la
# línea de tiempo de seguimiento.
ESTADOS_PEDIDO = ("pendiente", "en_proceso", "listo", "entregado", "cancelado")
PRIORIDADES_PEDIDO = ("baja", "media", "alta", "urgente")


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


class Pedido(Base, TenantMixin, TimestampMixin):
    """
    Un pedido es un compromiso con el cliente que se sigue en el tiempo
    (pendiente → en proceso → listo → entregado). No toca stock: cuando se
    entrega, el negocio registra la venta correspondiente.
    """
    __tablename__ = "pedidos"
    __table_args__ = (
        # Listado filtrado por estado y aviso de pedidos sin avanzar.
        Index("ix_pedidos_tenant_estado", "tenant_id", "estado"),
        Index("ix_pedidos_tenant_numero", "tenant_id", "numero"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    numero = Column(Integer, nullable=False, default=0, server_default="0")
    cliente_nombre = Column(String, nullable=False)
    cliente_telefono = Column(String, nullable=True)
    cliente_direccion = Column(String, nullable=True)
    fecha = Column(DateTime, nullable=False)
    fecha_entrega = Column(DateTime, nullable=True)
    prioridad = Column(String, nullable=False, default="media")
    estado = Column(String, nullable=False, default="pendiente")
    total = Column(Numeric(12, 2), nullable=False, default=0)
    notas = Column(String, nullable=True)

    items = relationship("PedidoItem", back_populates="pedido", cascade="all, delete-orphan")
    eventos = relationship(
        "PedidoEvento",
        back_populates="pedido",
        cascade="all, delete-orphan",
        order_by="PedidoEvento.created_at",
    )


class PedidoItem(Base, TenantMixin):
    __tablename__ = "pedido_items"
    __table_args__ = (
        Index("ix_pedido_items_pedido", "pedido_id"),
        Index("ix_pedido_items_producto", "producto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    pedido_id = Column(UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)

    pedido = relationship("Pedido", back_populates="items")
    producto = relationship("Producto")


class PedidoEvento(Base, TenantMixin, TimestampMixin):
    """Línea de tiempo del pedido: cada cambio de estado (o nota) es un evento."""
    __tablename__ = "pedido_eventos"
    __table_args__ = (
        # La línea de tiempo del pedido y el subconsulta de "último evento"
        # del panel de avisos agrupan por esta columna.
        Index("ix_pedido_eventos_pedido", "pedido_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    pedido_id = Column(UUID(as_uuid=True), ForeignKey("pedidos.id"), nullable=False)
    estado = Column(String, nullable=False)
    nota = Column(String, nullable=True)
    usuario_nombre = Column(String, nullable=True)

    pedido = relationship("Pedido", back_populates="eventos")
