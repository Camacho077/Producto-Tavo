"""proveedor: tipo de persona, documento y representante legal

Revision ID: b8d4f2a1c3e5
Revises: a7c3e1b9d2f4
Create Date: 2026-09-17 09:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b8d4f2a1c3e5"
down_revision: Union[str, Sequence[str], None] = "a7c3e1b9d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNAS = (
    "tipo_documento", "numero_documento", "nombres", "apellidos",
    "razon_social", "representante_nombre", "representante_documento",
)


def upgrade() -> None:
    op.add_column("proveedores", sa.Column("tipo_persona", sa.String(), server_default="juridica", nullable=False))
    for col in COLUMNAS:
        op.add_column("proveedores", sa.Column(col, sa.String(), nullable=True))
    # Los proveedores existentes eran empresas con `nombre`: pasa a razón social.
    op.execute("UPDATE proveedores SET razon_social = nombre WHERE razon_social IS NULL")


def downgrade() -> None:
    for col in COLUMNAS:
        op.drop_column("proveedores", col)
    op.drop_column("proveedores", "tipo_persona")
