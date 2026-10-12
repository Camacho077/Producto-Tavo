import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core import mensajes
from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError
from app.modules.compras.services import obtener_producto_o_404, registrar_movimiento, siguiente_numero
from app.modules.ventas import models, schemas

# Transiciones permitidas del pedido: desde cada estado, a cuáles se puede pasar.
TRANSICIONES_PEDIDO = {
    "pendiente": ("en_proceso", "cancelado"),
    "en_proceso": ("listo", "cancelado"),
    "listo": ("entregado", "en_proceso", "cancelado"),
    "entregado": (),
    "cancelado": (),
}

ORDEN_PRIORIDAD = {"urgente": 0, "alta": 1, "media": 2, "baja": 3}


# ---------- Serialización ----------
def _serializar_items(items) -> list[dict]:
    return [
        {
            "id": it.id,
            "producto_id": it.producto_id,
            "producto_nombre": it.producto.nombre if it.producto else None,
            "producto_sku": it.producto.sku if it.producto else None,
            "cantidad": it.cantidad,
            "precio_unitario": it.precio_unitario,
            "subtotal": Decimal(it.precio_unitario) * it.cantidad,
        }
        for it in items
    ]


def codigo_venta(numero: int) -> str:
    return f"VEN-{numero:06d}"


def codigo_pedido(numero: int) -> str:
    return f"PED-{numero:06d}"


def serializar_venta(v: models.Venta) -> dict:
    return {
        "id": v.id,
        "numero": v.numero,
        "codigo": codigo_venta(v.numero),
        "cliente_nombre": v.cliente_nombre,
        "cliente_documento": v.cliente_documento,
        "fecha": v.fecha,
        "estado": v.estado,
        "total": v.total,
        "notas": v.notas,
        "created_at": v.created_at,
        "items": _serializar_items(v.items),
    }


def serializar_pedido(p: models.Pedido) -> dict:
    return {
        "id": p.id,
        "numero": p.numero,
        "codigo": codigo_pedido(p.numero),
        "cliente_nombre": p.cliente_nombre,
        "cliente_telefono": p.cliente_telefono,
        "cliente_direccion": p.cliente_direccion,
        "fecha": p.fecha,
        "fecha_entrega": p.fecha_entrega,
        "prioridad": p.prioridad,
        "estado": p.estado,
        "total": p.total,
        "notas": p.notas,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
        "items": _serializar_items(p.items),
        "eventos": [
            {
                "id": e.id,
                "estado": e.estado,
                "nota": e.nota,
                "usuario_nombre": e.usuario_nombre,
                "created_at": e.created_at,
            }
            for e in p.eventos
        ],
    }


# ---------- Ventas ----------
def obtener_venta_o_404(db: Session, tenant_id: uuid.UUID, venta_id: uuid.UUID) -> models.Venta:
    return obtener_del_tenant(db, models.Venta, tenant_id, venta_id, "La venta indicada")


def _construir_items(db: Session, tenant_id: uuid.UUID, items_payload, modelo_item):
    total = Decimal("0")
    items = []
    for item in items_payload:
        obtener_producto_o_404(db, tenant_id, item.producto_id)
        total += item.precio_unitario * item.cantidad
        items.append(
            modelo_item(
                tenant_id=tenant_id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            )
        )
    return items, total


def _descontar_stock(
    db: Session, tenant_id: uuid.UUID, venta: models.Venta, usuario_nombre: str | None = None, accion: str | None = None
) -> None:
    """Valida TODO antes de mover nada: si una línea no tiene stock, no se
    descuenta ninguna y el stock jamás queda negativo.

    `accion` es lo que dice el mensaje de error. Por defecto cita la venta
    ("completar la venta VEN-000012"); al REGISTRAR una venta nueva no se cita
    el número, porque el rechazo revierte la transacción y ese número nunca
    llega a existir (el usuario lo buscaría y no lo encontraría)."""
    productos = {item.producto_id: obtener_producto_o_404(db, tenant_id, item.producto_id) for item in venta.items}
    pedido_por_producto: dict = {}
    for item in venta.items:
        pedido_por_producto[item.producto_id] = pedido_por_producto.get(item.producto_id, 0) + item.cantidad
    for producto_id, cantidad in pedido_por_producto.items():
        producto = productos[producto_id]
        if producto.stock < cantidad:
            raise ConflictError(
                mensajes.stock_insuficiente(
                    accion or f"completar la venta {codigo_venta(venta.numero)}", producto.nombre, producto.stock, cantidad
                )
            )
    for item in venta.items:
        registrar_movimiento(
            db, tenant_id, productos[item.producto_id], "venta", -item.cantidad, "venta", venta.id, codigo_venta(venta.numero), usuario_nombre
        )


def crear_venta(db: Session, tenant_id: uuid.UUID, payload: schemas.VentaCreate, usuario_nombre: str | None = None) -> models.Venta:
    items, total = _construir_items(db, tenant_id, payload.items, models.VentaItem)
    venta = models.Venta(
        tenant_id=tenant_id,
        numero=siguiente_numero(db, tenant_id, models.Venta),
        cliente_nombre=payload.cliente_nombre,
        cliente_documento=payload.cliente_documento,
        fecha=payload.fecha,
        estado="pendiente",
        total=total,
        notas=payload.notas,
        items=items,
    )
    db.add(venta)
    db.flush()
    if payload.confirmar:
        try:
            _descontar_stock(db, tenant_id, venta, usuario_nombre, accion="registrar la venta")
        except ConflictError:
            # La venta ya se había agregado (flush) para numerarla: se deshace
            # EXPLÍCITAMENTE, sin depender de cómo se cierre la sesión.
            db.rollback()
            raise
        venta.estado = "completada"
    db.commit()
    db.refresh(venta)
    return venta


