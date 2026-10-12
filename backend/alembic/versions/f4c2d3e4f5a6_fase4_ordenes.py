"""fase 4: órdenes de pedido con comanda (reemplazan a los pedidos)

- Tablas nuevas: ordenes (consecutivo por jornada), comandas (cada envío a
  cocina), orden_items (con lo que gastó de cada insumo) y orden_eventos.
- Se BORRAN pedidos, pedido_items y pedido_eventos: el pedido del ERP no
  tenía equivalente (no tocaba inventario ni tenía mesa ni comanda).
- Los roles guardados pasan su permiso "pedidos" a "ordenes" (mismas
  acciones que existan: ver, crear, editar, cambiar_estado).

Revision ID: f4c2d3e4f5a6
Revises: e3b1c2d3e4f5
Create Date: 2026-10-12
"""
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f4c2d3e4f5a6"
down_revision = "e3b1c2d3e4f5"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _tenant():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False)


def _tiempos():
    return [sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False)]


def _renombrar_permiso(de: str, a: str, acciones_validas: tuple[str, ...]) -> None:
    conexion = op.get_bind()
    for rol_id, permisos in conexion.execute(sa.text("SELECT id, permisos FROM roles")).fetchall():
        datos = permisos if isinstance(permisos, dict) else json.loads(permisos or "{}")
        if de not in datos:
            continue
        acciones = [x for x in datos.pop(de) if x in acciones_validas]
        if acciones:
            datos[a] = acciones
        conexion.execute(sa.text("UPDATE roles SET permisos = :p WHERE id = :id"), {"p": json.dumps(datos), "id": rol_id})


def upgrade() -> None:
    op.drop_table("pedido_eventos")
    op.drop_table("pedido_items")
    op.drop_table("pedidos")

    op.create_table(
        "ordenes",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("jornada", sa.Date(), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("origen", sa.String(12), nullable=False),
        sa.Column("mesa_id", UUID, sa.ForeignKey("mesas.id"), nullable=True),
        sa.Column("cliente_nombre", sa.String(80), nullable=True),
        sa.Column("cliente_telefono", sa.String(20), nullable=True),
        sa.Column("cliente_direccion", sa.String(150), nullable=True),
        sa.Column("nota", sa.String(200), nullable=True),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("mesero_id", UUID, sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("mesero_nombre", sa.String(), nullable=True),
        sa.Column("anulada_motivo", sa.String(200), nullable=True),
        sa.Column("cerrada_en", sa.DateTime(), nullable=True),
        *_tiempos(),
        sa.UniqueConstraint("tenant_id", "jornada", "numero", name="uq_ordenes_tenant_jornada_numero"),
    )
    op.create_index("ix_ordenes_tenant_id", "ordenes", ["tenant_id"])
    op.create_index("ix_ordenes_tenant_estado", "ordenes", ["tenant_id", "estado"])
    op.create_index("ix_ordenes_tenant_jornada", "ordenes", ["tenant_id", "jornada"])
    op.create_index("ix_ordenes_mesa", "ordenes", ["mesa_id"])
    op.create_index("ix_ordenes_mesero", "ordenes", ["mesero_id"])

    op.create_table(
        "comandas",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("orden_id", UUID, sa.ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(16), nullable=False),
        sa.Column("va_a_cocina", sa.Boolean(), nullable=False),
        sa.Column("tomada_en", sa.DateTime(), nullable=True),
        sa.Column("tomada_por", sa.String(), nullable=True),
        sa.Column("lista_en", sa.DateTime(), nullable=True),
        sa.Column("lista_por", sa.String(), nullable=True),
        sa.Column("entregada_en", sa.DateTime(), nullable=True),
        sa.Column("entregada_por", sa.String(), nullable=True),
        *_tiempos(),
    )
    op.create_index("ix_comandas_tenant_id", "comandas", ["tenant_id"])
    op.create_index("ix_comandas_orden", "comandas", ["orden_id"])
    op.create_index("ix_comandas_tenant_estado", "comandas", ["tenant_id", "estado"])

    op.create_table(
        "orden_items",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("orden_id", UUID, sa.ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("comanda_id", UUID, sa.ForeignKey("comandas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(12, 2), nullable=True),
        sa.Column("modificadores", sa.JSON(), nullable=False),
        sa.Column("nota", sa.String(120), nullable=True),
        sa.Column("va_a_cocina", sa.Boolean(), nullable=False),
        sa.Column("consumo", sa.JSON(), nullable=False),
        sa.Column("anulado", sa.Boolean(), nullable=False),
        sa.Column("anulado_motivo", sa.String(200), nullable=True),
        sa.Column("posicion", sa.Integer(), nullable=False),
    )
    op.create_index("ix_orden_items_tenant_id", "orden_items", ["tenant_id"])
    op.create_index("ix_orden_items_orden", "orden_items", ["orden_id"])
    op.create_index("ix_orden_items_comanda", "orden_items", ["comanda_id"])
    op.create_index("ix_orden_items_producto", "orden_items", ["producto_id"])

    op.create_table(
        "orden_eventos",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("orden_id", UUID, sa.ForeignKey("ordenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("nota", sa.String(250), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        *_tiempos(),
    )
    op.create_index("ix_orden_eventos_tenant_id", "orden_eventos", ["tenant_id"])
    op.create_index("ix_orden_eventos_orden", "orden_eventos", ["orden_id"])

    _renombrar_permiso("pedidos", "ordenes", ("ver", "crear", "editar", "cambiar_estado"))


def downgrade() -> None:
    _renombrar_permiso("ordenes", "pedidos", ("ver", "crear", "editar", "cambiar_estado"))
    op.drop_table("orden_eventos")
    op.drop_table("orden_items")
    op.drop_table("comandas")
    op.drop_table("ordenes")
    op.create_table(
        "pedidos",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("numero", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cliente_nombre", sa.String(), nullable=False),
        sa.Column("cliente_telefono", sa.String(), nullable=True),
        sa.Column("cliente_direccion", sa.String(), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.Column("fecha_entrega", sa.DateTime(), nullable=True),
        sa.Column("prioridad", sa.String(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("notas", sa.String(), nullable=True),
        *_tiempos(),
    )
    op.create_table(
        "pedido_items",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("pedido_id", UUID, sa.ForeignKey("pedidos.id"), nullable=False),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "pedido_eventos",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("pedido_id", UUID, sa.ForeignKey("pedidos.id"), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("nota", sa.String(), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        *_tiempos(),
    )
