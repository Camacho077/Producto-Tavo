from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, Numeric, String, Table, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.session import Base
from app.db.mixins import TenantMixin, TimestampMixin, gen_uuid

# Relación muchos a muchos: un proveedor surte varios productos y un producto
# puede venir de varios proveedores. Lleva tenant_id como toda tabla de negocio.
proveedor_productos = Table(
    "proveedor_productos",
    Base.metadata,
    Column("proveedor_id", UUID(as_uuid=True), ForeignKey("proveedores.id", ondelete="CASCADE"), primary_key=True),
    Column("producto_id", UUID(as_uuid=True), ForeignKey("productos.id", ondelete="CASCADE"), primary_key=True),
    Column("tenant_id", UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True),
    # La clave primaria ya cubre (proveedor_id, producto_id); este índice es
    # para el camino contrario: GET /compras/productos?proveedor_id= y el
    # listado de proveedores de un producto.
    Index("ix_proveedor_productos_producto", "producto_id"),
)

# Tipos de movimiento de inventario. `cantidad` va con signo: positiva suma
# stock, negativa lo resta. El stock de un producto es la suma de sus movimientos.
TIPOS_MOVIMIENTO = ("compra", "anulacion_compra", "venta", "anulacion_venta")

# pendiente: registrada, todavía no afecta stock. confirmada: el stock subió.
# cancelada: se descartó estando pendiente. anulada: se revirtió una compra
# confirmada (el stock vuelve a bajar).
ESTADOS_COMPRA = ("pendiente", "confirmada", "cancelada", "anulada")


class Categoria(Base, TenantMixin, TimestampMixin):
    __tablename__ = "categorias"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="uq_categorias_tenant_nombre"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)
    activo = Column(Boolean, nullable=False, default=True, server_default="true")

    productos = relationship("Producto", back_populates="categoria")


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
    # en services.sincronizar_productos_proveedor.
    productos = relationship("Producto", secondary=proveedor_productos, back_populates="proveedores", viewonly=True)


class Producto(Base, TenantMixin, TimestampMixin):
    __tablename__ = "productos"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku", name="uq_productos_tenant_sku"),
        # Listado filtrado por estado y el panel de avisos (agotados y bajo
        # mínimo) piden siempre tenant + activo + stock.
        Index("ix_productos_tenant_activo_stock", "tenant_id", "activo", "stock"),
        # Orden alfabético del listado dentro de la empresa.
        Index("ix_productos_tenant_nombre", "tenant_id", "nombre"),
        # Postgres NO indexa las claves foráneas solo: se usa en el conteo
        # por categoría y al bloquear su eliminación.
        Index("ix_productos_categoria", "categoria_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    nombre = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    descripcion = Column(String, nullable=True)
    precio = Column(Numeric(12, 2), nullable=False)
    # Último precio al que se compró: sirve de sugerencia al registrar compras.
    precio_compra = Column(Numeric(12, 2), nullable=True)
    stock = Column(Integer, nullable=False, default=0)
    stock_minimo = Column(Integer, nullable=False, default=0, server_default="0")
    activo = Column(Boolean, nullable=False, default=True)
    categoria_id = Column(UUID(as_uuid=True), ForeignKey("categorias.id"), nullable=True)

    categoria = relationship("Categoria", back_populates="productos")
    proveedores = relationship("Proveedor", secondary=proveedor_productos, back_populates="productos", viewonly=True)
    movimientos = relationship("MovimientoInventario", back_populates="producto", order_by="MovimientoInventario.created_at.desc()")


class MovimientoInventario(Base, TenantMixin, TimestampMixin):
    """
    Trazabilidad del stock: cada compra confirmada, venta completada o
    anulación deja un movimiento. `Producto.stock` es un acumulado de
    conveniencia; siempre debe coincidir con la suma de `cantidad`.
    """
    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        # Historial de un producto: GET /compras/productos/{id}/movimientos.
        Index("ix_movimientos_tenant_producto", "tenant_id", "producto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False, index=True)
    tipo = Column(String, nullable=False)  # ver TIPOS_MOVIMIENTO
    cantidad = Column(Integer, nullable=False)  # con signo
    stock_resultante = Column(Integer, nullable=False)
    documento_tipo = Column(String, nullable=False)  # compra | venta
    documento_id = Column(UUID(as_uuid=True), nullable=False)
    documento_codigo = Column(String, nullable=False)  # COM-000001 / VEN-000001
    usuario_nombre = Column(String, nullable=True)

    producto = relationship("Producto", back_populates="movimientos")


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
    __tablename__ = "compra_items"
    __table_args__ = (
        # Las dos se recorren en cada join del listado de compras.
        Index("ix_compra_items_compra", "compra_id"),
        Index("ix_compra_items_producto", "producto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    compra_id = Column(UUID(as_uuid=True), ForeignKey("compras.id"), nullable=False)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)

    compra = relationship("Compra", back_populates="items")
    producto = relationship("Producto")
