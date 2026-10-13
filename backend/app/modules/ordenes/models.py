"""
ÓRDENES DE PEDIDO CON COMANDA (fase 4, 2026-10-12) — el centro del sistema.

- Orden: lo que pide una mesa o un cliente. Número consecutivo POR JORNADA
  (la orden #1 de cada día). Estado de negocio: abierta → cobrada, o anulada.
- Comanda: cada ENVÍO a cocina. La orden nace con su comanda 1; agregar
  platos a una orden ya enviada crea la comanda 2 con solo lo nuevo. La
  cocina trabaja comandas: entrante → en preparación → lista → entregada.
  Una comanda sin nada para cocina (solo venta directa) nace "lista".
- OrdenItem: cada plato pedido, con lo que costaba y CUÁNTO GASTÓ de cada
  insumo (`consumo`): anular un plato devuelve exactamente eso, aunque la
  receta haya cambiado después.
- OrdenEvento: la línea de tiempo (creada, platos agregados, plato anulado,
  tomada, lista, entregada, anulada, cobrada) con quién y cuándo.
"""
from sqlalchemy import JSON, Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base
# Tablas a las que apuntan las claves foráneas (scripts y alembic).
from app.modules.ajustes import models as _ajustes  # noqa: F401
from app.modules.catalogo import models as _catalogo  # noqa: F401
from app.modules.seguridad import models as _seguridad  # noqa: F401

ESTADOS_ORDEN = ("abierta", "cobrada", "anulada")
ESTADOS_COMANDA = ("entrante", "en_preparacion", "lista", "entregada")
TIPOS_ORDEN = ("local", "llevar", "domicilio")
ORIGENES = ("local", "llamada", "whatsapp")


class Orden(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ordenes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "jornada", "numero", name="uq_ordenes_tenant_jornada_numero"),
        # Tablero (abiertas de la jornada) y estado de las mesas.
        Index("ix_ordenes_tenant_estado", "tenant_id", "estado"),
        Index("ix_ordenes_tenant_jornada", "tenant_id", "jornada"),
        Index("ix_ordenes_mesa", "mesa_id"),
        Index("ix_ordenes_mesero", "mesero_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    jornada = Column(Date, nullable=False)
    numero = Column(Integer, nullable=False)
    tipo = Column(String(12), nullable=False)
    origen = Column(String(12), nullable=False, default="local")
    mesa_id = Column(UUID(as_uuid=True), ForeignKey("mesas.id"), nullable=True)
    cliente_nombre = Column(String(80), nullable=True)
    cliente_telefono = Column(String(20), nullable=True)
    cliente_direccion = Column(String(150), nullable=True)
    nota = Column(String(200), nullable=True)
    estado = Column(String(12), nullable=False, default="abierta")
    total = Column(Numeric(12, 2), nullable=False, default=0)
    mesero_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    mesero_nombre = Column(String, nullable=True)
    anulada_motivo = Column(String(200), nullable=True)
    cerrada_en = Column(DateTime, nullable=True)  # cobrada o anulada

    mesa = relationship("Mesa")
    items = relationship("OrdenItem", back_populates="orden", cascade="all, delete-orphan", order_by="OrdenItem.posicion")
    comandas = relationship("Comanda", back_populates="orden", cascade="all, delete-orphan", order_by="Comanda.numero")
    eventos = relationship("OrdenEvento", back_populates="orden", cascade="all, delete-orphan", order_by="OrdenEvento.created_at")


class Comanda(Base, TenantMixin, TimestampMixin):
    __tablename__ = "comandas"
    __table_args__ = (
        Index("ix_comandas_orden", "orden_id"),
        # Pantalla de cocina: las comandas vivas de la empresa.
        Index("ix_comandas_tenant_estado", "tenant_id", "estado"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    orden_id = Column(UUID(as_uuid=True), ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)  # 1 = el pedido, 2… = lo agregado
    estado = Column(String(16), nullable=False, default="entrante")
    va_a_cocina = Column(Boolean, nullable=False, default=True)
    tomada_en = Column(DateTime, nullable=True)
    tomada_por = Column(String, nullable=True)
    lista_en = Column(DateTime, nullable=True)
    lista_por = Column(String, nullable=True)
    entregada_en = Column(DateTime, nullable=True)
    entregada_por = Column(String, nullable=True)

    orden = relationship("Orden", back_populates="comandas")
    items = relationship("OrdenItem", back_populates="comanda", order_by="OrdenItem.posicion")


class OrdenItem(Base, TenantMixin):
    __tablename__ = "orden_items"
    __table_args__ = (
        Index("ix_orden_items_orden", "orden_id"),
        Index("ix_orden_items_comanda", "comanda_id"),
        Index("ix_orden_items_producto", "producto_id"),
        Index("ix_orden_items_venta", "venta_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    orden_id = Column(UUID(as_uuid=True), ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False)
    comanda_id = Column(UUID(as_uuid=True), ForeignKey("comandas.id", ondelete="CASCADE"), nullable=False)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    nombre = Column(String, nullable=False)  # como estaba en la carta
    cantidad = Column(Integer, nullable=False)
    # Precio de UNA unidad con sus extras (el que se cobra).
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    costo_unitario = Column(Numeric(12, 2), nullable=True)
    # [{id, tipo, nombre, precio}] tal como se pidió.
    modificadores = Column(JSON, nullable=False, default=list)
    nota = Column(String(120), nullable=True)
    va_a_cocina = Column(Boolean, nullable=False, default=True)
    # {insumo_id: cantidad en la unidad del insumo} que salió de la bodega.
    consumo = Column(JSON, nullable=False, default=dict)
    anulado = Column(Boolean, nullable=False, default=False)
    anulado_motivo = Column(String(200), nullable=True)
    # La venta (comprobante) que lo cobró; None = por cobrar.
    venta_id = Column(UUID(as_uuid=True), ForeignKey("ventas.id", use_alter=True, name="fk_orden_items_venta"), nullable=True)
    posicion = Column(Integer, nullable=False, default=0)

    orden = relationship("Orden", back_populates="items")
    comanda = relationship("Comanda", back_populates="items")
    producto = relationship("Producto")


class OrdenEvento(Base, TenantMixin, TimestampMixin):
    __tablename__ = "orden_eventos"
    __table_args__ = (Index("ix_orden_eventos_orden", "orden_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    orden_id = Column(UUID(as_uuid=True), ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String(20), nullable=False)
    nota = Column(String(250), nullable=True)
    usuario_nombre = Column(String, nullable=True)

    orden = relationship("Orden", back_populates="eventos")
