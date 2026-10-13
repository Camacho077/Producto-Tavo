"""fase 6: caja (cobros con comprobante interno, apertura y cierre) y gastos

- ventas y venta_items se RECREAN: la venta deja de ser un documento suelto
  del ERP y pasa a ser el cobro de una orden (con caja, cajero, base,
  impuesto al consumo, propina y datos del cliente para una futura factura
  electrónica). Las ventas de demostración anteriores se pierden (2026-10-12:
  el producto aún no tiene datos de ningún restaurante; el seed las recrea).
  Sus movimientos de inventario se conservan: la existencia es la suma de
  los movimientos y no debe cambiar.
- Tablas nuevas: cajas, venta_pagos, gastos.
- orden_items.venta_id: qué cobro pagó cada plato (None = por cobrar).
- Roles: la acción "cambiar_estado" de ventas pasa a "caja" (abrir y
  cerrar), y quien veía ventas ve también la caja.

Revision ID: a6d4e5f6a7b8
Revises: f4c2d3e4f5a6
Create Date: 2026-10-12
"""
import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a6d4e5f6a7b8"
down_revision = "f4c2d3e4f5a6"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def _tenant():
    return sa.Column("tenant_id", UUID, sa.ForeignKey("tenants.id"), nullable=False)


def _tiempos():
    return [sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False)]


def _permisos_de_caja() -> None:
    conexion = op.get_bind()
    for rol_id, permisos in conexion.execute(sa.text("SELECT id, permisos FROM roles")).fetchall():
        datos = permisos if isinstance(permisos, dict) else json.loads(permisos or "{}")
        ventas = datos.get("ventas")
        if not ventas:
            continue
        caja = (["ver"] if "ver" in ventas else []) + (["cambiar_estado"] if "cambiar_estado" in ventas else [])
        datos["ventas"] = [a for a in ventas if a in ("ver", "crear", "anular")]
        if caja:
            datos["caja"] = caja
        conexion.execute(sa.text("UPDATE roles SET permisos = :p WHERE id = :id"), {"p": json.dumps(datos), "id": rol_id})


