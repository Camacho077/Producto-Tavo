"""marcas, pedidos con seguimiento, permisos JSON, estado en catálogos

Revision ID: a7c3e1b9d2f4
Revises: f2ac75939c74
Create Date: 2026-09-16 12:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "a7c3e1b9d2f4"
down_revision: Union[str, Sequence[str], None] = "f2ac75939c74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- Marcas (modelo nuevo) ----------
    op.create_table(
        "marcas",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_marcas_tenant_nombre"),
    )
    op.create_index(op.f("ix_marcas_tenant_id"), "marcas", ["tenant_id"], unique=False)

    # ---------- Catálogos: estado activo/inactivo ----------
    op.add_column("categorias", sa.Column("activo", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("proveedores", sa.Column("direccion", sa.String(), nullable=True))
    op.add_column("proveedores", sa.Column("activo", sa.Boolean(), server_default="true", nullable=False))

    # ---------- Productos: marca, descripción, precio de compra, stock mínimo ----------
    op.add_column("productos", sa.Column("descripcion", sa.String(), nullable=True))
    op.add_column("productos", sa.Column("precio_compra", sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column("productos", sa.Column("stock_minimo", sa.Integer(), server_default="0", nullable=False))
    op.add_column("productos", sa.Column("marca_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_productos_marca_id", "productos", "marcas", ["marca_id"], ["id"])

    # ---------- Compras / Ventas: consecutivo y notas ----------
    op.add_column("compras", sa.Column("numero", sa.Integer(), server_default="0", nullable=False))
    op.add_column("compras", sa.Column("notas", sa.String(), nullable=True))
    op.add_column("ventas", sa.Column("numero", sa.Integer(), server_default="0", nullable=False))
    op.add_column("ventas", sa.Column("cliente_documento", sa.String(), nullable=True))
    op.add_column("ventas", sa.Column("notas", sa.String(), nullable=True))
    # Numerar lo que ya existe, por tenant y en orden de creación.
    for tabla in ("compras", "ventas"):
        op.execute(
            f"""
            UPDATE {tabla} t SET numero = n.numero
            FROM (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY tenant_id ORDER BY created_at, id) AS numero
                FROM {tabla}
            ) n
            WHERE t.id = n.id
            """
        )

    # ---------- Pedidos con línea de tiempo ----------
    op.create_table(
        "pedidos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("numero", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cliente_nombre", sa.String(), nullable=False),
        sa.Column("cliente_telefono", sa.String(), nullable=True),
        sa.Column("cliente_direccion", sa.String(), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.Column("fecha_entrega", sa.DateTime(), nullable=True),
        sa.Column("prioridad", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("notas", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pedidos_tenant_id"), "pedidos", ["tenant_id"], unique=False)

    op.create_table(
        "pedido_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pedido_id", sa.UUID(), nullable=False),
        sa.Column("producto_id", sa.UUID(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"]),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pedido_items_tenant_id"), "pedido_items", ["tenant_id"], unique=False)

    op.create_table(
        "pedido_eventos",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pedido_id", sa.UUID(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["pedido_id"], ["pedidos.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pedido_eventos_tenant_id"), "pedido_eventos", ["tenant_id"], unique=False)

    # ---------- Roles: permisos pasan de texto a JSON ----------
    op.execute("ALTER TABLE roles ALTER COLUMN permisos DROP DEFAULT")
    op.execute(
        "ALTER TABLE roles ALTER COLUMN permisos TYPE JSON "
        "USING CASE WHEN permisos IS NULL OR permisos = '' THEN '{}'::json ELSE permisos::json END"
    )
    op.execute("ALTER TABLE roles ALTER COLUMN permisos SET DEFAULT '{}'::json")


def downgrade() -> None:
    op.execute("ALTER TABLE roles ALTER COLUMN permisos DROP DEFAULT")
    op.execute("ALTER TABLE roles ALTER COLUMN permisos TYPE VARCHAR USING permisos::text")
    op.execute("ALTER TABLE roles ALTER COLUMN permisos SET DEFAULT '{}'")

    op.drop_index(op.f("ix_pedido_eventos_tenant_id"), table_name="pedido_eventos")
    op.drop_table("pedido_eventos")
    op.drop_index(op.f("ix_pedido_items_tenant_id"), table_name="pedido_items")
    op.drop_table("pedido_items")
    op.drop_index(op.f("ix_pedidos_tenant_id"), table_name="pedidos")
    op.drop_table("pedidos")

    op.drop_column("ventas", "notas")
    op.drop_column("ventas", "cliente_documento")
    op.drop_column("ventas", "numero")
    op.drop_column("compras", "notas")
    op.drop_column("compras", "numero")

    op.drop_constraint("fk_productos_marca_id", "productos", type_="foreignkey")
    op.drop_column("productos", "marca_id")
    op.drop_column("productos", "stock_minimo")
    op.drop_column("productos", "precio_compra")
    op.drop_column("productos", "descripcion")

    op.drop_column("proveedores", "activo")
    op.drop_column("proveedores", "direccion")
    op.drop_column("categorias", "activo")

    op.drop_index(op.f("ix_marcas_tenant_id"), table_name="marcas")
    op.drop_table("marcas")