def confirmar_venta(db: Session, tenant_id: uuid.UUID, venta_id: uuid.UUID, usuario_nombre: str | None = None) -> models.Venta:
    venta = obtener_venta_o_404(db, tenant_id, venta_id)
    if venta.estado != "pendiente":
        raise ConflictError(
            mensajes.estado_no_permite("completar", "la venta", codigo_venta(venta.numero), venta.estado, ("pendiente",))
        )

    _descontar_stock(db, tenant_id, venta, usuario_nombre)
    venta.estado = "completada"
    db.commit()
    db.refresh(venta)
    return venta


def cancelar_venta(db: Session, tenant_id: uuid.UUID, venta_id: uuid.UUID) -> models.Venta:
    venta = obtener_venta_o_404(db, tenant_id, venta_id)
    if venta.estado != "pendiente":
        raise ConflictError(
            mensajes.estado_no_permite("cancelar", "la venta", codigo_venta(venta.numero), venta.estado, ("pendiente",))
        )

    venta.estado = "cancelada"
    db.commit()
    db.refresh(venta)
    return venta


def anular_venta(db: Session, tenant_id: uuid.UUID, venta_id: uuid.UUID, usuario_nombre: str | None = None) -> models.Venta:
    """Anula una venta pendiente o completada. Si estaba completada, el stock
    descontado vuelve al inventario."""
    venta = obtener_venta_o_404(db, tenant_id, venta_id)
    if venta.estado not in ("pendiente", "completada"):
        raise ConflictError(
            mensajes.estado_no_permite(
                "anular", "la venta", codigo_venta(venta.numero), venta.estado, ("pendiente", "completada")
            )
        )

    if venta.estado == "completada":
        for item in venta.items:
            producto = obtener_producto_o_404(db, tenant_id, item.producto_id)
            registrar_movimiento(
                db, tenant_id, producto, "anulacion_venta", item.cantidad, "venta", venta.id, codigo_venta(venta.numero), usuario_nombre
            )

    venta.estado = "anulada"
    db.commit()
    db.refresh(venta)
    return venta


# ---------- Pedidos ----------
def obtener_pedido_o_404(db: Session, tenant_id: uuid.UUID, pedido_id: uuid.UUID) -> models.Pedido:
    return obtener_del_tenant(db, models.Pedido, tenant_id, pedido_id, "El pedido indicado")


def crear_pedido(db: Session, tenant_id: uuid.UUID, payload: schemas.PedidoCreate, usuario_nombre: str) -> models.Pedido:
    items, total = _construir_items(db, tenant_id, payload.items, models.PedidoItem)
    pedido = models.Pedido(
        tenant_id=tenant_id,
        numero=siguiente_numero(db, tenant_id, models.Pedido),
        cliente_nombre=payload.cliente_nombre,
        cliente_telefono=payload.cliente_telefono,
        cliente_direccion=payload.cliente_direccion,
        fecha=payload.fecha,
        fecha_entrega=payload.fecha_entrega,
        prioridad=payload.prioridad,
        estado="pendiente",
        total=total,
        notas=payload.notas,
        items=items,
        eventos=[
            models.PedidoEvento(
                tenant_id=tenant_id, estado="pendiente", nota="Pedido registrado", usuario_nombre=usuario_nombre
            )
        ],
    )
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    return pedido


def actualizar_pedido(
    db: Session, tenant_id: uuid.UUID, pedido_id: uuid.UUID, payload: schemas.PedidoUpdate, usuario_nombre: str
) -> models.Pedido:
    pedido = obtener_pedido_o_404(db, tenant_id, pedido_id)
    if pedido.estado in ("entregado", "cancelado"):
        raise ConflictError(
            f"No se puede editar el pedido {codigo_pedido(pedido.numero)}: ya está "
            f"{pedido.estado} y los pedidos cerrados no admiten cambios."
        )

    datos = payload.model_dump(exclude_unset=True)
    items_payload = datos.pop("items", None)
    for campo, valor in datos.items():
        setattr(pedido, campo, valor)

    if items_payload is not None:
        items, total = _construir_items(db, tenant_id, payload.items, models.PedidoItem)
        pedido.items = items
        pedido.total = total

    pedido.eventos.append(
        models.PedidoEvento(tenant_id=tenant_id, estado=pedido.estado, nota="Pedido editado", usuario_nombre=usuario_nombre)
    )
    db.commit()
    db.refresh(pedido)
    return pedido


def cambiar_estado_pedido(
    db: Session, tenant_id: uuid.UUID, pedido_id: uuid.UUID, payload: schemas.PedidoCambioEstado, usuario_nombre: str
) -> models.Pedido:
    pedido = obtener_pedido_o_404(db, tenant_id, pedido_id)
    permitidos = TRANSICIONES_PEDIDO.get(pedido.estado, ())
    if payload.estado not in permitidos:
        actual = pedido.estado.replace("_", " ")
        destino = payload.estado.replace("_", " ")
        if not permitidos:
            raise ConflictError(
                f"No se puede pasar el pedido {codigo_pedido(pedido.numero)} a {destino}: "
                f"ya está {actual} y es un estado final."
            )
        legibles = ", ".join(p.replace("_", " ") for p in permitidos)
        raise ConflictError(
            f"No se puede pasar el pedido {codigo_pedido(pedido.numero)} a {destino}: "
            f"está {actual} y desde ahí solo puede pasar a {legibles}."
        )

    pedido.estado = payload.estado
    pedido.eventos.append(
        models.PedidoEvento(
            tenant_id=tenant_id, estado=payload.estado, nota=payload.nota, usuario_nombre=usuario_nombre
        )
    )
    db.commit()
    db.refresh(pedido)
    return pedido
