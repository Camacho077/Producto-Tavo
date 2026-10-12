"""permisos por rol: rol administrador, catálogo por módulo y roles de ejemplo

1. `roles.es_administrador`: el rol con acceso total. Se marca en los roles
   llamados "Administrador" (los que crea el registro de cada empresa).
2. Los permisos pasan de 5 módulos gruesos (compras, ventas, seguridad…) a los
   módulos reales del sistema (compras, productos, categorías, marcas,
   proveedores, ventas, pedidos, usuarios, roles, dashboard, ia), cada uno
   con sus acciones (ver, crear, editar, cambiar_estado, anular, eliminar).
   Un permiso viejo se traduce al módulo nuevo sin conceder nada que no
   tuviera: `editar` en el viejo da `cambiar_estado` en el nuevo y
   `eliminar` da `anular` donde esa acción existe.
3. Cada empresa recibe los roles de ejemplo Cajero y Bodega si no los tiene.

Los valores están CONGELADOS aquí (no se importan de la app): una migración
debe hacer siempre lo mismo aunque el catálogo cambie después.

Revision ID: a1b2c3d4e5f6
Revises: e1f7c4a9b6d3
Create Date: 2026-09-30 09:00:00
"""
import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e1f7c4a9b6d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACCIONES = {
    "dashboard": ["ver"],
    "compras": ["ver", "crear", "cambiar_estado", "anular"],
    "productos": ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
    "categorias": ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
    "marcas": ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
    "proveedores": ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
    "ventas": ["ver", "crear", "cambiar_estado", "anular"],
    "pedidos": ["ver", "crear", "editar", "cambiar_estado"],
    "usuarios": ["ver", "crear", "editar", "cambiar_estado", "eliminar"],
    "roles": ["ver", "crear", "editar", "eliminar"],
    "ia": ["ver"],
}
# módulo viejo -> módulos nuevos que cubría
DE_VIEJO_A_NUEVO = {
    "dashboard": ["dashboard"],
    "compras": ["compras", "productos", "categorias", "marcas", "proveedores"],
    "ventas": ["ventas", "pedidos"],
    "seguridad": ["usuarios", "roles"],
    "ia": ["ia"],
}
ROLES_DE_EJEMPLO = {
    "Cajero": (
        "Registra ventas y atiende pedidos. No ve compras, costos ni márgenes.",
        {
            "ventas": ["ver", "crear", "cambiar_estado"],
            "pedidos": ["ver", "crear", "editar", "cambiar_estado"],
            "productos": ["ver"],
            "categorias": ["ver"],
            "marcas": ["ver"],
        },
    ),
    "Bodega": (
        "Recibe compras y mantiene el catálogo. No vende ni ve el dashboard.",
        {
            "compras": ["ver", "crear", "cambiar_estado"],
            "productos": ["ver", "crear", "editar", "cambiar_estado"],
            "categorias": ["ver", "crear", "editar"],
            "marcas": ["ver", "crear", "editar"],
            "proveedores": ["ver"],
            "pedidos": ["ver"],
        },
    ),
}


def _traducir(viejos: dict) -> dict:
    nuevos: dict[str, set] = {}
    for modulo_viejo, acciones in (viejos or {}).items():
        if not isinstance(acciones, list):
            continue
        if modulo_viejo in ACCIONES and modulo_viejo not in DE_VIEJO_A_NUEVO:
            destinos = [modulo_viejo]
        else:
            destinos = DE_VIEJO_A_NUEVO.get(modulo_viejo, [])
        for destino in destinos:
            posibles = ACCIONES[destino]
            concedidas = {a for a in acciones if a in posibles}
            if "editar" in acciones and "cambiar_estado" in posibles:
                concedidas.add("cambiar_estado")
            if "eliminar" in acciones and "anular" in posibles:
                concedidas.add("anular")
            if concedidas:
                nuevos.setdefault(destino, set()).update(concedidas)
    return {m: [a for a in ACCIONES[m] if a in acc] for m, acc in nuevos.items()}


def upgrade() -> None:
    op.add_column(
        "roles",
        sa.Column("es_administrador", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    conn = op.get_bind()
    conn.execute(sa.text("UPDATE roles SET es_administrador = true WHERE lower(trim(nombre)) = 'administrador'"))

    for rol_id, permisos in conn.execute(sa.text("SELECT id, permisos FROM roles")).all():
        viejos = permisos if isinstance(permisos, dict) else json.loads(permisos or "{}")
        conn.execute(
            sa.text("UPDATE roles SET permisos = CAST(:p AS json) WHERE id = :id"),
            {"p": json.dumps(_traducir(viejos)), "id": rol_id},
        )

    for (tenant_id,) in conn.execute(sa.text("SELECT id FROM tenants")).all():
        existentes = {
            n.lower()
            for (n,) in conn.execute(sa.text("SELECT nombre FROM roles WHERE tenant_id = :t"), {"t": tenant_id}).all()
        }
        for nombre, (descripcion, permisos) in ROLES_DE_EJEMPLO.items():
            if nombre.lower() in existentes:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO roles (id, tenant_id, nombre, descripcion, permisos, es_administrador, created_at, updated_at) "
                    "VALUES (:id, :t, :n, :d, CAST(:p AS json), false, now(), now())"
                ),
                {"id": uuid.uuid4(), "t": tenant_id, "n": nombre, "d": descripcion, "p": json.dumps(permisos)},
            )


def downgrade() -> None:
    # Los permisos traducidos no se reconvierten al formato viejo (ese formato
    # no podía expresar la mayoría de estas acciones); los roles de ejemplo se
    # conservan porque pueden tener usuarios asignados.
    op.drop_column("roles", "es_administrador")
