"""fase 1 restaurante: sin Marcas; datos del negocio, configuración, zonas, mesas e imágenes

- Se QUITA el módulo Marcas (2026-10-12): columna productos.marca_id, su
  índice, la tabla marcas y el permiso "marcas" guardado en los roles.
- Tenant: dirección, ciudad, teléfono, correo, logo y `configuracion` (JSON
  validado por ConfiguracionRestaurante).
- Tablas nuevas: imagenes (WebP ya procesado), zonas y mesas.

Revision ID: c1f0a1b2c3d4
Revises: b7c8d9e0f1a2
Create Date: 2026-10-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c1f0a1b2c3d4"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _columna_tenant():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False)


def upgrade() -> None:
    # --- Marcas fuera ------------------------------------------------------
    op.drop_index("ix_productos_marca", table_name="productos")
    op.drop_constraint("fk_productos_marca_id", "productos", type_="foreignkey")
    op.drop_column("productos", "marca_id")
    op.drop_table("marcas")
    # El permiso guardado en cada rol: un módulo que ya no existe no concede
    # nada (permisos_de_rol lo ignora), pero se limpia para no dejar basura.
    op.execute("UPDATE roles SET permisos = (permisos::jsonb - 'marcas')::json WHERE permisos::jsonb ? 'marcas'")

    # --- Datos del negocio y configuración ---------------------------------
    op.add_column("tenants", sa.Column("direccion", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("ciudad", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("telefono", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("correo", sa.String(), nullable=True))
    op.add_column("tenants", sa.Column("logo_id", UUID, nullable=True))
    op.add_column("tenants", sa.Column("configuracion", sa.JSON(), nullable=False, server_default="{}"))

    # --- Imágenes ----------------------------------------------------------
    op.create_table(
        "imagenes",
        sa.Column("id", UUID, primary_key=True),
        _columna_tenant(),
        sa.Column("uso", sa.String(length=20), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("tipo", sa.String(length=40), nullable=False, server_default="image/webp"),
        sa.Column("ancho", sa.Integer(), nullable=False),
        sa.Column("alto", sa.Integer(), nullable=False),
        sa.Column("bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_imagenes_tenant_id", "imagenes", ["tenant_id"])

    # --- Zonas y mesas -----------------------------------------------------
    op.create_table(
        "zonas",
        sa.Column("id", UUID, primary_key=True),
        _columna_tenant(),
        sa.Column("nombre", sa.String(length=40), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_zonas_tenant_nombre"),
    )
    op.create_index("ix_zonas_tenant_id", "zonas", ["tenant_id"])
    op.create_table(
        "mesas",
        sa.Column("id", UUID, primary_key=True),
        _columna_tenant(),
        sa.Column("nombre", sa.String(length=20), nullable=False),
        sa.Column("zona_id", UUID, sa.ForeignKey("zonas.id"), nullable=True),
        sa.Column("puestos", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_mesas_tenant_nombre"),
    )
    op.create_index("ix_mesas_tenant_id", "mesas", ["tenant_id"])
    op.create_index("ix_mesas_zona", "mesas", ["zona_id"])


def downgrade() -> None:
    op.drop_index("ix_mesas_zona", table_name="mesas")
    op.drop_index("ix_mesas_tenant_id", table_name="mesas")
    op.drop_table("mesas")
    op.drop_index("ix_zonas_tenant_id", table_name="zonas")
    op.drop_table("zonas")
    op.drop_index("ix_imagenes_tenant_id", table_name="imagenes")
    op.drop_table("imagenes")
    for columna in ("configuracion", "logo_id", "correo", "telefono", "ciudad", "direccion"):
        op.drop_column("tenants", columna)
    op.create_table(
        "marcas",
        sa.Column("id", UUID, primary_key=True),
        _columna_tenant(),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("descripcion", sa.String(), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_marcas_tenant_nombre"),
    )
    op.add_column("productos", sa.Column("marca_id", UUID, sa.ForeignKey("marcas.id"), nullable=True))
    op.create_index("ix_productos_marca", "productos", ["marca_id"])
