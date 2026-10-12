from sqlalchemy import Boolean, Column, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base

# Tipos de movimiento de un insumo. `cantidad` va con signo (en la unidad del
# insumo): positiva suma existencia, negativa la resta.
TIPOS_MOVIMIENTO = (
    "inicial",  # carga inicial o primera existencia conocida
    "compra",
    "anulacion_compra",
    "venta",  # salida por receta al vender
    "anulacion_venta",
    "merma",  # daño, vencimiento, desperdicio: siempre con motivo
    "ajuste",  # conteo físico: diferencia entre el sistema y lo contado
)

UNIDADES_INSUMO = ("kg", "g", "L", "ml", "unidad")


class Insumo(Base, TenantMixin, TimestampMixin):
    """
    Materia prima del restaurante (arroz, queso, carne, gaseosa en botella).

    `existencia` es un acumulado de conveniencia: SIEMPRE es la suma de sus
    movimientos y nunca se edita a mano (el formulario no la trae y el
    backend la ignora). `costo_unitario` es el costo de UNA unidad del
    insumo (un kg, un g, una unidad) por promedio ponderado de las compras;
    con él se calcula el costo de cada plato por su receta.
    """
    __tablename__ = "insumos"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nombre", name="uq_insumos_tenant_nombre"),
        Index("ix_insumos_tenant_activo", "tenant_id", "activo"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String(100), nullable=False)
    unidad = Column(String(10), nullable=False)  # ver UNIDADES_INSUMO
    # Grupo libre para ordenar la bodega y el dashboard: "Carnes", "Lácteos".
    grupo = Column(String(40), nullable=True)
    existencia = Column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    minimo = Column(Numeric(14, 3), nullable=False, default=0, server_default="0")
    costo_unitario = Column(Numeric(14, 4), nullable=False, default=0, server_default="0")
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    movimientos = relationship("MovimientoInsumo", back_populates="insumo", order_by="MovimientoInsumo.created_at.desc()")


class MovimientoInsumo(Base, TenantMixin, TimestampMixin):
    """
    Trazabilidad de la existencia: quién, cuándo, cuánto y por qué. Cada
    compra confirmada, venta, merma, ajuste o anulación deja una fila.
    `costo_unitario` es el costo vigente al momento del movimiento y `valor`
    el costo de lo que entró o salió (con signo): la suma de los `valor` de
    tipo venta es el COSTO DE LO VENDIDO.
    """
    __tablename__ = "movimientos_insumo"
    __table_args__ = (
        Index("ix_movimientos_insumo_tenant_insumo", "tenant_id", "insumo_id"),
        Index("ix_movimientos_insumo_documento", "documento_id"),
        Index("ix_movimientos_insumo_tenant_tipo_fecha", "tenant_id", "tipo", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    insumo_id = Column(UUID(as_uuid=True), ForeignKey("insumos.id"), nullable=False)
    tipo = Column(String(20), nullable=False)
    cantidad = Column(Numeric(14, 3), nullable=False)
    existencia_resultante = Column(Numeric(14, 3), nullable=False)
    costo_unitario = Column(Numeric(14, 4), nullable=False, default=0, server_default="0")
    valor = Column(Numeric(14, 2), nullable=False, default=0, server_default="0")
    documento_tipo = Column(String(20), nullable=True)  # compra | venta | orden | None (merma/ajuste)
    documento_id = Column(UUID(as_uuid=True), nullable=True)
    documento_codigo = Column(String(30), nullable=True)
    motivo = Column(String(255), nullable=True)
    usuario_nombre = Column(String, nullable=True)

    insumo = relationship("Insumo", back_populates="movimientos")