def upgrade() -> None:
    op.drop_table("venta_items")
    op.drop_table("ventas")

    op.create_table(
        "cajas",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(10), nullable=False),
        sa.Column("abierta_en", sa.DateTime(), nullable=False),
        sa.Column("abierta_por_id", UUID, sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("abierta_por", sa.String(), nullable=True),
        sa.Column("base_inicial", sa.Numeric(12, 2), nullable=False),
        sa.Column("cerrada_en", sa.DateTime(), nullable=True),
        sa.Column("cerrada_por_id", UUID, sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("cerrada_por", sa.String(), nullable=True),
        sa.Column("esperado", sa.JSON(), nullable=True),
        sa.Column("contado", sa.JSON(), nullable=True),
        sa.Column("diferencia", sa.Numeric(12, 2), nullable=True),
        sa.Column("motivo_diferencia", sa.String(250), nullable=True),
        *_tiempos(),
    )
    op.create_index("ix_cajas_tenant_id", "cajas", ["tenant_id"])
    op.create_index("ix_cajas_tenant_estado", "cajas", ["tenant_id", "estado"])
    op.create_index("ix_cajas_tenant_numero", "cajas", ["tenant_id", "numero"])

    op.create_table(
        "ventas",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("numero", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False),
        sa.Column("orden_id", UUID, sa.ForeignKey("ordenes.id"), nullable=False),
        sa.Column("caja_id", UUID, sa.ForeignKey("cajas.id"), nullable=False),
        sa.Column("cajero_id", UUID, sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("cajero_nombre", sa.String(), nullable=True),
        sa.Column("cliente_nombre", sa.String(80), nullable=True),
        sa.Column("cliente_documento_tipo", sa.String(4), nullable=True),
        sa.Column("cliente_documento", sa.String(20), nullable=True),
        sa.Column("cliente_correo", sa.String(120), nullable=True),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("impuesto", sa.Numeric(12, 2), nullable=False),
        sa.Column("impuesto_tasa", sa.Numeric(5, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("propina", sa.Numeric(12, 2), nullable=False),
        sa.Column("anulada_motivo", sa.String(200), nullable=True),
        sa.Column("fe_estado", sa.String(20), nullable=True),
        sa.Column("fe_cufe", sa.String(120), nullable=True),
        *_tiempos(),
    )
    op.create_index("ix_ventas_tenant_id", "ventas", ["tenant_id"])
    op.create_index("ix_ventas_tenant_estado_fecha", "ventas", ["tenant_id", "estado", "fecha"])
    op.create_index("ix_ventas_tenant_numero", "ventas", ["tenant_id", "numero"])
    op.create_index("ix_ventas_orden", "ventas", ["orden_id"])
    op.create_index("ix_ventas_caja", "ventas", ["caja_id"])

    op.create_table(
        "venta_items",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("venta_id", UUID, sa.ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("orden_item_id", UUID, sa.ForeignKey("orden_items.id"), nullable=True),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("nombre", sa.String(), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index("ix_venta_items_tenant_id", "venta_items", ["tenant_id"])
    op.create_index("ix_venta_items_venta", "venta_items", ["venta_id"])
    op.create_index("ix_venta_items_producto", "venta_items", ["producto_id"])

    op.create_table(
        "venta_pagos",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("venta_id", UUID, sa.ForeignKey("ventas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("medio", sa.String(15), nullable=False),
        sa.Column("monto", sa.Numeric(12, 2), nullable=False),
        sa.Column("recibido", sa.Numeric(12, 2), nullable=True),
        sa.Column("cambio", sa.Numeric(12, 2), nullable=True),
    )
    op.create_index("ix_venta_pagos_tenant_id", "venta_pagos", ["tenant_id"])
    op.create_index("ix_venta_pagos_venta", "venta_pagos", ["venta_id"])

    op.add_column("orden_items", sa.Column("venta_id", UUID, nullable=True))
    op.create_foreign_key("fk_orden_items_venta", "orden_items", "ventas", ["venta_id"], ["id"])
    op.create_index("ix_orden_items_venta", "orden_items", ["venta_id"])

    op.create_table(
        "gastos",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("descripcion", sa.String(150), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("medio_pago", sa.String(15), nullable=False),
        sa.Column("caja_id", UUID, sa.ForeignKey("cajas.id"), nullable=True),
        sa.Column("usuario_nombre", sa.String(), nullable=True),
        *_tiempos(),
    )
    op.create_index("ix_gastos_tenant_id", "gastos", ["tenant_id"])
    op.create_index("ix_gastos_tenant_fecha", "gastos", ["tenant_id", "fecha"])
    op.create_index("ix_gastos_caja", "gastos", ["caja_id"])

    _permisos_de_caja()


def downgrade() -> None:
    op.drop_table("gastos")
    op.drop_index("ix_orden_items_venta", table_name="orden_items")
    op.drop_constraint("fk_orden_items_venta", "orden_items", type_="foreignkey")
    op.drop_column("orden_items", "venta_id")
    op.drop_table("venta_pagos")
    op.drop_table("venta_items")
    op.drop_table("ventas")
    op.drop_table("cajas")
    op.create_table(
        "ventas",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("numero", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cliente_nombre", sa.String(), nullable=False),
        sa.Column("cliente_documento", sa.String(), nullable=True),
        sa.Column("fecha", sa.DateTime(), nullable=False),
        sa.Column("estado", sa.String(), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("notas", sa.String(), nullable=True),
        *_tiempos(),
    )
    op.create_table(
        "venta_items",
        sa.Column("id", UUID, primary_key=True),
        _tenant(),
        sa.Column("venta_id", UUID, sa.ForeignKey("ventas.id"), nullable=False),
        sa.Column("producto_id", UUID, sa.ForeignKey("productos.id"), nullable=False),
        sa.Column("cantidad", sa.Integer(), nullable=False),
        sa.Column("precio_unitario", sa.Numeric(12, 2), nullable=False),
        sa.Column("costo_unitario", sa.Numeric(12, 2), nullable=True),
    )
