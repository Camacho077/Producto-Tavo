"""
CAJA (fase 6, 2026-10-12): cobrar una orden la convierte en VENTA.

- Venta: el comprobante interno con número consecutivo de la empresa. Puede
  cubrir toda la orden o una parte (dividir la cuenta por platos). Desglosa
  la base, el impuesto al consumo y la propina (que nunca es automática y
  no es ingreso del restaurante). Lleva los datos del cliente que pediría
  una factura electrónica (tipo y número de documento, correo) y los campos
  `fe_*` vacíos: la facturación electrónica se integra después con un
  proveedor autorizado por la DIAN, sin cambiar este modelo.
- VentaPago: cada medio con el que se pagó (varios en una cuenta). En
  efectivo guarda lo recibido y las devueltas.
- CajaSesion: la caja del día. Se abre con una base, cada cobro y cada gasto
  pagado desde la caja cuentan en ella, y se cierra contando lo que hay por
  medio de pago; la diferencia queda registrada con su motivo.
"""
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base
from app.modules.ordenes import models as _ordenes  # noqa: F401

ESTADOS_VENTA = ("completada", "anulada")
ESTADOS_CAJA = ("abierta", "cerrada")


class CajaSesion(Base, TenantMixin, TimestampMixin):
    __tablename__ = "cajas"
    __table_args__ = (
        Index("ix_cajas_tenant_estado", "tenant_id", "estado"),
        Index("ix_cajas_tenant_numero", "tenant_id", "numero"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    numero = Column(Integer, nullable=False)
    estado = Column(String(10), nullable=False, default="abierta")
    abierta_en = Column(DateTime, nullable=False)
    abierta_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    abierta_por = Column(String, nullable=True)
    base_inicial = Column(Numeric(12, 2), nullable=False, default=0)
    cerrada_en = Column(DateTime, nullable=True)
    cerrada_por_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    cerrada_por = Column(String, nullable=True)
    # {medio: valor} al cerrar: lo que el sistema esperaba y lo que se contó.
    esperado = Column(JSON, nullable=True)
    contado = Column(JSON, nullable=True)
    diferencia = Column(Numeric(12, 2), nullable=True)
    motivo_diferencia = Column(String(250), nullable=True)

    ventas = relationship("Venta", back_populates="caja")


class Venta(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ventas"
    __table_args__ = (
        # El dashboard y los avisos suman ventas completadas por rango de fecha.
        Index("ix_ventas_tenant_estado_fecha", "tenant_id", "estado", "fecha"),
        Index("ix_ventas_tenant_numero", "tenant_id", "numero"),
        Index("ix_ventas_orden", "orden_id"),
        Index("ix_ventas_caja", "caja_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    numero = Column(Integer, nullable=False)
    fecha = Column(DateTime, nullable=False)
    estado = Column(String(12), nullable=False, default="completada")
    orden_id = Column(UUID(as_uuid=True), ForeignKey("ordenes.id"), nullable=False)
    caja_id = Column(UUID(as_uuid=True), ForeignKey("cajas.id"), nullable=False)
    cajero_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=True)
    cajero_nombre = Column(String, nullable=True)
    # Cliente (opcional; lo pediría la factura electrónica).
    cliente_nombre = Column(String(80), nullable=True)
    cliente_documento_tipo = Column(String(4), nullable=True)
    cliente_documento = Column(String(20), nullable=True)
    cliente_correo = Column(String(120), nullable=True)
    # Montos: total = subtotal + impuesto (lo que vale lo consumido); la
    # propina va aparte y no es ingreso del restaurante.
    subtotal = Column(Numeric(12, 2), nullable=False, default=0)
    impuesto = Column(Numeric(12, 2), nullable=False, default=0)
    impuesto_tasa = Column(Numeric(5, 2), nullable=False, default=0)
    total = Column(Numeric(12, 2), nullable=False, default=0)
    propina = Column(Numeric(12, 2), nullable=False, default=0)
    anulada_motivo = Column(String(200), nullable=True)
    # Facturación electrónica (NO construida): estado y CUFE del proveedor.
    fe_estado = Column(String(20), nullable=True)
    fe_cufe = Column(String(120), nullable=True)

    items = relationship("VentaItem", back_populates="venta", cascade="all, delete-orphan")
    pagos = relationship("VentaPago", back_populates="venta", cascade="all, delete-orphan")
    caja = relationship("CajaSesion", back_populates="ventas")
    orden = relationship("Orden")


class VentaItem(Base, TenantMixin):
    __tablename__ = "venta_items"
    __table_args__ = (
        Index("ix_venta_items_venta", "venta_id"),
        # "Más vendidos" agrupa por producto sobre esta columna.
        Index("ix_venta_items_producto", "producto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venta_id = Column(UUID(as_uuid=True), ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False)
    orden_item_id = Column(UUID(as_uuid=True), ForeignKey("orden_items.id"), nullable=True)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    nombre = Column(String, nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    # Costo de UNA unidad por su receta cuando se pidió: el margen de ese día
    # no cambia aunque después suba un insumo.
    costo_unitario = Column(Numeric(12, 2), nullable=True)

    venta = relationship("Venta", back_populates="items")
    producto = relationship("Producto")


class VentaPago(Base, TenantMixin):
    __tablename__ = "venta_pagos"
    __table_args__ = (Index("ix_venta_pagos_venta", "venta_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    venta_id = Column(UUID(as_uuid=True), ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False)
    medio = Column(String(15), nullable=False)
    monto = Column(Numeric(12, 2), nullable=False)  # lo que se abona a la cuenta
    recibido = Column(Numeric(12, 2), nullable=True)  # efectivo entregado
    cambio = Column(Numeric(12, 2), nullable=True)  # devueltas

    venta = relationship("Venta", back_populates="pagos")
