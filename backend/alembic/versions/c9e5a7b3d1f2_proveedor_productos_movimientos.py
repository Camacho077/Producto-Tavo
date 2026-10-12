"""relación proveedor-productos y movimientos de inventario

Revision ID: c9e5a7b3d1f2
Revises: b8d4f2a1c3e5
Create Date: 2026-09-18 09:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9e5a7b3d1f2"
down_revision: Union[str, Sequence[str], None] = "b8d4f2a1c3e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "proveedor_productos",
        sa.Column("proveedor_id", sa.UUID(), nullable=False),
        sa.Column("producto_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["proveedor_id"], ["proveedores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("proveedor_id", "producto_id"),
    )
    op.create_index(op.f("ix_proveedor_productos_tenant_id"), "proveedor_productos", ["tenant_id"], unique=False)

    op.create_table(
        "movimientos_inventario",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("producto_id", sa.UUID(), nullable=False),
        sa.Column("tipo", sa.String(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("stock_resultante", sa.Integer(), nullable=False),
        sa.Column("documento_tipo", sa.String(), nullable=False),
        sa.Column("documento_id", sa.UUID(), nullable=False),
        sa.Column("documento_codigo", sa.String(), nullable=False),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["producto_id"], ["productos.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_movimientos_inventario_producto_id"), "movimientos_inventario", ["producto_id"], unique=False)
    op.create_index(op.f("ix_movimientos_inventario_tenant_id"), "movimientos_inventario", ["tenant_id"], unique=False)

    # Trazabilidad del stock ya existente: se registra como un movimiento de
    # ajuste inicial por producto, para que la suma de movimientos coincida
    # con el stock actual desde el primer día.
    op.execute(
        """
        INSERT INTO movimientos_inventario
            (id, producto_id, tipo, cantidad, stock_resultante, documento_tipo, documento_id, documento_codigo,
             usuario_nombre, tenant_id, created_at, updated_at)
        SELECT gen_random_uuid(), id, 'ajuste_inicial', stock, stock, 'ajuste', id, 'SALDO-INICIAL',
               'Migración', tenant_id, NOW(), NOW()
        FROM productos WHERE stock <> 0
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_movimientos_inventario_tenant_id"), table_name="movimientos_inventario")
    op.drop_index(op.f("ix_movimientos_inventario_producto_id"), table_name="movimientos_inventario")
    op.drop_table("movimientos_inventario")
    op.drop_index(op.f("ix_proveedor_productos_tenant_id"), table_name="proveedor_productos")
    op.drop_table("proveedor_productos")
