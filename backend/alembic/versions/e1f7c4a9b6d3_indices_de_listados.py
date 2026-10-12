"""índices para los listados y el dashboard

Postgres crea un índice por la clave primaria y por cada restricción UNIQUE,
pero NO por las claves foráneas. Esta migración agrega:

1. Las claves foráneas que se recorren en cada join de un listado
   (`compra_items.compra_id`, `venta_items.venta_id`, …) y en los conteos
   que bloquean una eliminación (`productos.categoria_id`, `usuarios.rol_id`).
2. Índices compuestos que empiezan por `tenant_id`, porque TODA consulta de
   negocio filtra primero por empresa: `(tenant_id, estado, fecha)` para el
   dashboard y los listados filtrados, `(tenant_id, numero)` y
   `(tenant_id, nombre)` para el orden de cada listado, y
   `(tenant_id, activo, stock)` para el panel de avisos de inventario.

No se agregan índices sobre columnas por las que nadie filtra: cada índice
se paga en cada escritura.

Revision ID: e1f7c4a9b6d3
Revises: c9e5a7b3d1f2
Create Date: 2026-09-21 11:20:00

"""
from typing import Sequence, Union

from alembic import op

revision: str = "e1f7c4a9b6d3"
down_revision: Union[str, Sequence[str], None] = "c9e5a7b3d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (nombre del índice, tabla, columnas)
INDICES = [
    # ---- Compras ----
    ("ix_compras_tenant_estado_fecha", "compras", ["tenant_id", "estado", "fecha"]),
    ("ix_compras_tenant_numero", "compras", ["tenant_id", "numero"]),
    ("ix_compras_proveedor", "compras", ["proveedor_id"]),
    ("ix_compra_items_compra", "compra_items", ["compra_id"]),
    ("ix_compra_items_producto", "compra_items", ["producto_id"]),
    # ---- Productos e inventario ----
    ("ix_productos_tenant_activo_stock", "productos", ["tenant_id", "activo", "stock"]),
    ("ix_productos_tenant_nombre", "productos", ["tenant_id", "nombre"]),
    ("ix_productos_categoria", "productos", ["categoria_id"]),
    ("ix_productos_marca", "productos", ["marca_id"]),
    ("ix_movimientos_tenant_producto", "movimientos_inventario", ["tenant_id", "producto_id"]),
    # ---- Proveedores ----
    ("ix_proveedores_tenant_nombre", "proveedores", ["tenant_id", "nombre"]),
    ("ix_proveedor_productos_producto", "proveedor_productos", ["producto_id"]),
    # ---- Ventas ----
    ("ix_ventas_tenant_estado_fecha", "ventas", ["tenant_id", "estado", "fecha"]),
    ("ix_ventas_tenant_numero", "ventas", ["tenant_id", "numero"]),
    ("ix_venta_items_venta", "venta_items", ["venta_id"]),
    ("ix_venta_items_producto", "venta_items", ["producto_id"]),
    # ---- Pedidos ----
    ("ix_pedidos_tenant_estado", "pedidos", ["tenant_id", "estado"]),
    ("ix_pedidos_tenant_numero", "pedidos", ["tenant_id", "numero"]),
    ("ix_pedido_items_pedido", "pedido_items", ["pedido_id"]),
    ("ix_pedido_items_producto", "pedido_items", ["producto_id"]),
    ("ix_pedido_eventos_pedido", "pedido_eventos", ["pedido_id"]),
    # ---- Seguridad ----
    ("ix_usuarios_rol", "usuarios", ["rol_id"]),
]


def upgrade() -> None:
    for nombre, tabla, columnas in INDICES:
        op.create_index(nombre, tabla, columnas)


def downgrade() -> None:
    for nombre, tabla, _ in reversed(INDICES):
        op.drop_index(nombre, table_name=tabla)
