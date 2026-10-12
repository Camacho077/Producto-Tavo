"""aceptaciones legales: prueba de la autorización de tratamiento de datos

Ley 1581 de 2012 (art. 9) y Decreto 1377 de 2013 (art. 7): quien registra
una empresa acepta la Política de tratamiento de datos y los Términos; se
guarda qué versión aceptó y en qué fecha y hora. Las empresas creadas antes
de esta migración no tienen fila: su aceptación se recoge fuera del producto
(contrato) o en una futura pantalla de "acepta la nueva versión".

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-30
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "aceptaciones_legales",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("documento", sa.String(length=40), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("aceptada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_aceptaciones_legales_tenant_id", "aceptaciones_legales", ["tenant_id"])
    op.create_index("ix_aceptaciones_legales_usuario", "aceptaciones_legales", ["usuario_id"])


def downgrade() -> None:
    op.drop_index("ix_aceptaciones_legales_usuario", table_name="aceptaciones_legales")
    op.drop_index("ix_aceptaciones_legales_tenant_id", table_name="aceptaciones_legales")
    op.drop_table("aceptaciones_legales")
