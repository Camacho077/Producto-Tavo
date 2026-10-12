"""fase 3: conteos físicos de la bodega

- conteos: cada conteo físico (consecutivo por empresa, motivo, usuario y
  valor total de la diferencia).
- conteo_items: por insumo, lo que decía el sistema, lo contado, la
  diferencia y su valor a costo. La diferencia queda además como movimiento
  "ajuste" en movimientos_insumo (documento_tipo = "conteo").

Revision ID: e3b1c2d3e4f5
Revises: d2a0b1c2d3e4
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e3b1c2d3e4f5"
down_revision = "d2a0b1c2d3e4"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "conteos",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("motivo", sa.String(length=255), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        sa.Column("valor_diferencia", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_conteos_tenant_id", "conteos", ["tenant_id"])
    op.create_index("ix_conteos_tenant_numero", "conteos", ["tenant_id", "numero"])

    op.create_table(
        "conteo_items",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("conteo_id", UUID, sa.ForeignKey("conteos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("insumo_id", UUID, sa.ForeignKey("insumos.id"), nullable=False),
        sa.Column("sistema", sa.Numeric(14, 3), nullable=False),
        sa.Column("contado", sa.Numeric(14, 3), nullable=False),
        sa.Column("diferencia", sa.Numeric(14, 3), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(14, 4), nullable=False),
        sa.Column("valor", sa.Numeric(14, 2), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False),
    )
    op.create_index("ix_conteo_items_tenant_id", "conteo_items", ["tenant_id"])
    op.create_index("ix_conteo_items_conteo", "conteo_items", ["conteo_id"])
    # Clave foránea sin índice propio en Postgres (regla de indices_de_listados).
    op.create_index("ix_conteo_items_insumo_id", "conteo_items", ["insumo_id"])


def downgrade() -> None:
    op.drop_table("conteo_items")
    op.drop_table("conteos")
