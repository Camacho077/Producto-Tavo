"""fase 2: carta con recetas, modificadores y combos; inventario de INSUMOS

El inventario deja de ser de productos y pasa a los insumos (un plato no se
"tiene en bodega": se prepara con sus insumos).

- productos: sin stock, stock_minimo ni precio_compra; sku opcional; tipo
  (plato | combo), imagen, va_a_cocina, agotado_fecha y vigencia.
- categorias: orden.
- Tablas nuevas: insumos, movimientos_insumo, receta_items, modificadores,
  combo_items, proveedor_insumos.
- Se BORRAN movimientos_inventario y proveedor_productos (stock de productos).
- compra_items pasa de producto a insumo (cantidad decimal y unidad). Las
  compras que había eran de productos de reventa y no tienen equivalente en
  insumos: se eliminan (2026-10-12: el producto todavía no tiene datos de
  ningún restaurante; solo demostraciones).
- venta_items: costo_unitario (costo por receta en el momento de la venta).

Revision ID: d2a0b1c2d3e4
Revises: c1f0a1b2c3d4
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d2a0b1c2d3e4"
down_revision = "c1f0a1b2c3d4"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _tenant():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False)


def _tiempos():
    return [sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False)]


def upgrade() -> None:
    # --- Lo que era stock de productos se va -------------------------------
    op.drop_table("movimientos_inventario")
    op.drop_table("proveedor_productos")
    op.execute("DELETE FROM compra_items")
    op.execute("DELETE FROM compras")

    # --- Carta -------------------------------------------------------------
    op.add_column("categorias", sa.Column("orden", sa.Integer(), nullable=False, server_default="0"))

    op.drop_index("ix_productos_tenant_activo_stock", table_name="productos")
    for columna in ("stock", "stock_minimo", "precio_compra"):
        op.drop_column("productos", columna)
    op.alter_column("productos", "sku", existing_type=sa.String(), nullable=True)
    op.add_column("productos", sa.Column("tipo", sa.String(length=10), nullable=False, server_default="plato"))
    op.add_column("productos", sa.Column("imagen_id", UUID, sa.ForeignKey("imagenes.id", ondelete="SET NULL"), nullable=True))
    op.add_column("productos", sa.Column("va_a_cocina", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("productos", sa.Column("agotado_fecha", sa.Date(), nullable=True))
    op.add_column("productos", sa.Column("vigente_desde", sa.Date(), nullable=True))
    op.add_column("productos", sa.Column("vigente_hasta", sa.Date(), nullable=True))
    op.add_column("productos", sa.Column("dias_semana", sa.JSON(), nullable=True))
    op.create_check_constraint("ck_productos_tipo", "productos", "tipo IN ('plato', 'combo')")
    op.create_index("ix_productos_tenant_activo", "productos", ["tenant_id", "activo"])

    # --- Insumos y sus movimientos -----------------------------------------
    op.create_table(
        "insumos",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("unidad", sa.String(length=10), nullable=False),
        sa.Column("grupo", sa.String(length=40), nullable=True),
        sa.Column("existencia", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("minimo", sa.Numeric(14, 3), nullable=False, server_default="0"),
        sa.Column("costo_unitario", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        *_tiempos(),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_insumos_tenant_nombre"),
    )
    op.create_index("ix_insumos_tenant_id", "insumos", ["tenant_id"])
    op.create_index("ix_insumos_tenant_activo", "insumos", ["tenant_id", "activo"])

    op.create_table(
        "movimientos_insumo",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("insumo_id", UUID, sa.ForeignKey("insumos.id"), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 3), nullable=False),
        sa.Column("existencia_resultante", sa.Numeric(14, 3), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(14, 4), nullable=False, server_default="0"),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("documento_tipo", sa.String(length=20), nullable=True),
        sa.Column("documento_id", UUID, nullable=True),
        sa.Column("documento_codigo", sa.String(length=30), nullable=True),
        sa.Column("motivo", sa.String(length=255), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        *_tiempos(),
    )
    op.create_index("ix_movimientos_insumo_tenant_id", "movimientos_insumo", ["tenant_id"])
    op.create_index("ix_movimientos_insumo_tenant_insumo", "movimientos_insumo", ["tenant_id", "insumo_id"])
    op.create_index("ix_movimientos_insumo_documento", "movimientos_insumo", ["documento_id"])
    op.create_index("ix_movimientos_insumo_tenant_tipo_fecha", "movimientos_insumo", ["tenant_id", "tipo", "created_at"])

    # --- Recetas, modificadores y combos -----------------------------------
    op.create_table(
        "receta_items",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("insumo_id", UUID, sa.ForeignKey("insumos.id"), nullable=False),
        sa.Column("cantidad", sa.Numeric(14, 3), nullable=False),
        sa.Column("unidad", sa.String(length=10), nullable=False),
        sa.Column("merma_porcentaje", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_receta_items_tenant_id", "receta_items", ["tenant_id"])
    op.create_index("ix_receta_items_producto", "receta_items", ["producto_id"])
    op.create_index("ix_receta_items_insumo", "receta_items", ["insumo_id"])

    op.create_table(
        "modificadores",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(length=10), nullable=False),
        sa.Column("nombre", sa.String(length=60), nullable=False),
        sa.Column("precio", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("insumo_id", UUID, sa.ForeignKey("insumos.id"), nullable=True),
        sa.Column("cantidad", sa.Numeric(14, 3), nullable=True),
        sa.Column("unidad", sa.String(length=10), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.CheckConstraint("tipo IN ('sin', 'extra')", name="ck_modificadores_tipo"),
    )
    op.create_index("ix_modificadores_tenant_id", "modificadores", ["tenant_id"])
    op.create_index("ix_modificadores_producto", "modificadores", ["producto_id"])

    op.create_table(
        "combo_items",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("combo_id", UUID, sa.ForeignKey("productos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_combo_items_tenant_id", "combo_items", ["tenant_id"])
    op.create_index("ix_combo_items_combo", "combo_items", ["combo_id"])
    op.create_index("ix_combo_items_producto", "combo_items", ["producto_id"])

    # --- Proveedores ↔ insumos ---------------------------------------------
    op.create_table(
        "proveedor_insumos",
        sa.Column("proveedor_id", UUID, sa.ForeignKey("proveedores.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("insumo_id", UUID, sa.ForeignKey("insumos.id", ondelete="CASCADE"), primary_key=True),
        _tenant(),
    )
    op.create_index("ix_proveedor_insumos_tenant_id", "proveedor_insumos", ["tenant_id"])
    op.create_index("ix_proveedor_insumos_insumo", "proveedor_insumos", ["insumo_id"])

    # --- Compras de insumos ------------------------------------------------
    op.drop_index("ix_compra_items_producto", table_name="compra_items")
    op.drop_constraint("compra_items_producto_id_fkey", "compra_items", type_="foreignkey")
    op.drop_column("compra_items", "producto_id")
    op.add_column("compra_items", sa.Column("insumo_id", UUID, sa.ForeignKey("insumos.id"), nullable=False))
    op.add_column("compra_items", sa.Column("unidad", sa.String(length=10), nullable=False))
    op.alter_column("compra_items", "cantidad", existing_type=sa.Integer(), type_=sa.Numeric(14, 3))
    op.create_index("ix_compra_items_insumo", "compra_items", ["insumo_id"])

    # --- Costo de lo vendido -----------------------------------------------
    op.add_column("venta_items", sa.Column("costo_unitario", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("venta_items", "costo_unitario")
    op.execute("DELETE FROM compra_items")
    op.execute("DELETE FROM compras")
    op.drop_index("ix_compra_items_insumo", table_name="compra_items")
    op.alter_column("compra_items", "cantidad", existing_type=sa.Numeric(14, 3), type_=sa.Integer())
    op.drop_column("compra_items", "unidad")
    op.drop_column("compra_items", "insumo_id")
    op.add_column("compra_items", sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False))
    op.create_index("ix_compra_items_producto", "compra_items", ["producto_id"])
    for tabla in ("proveedor_insumos", "combo_items", "modificadores", "receta_items", "movimientos_insumo", "insumos"):
        op.drop_table(tabla)
    op.drop_index("ix_productos_tenant_activo", table_name="productos")
    op.drop_constraint("ck_productos_tipo", "productos", type_="check")
    for columna in ("dias_semana", "vigente_hasta", "vigente_desde", "agotado_fecha", "va_a_cocina", "imagen_id", "tipo"):
        op.drop_column("productos", columna)
    op.execute("UPDATE productos SET sku = 'P-' || substr(id::text, 1, 8) WHERE sku IS NULL")
    op.alter_column("productos", "sku", existing_type=sa.String(), nullable=False)
    op.add_column("productos", sa.Column("stock", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("productos", sa.Column("stock_minimo", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("productos", sa.Column("precio_compra", sa.Numeric(12, 2), nullable=True))
    op.create_index("ix_productos_tenant_activo_stock", "productos", ["tenant_id", "activo", "stock"])
    op.drop_column("categorias", "orden")
    op.create_table(
        "proveedor_productos",
        sa.Column("proveedor_id", UUID, sa.ForeignKey("proveedores.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id", ondelete="CASCADE"), primary_key=True),
        _tenant(),
    )
    op.create_table(
        "movimientos_inventario",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("stock_resultante", sa.Integer(), nullable=False),
        sa.Column("documento_tipo", sa.String(), nullable=False),
        sa.Column("documento_id", UUID, nullable=False),
        sa.Column("documento_codigo", sa.String(), nullable=False),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        *_tiempos(),
    )
