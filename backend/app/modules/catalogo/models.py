from sqlalchemy import JSON, Boolean, CheckConstraint, Column, Date, ForeignKey, Index, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid
from app.db.session import Base
# Las tablas a las que apuntan las claves foráneas tienen que estar en el
# registro aunque quien importe esto (un script, alembic) no las importe.
from app.modules.imagenes import models as _imagenes  # noqa: F401
from app.modules.inventario import models as _inventario  # noqa: F401

TIPOS_PRODUCTO = ("plato", "combo")
TIPOS_MODIFICADOR = ("sin", "extra")


class Categoria(Base, TenantMixin, TimestampMixin):
    """Sección de la carta ("Almuerzos", "Bebidas"). `orden` define el orden
    de las pestañas en la toma de pedidos."""
    __tablename__ = "categorias"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="uq_categorias_tenant_nombre"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)
    orden = Column(Integer, nullable=False, default=0, server_default="0")
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    productos = relationship("Producto", back_populates="categoria")


class Producto(Base, TenantMixin, TimestampMixin):
    """
    Lo que se vende: un PLATO (con su receta) o un COMBO (varios platos a un
    precio especial, con vigencia: las promociones para estudiantes).

    El producto NO tiene stock: lo que se gasta son los insumos de su receta
    (app/modules/inventario). `va_a_cocina` en False es la "venta directa"
    (una gaseosa): no sale en la comanda ni en la pantalla de cocina.
    `agotado_fecha` marca "agotado hoy" para UNA jornada sin desactivarlo:
    al día siguiente vuelve solo.
    """
    __tablename__ = "productos"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_productos_tenant_sku"),
        Index("ix_productos_tenant_nombre", "tenant_id", "nombre"),
        Index("ix_productos_tenant_activo", "tenant_id", "activo"),
        Index("ix_productos_categoria", "categoria_id"),
        CheckConstraint("tipo IN ('plato', 'combo')", name="ck_productos_tipo"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    tipo = Column(String(10), nullable=False, default="plato", server_default="plato")
    nombre = Column(String, nullable=False)
    # Código corto opcional (lo usaban las cajas registradoras). Único por
    # restaurante cuando existe.
    sku = Column(String, nullable=True)
    descripcion = Column(String, nullable=True)
    precio = Column(Numeric(12, 2), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    categoria_id = Column(UUID(as_uuid=True), ForeignKey("categorias.id"), nullable=True)
    imagen_id = Column(UUID(as_uuid=True), ForeignKey("imagenes.id", ondelete="SET NULL"), nullable=True)
    va_a_cocina = Column(Boolean, nullable=False, default=True, server_default="true")
    agotado_fecha = Column(Date, nullable=True)
    # Solo combos/promociones: vigencia y días de la semana (0 = lunes).
    vigente_desde = Column(Date, nullable=True)
    vigente_hasta = Column(Date, nullable=True)
    dias_semana = Column(JSON, nullable=True)

    categoria = relationship("Categoria", back_populates="productos")
    receta = relationship("RecetaItem", back_populates="producto", cascade="all, delete-orphan", order_by="RecetaItem.orden")
    modificadores = relationship(
        "Modificador", back_populates="producto", cascade="all, delete-orphan", order_by="[Modificador.tipo, Modificador.orden]"
    )
    componentes = relationship(
        "ComboItem", back_populates="combo", cascade="all, delete-orphan", foreign_keys="ComboItem.combo_id", order_by="ComboItem.orden"
    )


class RecetaItem(Base, TenantMixin):
    """Una línea de la receta: cuánto de un insumo lleva UNA porción del
    plato, en cualquier unidad compatible con la del insumo, más un
    porcentaje de merma opcional (lo que se pierde al pelar, limpiar o
    cocinar): se descuenta cantidad × (1 + merma)."""
    __tablename__ = "receta_items"
    __table_args__ = (
        Index("ix_receta_items_producto", "producto_id"),
        Index("ix_receta_items_insumo", "insumo_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id", ondelete="CASCADE"), nullable=False)
    insumo_id = Column(UUID(as_uuid=True), ForeignKey("insumos.id"), nullable=False)
    cantidad = Column(Numeric(14, 3), nullable=False)
    unidad = Column(String(10), nullable=False)
    merma_porcentaje = Column(Numeric(5, 2), nullable=False, default=0, server_default="0")
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    producto = relationship("Producto", back_populates="receta")
    insumo = relationship("Insumo")


class Modificador(Base, TenantMixin):
    """
    "SIN TOMATE" (gratis) o "EXTRA QUESO" (con precio) para un plato.
    Cada modificador mueve como mucho UN insumo:
      - extra: suma `cantidad` de `insumo_id` (su "receta");
      - sin: deja de descontar el insumo `insumo_id` de la receta del plato.
    """
    __tablename__ = "modificadores"
    __table_args__ = (
        Index("ix_modificadores_producto", "producto_id"),
        CheckConstraint("tipo IN ('sin', 'extra')", name="ck_modificadores_tipo"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id", ondelete="CASCADE"), nullable=False)
    tipo = Column(String(10), nullable=False)
    nombre = Column(String(60), nullable=False)
    precio = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    insumo_id = Column(UUID(as_uuid=True), ForeignKey("insumos.id"), nullable=True)
    cantidad = Column(Numeric(14, 3), nullable=True)
    unidad = Column(String(10), nullable=True)
    orden = Column(Integer, nullable=False, default=0, server_default="0")
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    producto = relationship("Producto", back_populates="modificadores")
    insumo = relationship("Insumo")


class ComboItem(Base, TenantMixin):
    """Un plato dentro de un combo, con su cantidad."""
    __tablename__ = "combo_items"
    __table_args__ = (
        Index("ix_combo_items_combo", "combo_id"),
        Index("ix_combo_items_producto", "producto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    combo_id = Column(UUID(as_uuid=True), ForeignKey("productos.id", ondelete="CASCADE"), nullable=False)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    orden = Column(Integer, nullable=False, default=0, server_default="0")

    combo = relationship("Producto", back_populates="componentes", foreign_keys=[combo_id])
    producto = relationship("Producto", foreign_keys=[producto_id])
