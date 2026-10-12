import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import mensajes
from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError, NotFoundError
from app.modules.compras import models, schemas


# ---------- Serialización (campos calculados que el ORM no tiene) ----------
def serializar_catalogo(obj, productos_count: int = 0) -> dict:
    return {
        "id": obj.id,
        "nombre": obj.nombre,
        "descripcion": obj.descripcion,
        "activo": obj.activo,
        "productos_count": productos_count,
        "created_at": obj.created_at,
    }


def serializar_proveedor(p: models.Proveedor, compras_count: int = 0) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "tipo_persona": p.tipo_persona,
        "tipo_documento": p.tipo_documento,
        "numero_documento": p.numero_documento,
        "nombres": p.nombres,
        "apellidos": p.apellidos,
        "nit": p.nit,
        "razon_social": p.razon_social,
        "representante_nombre": p.representante_nombre,
        "representante_documento": p.representante_documento,
        "telefono": p.telefono,
        "email": p.email,
        "direccion": p.direccion,
        "activo": p.activo,
        "compras_count": compras_count,
        "productos": [{"id": x.id, "nombre": x.nombre, "sku": x.sku, "stock": x.stock} for x in p.productos],
        "created_at": p.created_at,
    }


def serializar_producto(p: models.Producto) -> dict:
    return {
        "id": p.id,
        "nombre": p.nombre,
        "sku": p.sku,
        "descripcion": p.descripcion,
        "precio": p.precio,
        "precio_compra": p.precio_compra,
        "stock": p.stock,
        "stock_minimo": p.stock_minimo,
        "activo": p.activo,
        "categoria_id": p.categoria_id,
        "categoria_nombre": p.categoria.nombre if p.categoria else None,
        "proveedores": [{"id": x.id, "nombre": x.nombre} for x in p.proveedores],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def codigo_compra(numero: int) -> str:
    return f"COM-{numero:06d}"


def serializar_compra(c: models.Compra) -> dict:
    return {
        "id": c.id,
        "numero": c.numero,
        "codigo": codigo_compra(c.numero),
        "proveedor_id": c.proveedor_id,
        "proveedor_nombre": c.proveedor.nombre if c.proveedor else None,
        "fecha": c.fecha,
        "estado": c.estado,
        "total": c.total,
        "notas": c.notas,
        "created_at": c.created_at,
        "items": [
            {
                "id": it.id,
                "producto_id": it.producto_id,
                "producto_nombre": it.producto.nombre if it.producto else None,
                "producto_sku": it.producto.sku if it.producto else None,
                "cantidad": it.cantidad,
                "precio_unitario": it.precio_unitario,
                "subtotal": Decimal(it.precio_unitario) * it.cantidad,
            }
            for it in c.items
        ],
    }


def conteo_productos_por(db: Session, tenant_id: uuid.UUID, columna) -> dict:
    """{categoria_id: cantidad de productos} para el tenant."""
    filas = (
        db.query(columna, func.count(models.Producto.id))
        .filter(models.Producto.tenant_id == tenant_id, columna.isnot(None))
        .group_by(columna)
        .all()
    )
    return {clave: total for clave, total in filas}


def conteo_compras_por_proveedor(db: Session, tenant_id: uuid.UUID) -> dict:
    filas = (
        db.query(models.Compra.proveedor_id, func.count(models.Compra.id))
        .filter(models.Compra.tenant_id == tenant_id)
        .group_by(models.Compra.proveedor_id)
        .all()
    )
    return {clave: total for clave, total in filas}


# ---------- Búsquedas o 404 ----------
# Todas filtran por tenant_id (ver app/core/consultas.py): un id de otra
# empresa responde 404, no el registro ajeno.
def obtener_producto_o_404(db: Session, tenant_id: uuid.UUID, producto_id: uuid.UUID) -> models.Producto:
    return obtener_del_tenant(db, models.Producto, tenant_id, producto_id, "El producto indicado")


def obtener_proveedor_o_404(db: Session, tenant_id: uuid.UUID, proveedor_id: uuid.UUID) -> models.Proveedor:
    return obtener_del_tenant(db, models.Proveedor, tenant_id, proveedor_id, "El proveedor indicado")


def obtener_categoria_o_404(db: Session, tenant_id: uuid.UUID, categoria_id: uuid.UUID) -> models.Categoria:
    return obtener_del_tenant(db, models.Categoria, tenant_id, categoria_id, "La categoría indicada")


def obtener_compra_o_404(db: Session, tenant_id: uuid.UUID, compra_id: uuid.UUID) -> models.Compra:
    return obtener_del_tenant(db, models.Compra, tenant_id, compra_id, "La compra indicada")


def siguiente_numero(db: Session, tenant_id: uuid.UUID, modelo) -> int:
    actual = db.query(func.coalesce(func.max(modelo.numero), 0)).filter(modelo.tenant_id == tenant_id).scalar()
    return int(actual) + 1


# ---------- Inventario ----------
def registrar_movimiento(
    db: Session,
    tenant_id: uuid.UUID,
    producto: models.Producto,
    tipo: str,
    cantidad: int,
    documento_tipo: str,
    documento_id: uuid.UUID,
    documento_codigo: str,
    usuario_nombre: str | None,
) -> models.MovimientoInventario:
    """Aplica `cantidad` (con signo) al stock y deja la traza. Nunca deja el
    stock negativo: eso lo garantiza quien llama validando antes."""
    if producto.stock + cantidad < 0:
        raise ConflictError(
            mensajes.stock_insuficiente(
                f"registrar el movimiento de {documento_codigo}", producto.nombre, producto.stock, abs(cantidad)
            )
        )
    producto.stock += cantidad
    movimiento = models.MovimientoInventario(
        tenant_id=tenant_id,
        producto_id=producto.id,
        tipo=tipo,
        cantidad=cantidad,
        stock_resultante=producto.stock,
        documento_tipo=documento_tipo,
        documento_id=documento_id,
        documento_codigo=documento_codigo,
        usuario_nombre=usuario_nombre,
    )
    db.add(movimiento)
    return movimiento


def sincronizar_productos_proveedor(db: Session, tenant_id: uuid.UUID, proveedor: models.Proveedor, producto_ids) -> None:
    """Reemplaza la lista de productos que surte el proveedor (solo del tenant).
    Se escribe la tabla intermedia a mano para dejar tenant_id en cada fila."""
    ids = list(dict.fromkeys(producto_ids or []))
    productos = (
        db.query(models.Producto).filter(models.Producto.tenant_id == tenant_id, models.Producto.id.in_(ids)).all()
        if ids
        else []
    )
    if len(productos) != len(ids):
        faltantes = len(ids) - len(productos)
        raise NotFoundError(
            f"No se pudo guardar el proveedor: {mensajes.plural(faltantes, 'producto')} de los seleccionados "
            "ya no existe(n) o pertenece(n) a otra empresa."
        )
    if proveedor.id is None:
        db.flush()
    tabla = models.proveedor_productos
    db.execute(tabla.delete().where(tabla.c.proveedor_id == proveedor.id))
    if productos:
        db.execute(
            tabla.insert(),
            [{"proveedor_id": proveedor.id, "producto_id": p.id, "tenant_id": tenant_id} for p in productos],
        )
    db.expire(proveedor, ["productos"])


# ---------- Compras ----------
def _aplicar_stock(db: Session, tenant_id: uuid.UUID, compra: models.Compra, signo: int, usuario_nombre: str | None = None) -> None:
    tipo = "compra" if signo > 0 else "anulacion_compra"
    for item in compra.items:
        producto = obtener_producto_o_404(db, tenant_id, item.producto_id)
        registrar_movimiento(
            db, tenant_id, producto, tipo, signo * item.cantidad, "compra", compra.id, codigo_compra(compra.numero), usuario_nombre
        )
        if signo > 0:
            producto.precio_compra = item.precio_unitario


def crear_compra(db: Session, tenant_id: uuid.UUID, payload: schemas.CompraCreate, usuario_nombre: str | None = None) -> models.Compra:
    obtener_proveedor_o_404(db, tenant_id, payload.proveedor_id)

    total = Decimal("0")
    items = []
    for item in payload.items:
        obtener_producto_o_404(db, tenant_id, item.producto_id)
        total += item.precio_unitario * item.cantidad
        items.append(
            models.CompraItem(
                tenant_id=tenant_id,
                producto_id=item.producto_id,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            )
        )

    compra = models.Compra(
        tenant_id=tenant_id,
        numero=siguiente_numero(db, tenant_id, models.Compra),
        proveedor_id=payload.proveedor_id,
        fecha=payload.fecha,
        estado="pendiente",
        total=total,
        notas=payload.notas,
        items=items,
    )
    db.add(compra)
    db.flush()
    if payload.confirmar:
        _aplicar_stock(db, tenant_id, compra, +1, usuario_nombre)
        compra.estado = "confirmada"
    db.commit()
    db.refresh(compra)
    return compra


def confirmar_compra(db: Session, tenant_id: uuid.UUID, compra_id: uuid.UUID, usuario_nombre: str | None = None) -> models.Compra:
    compra = obtener_compra_o_404(db, tenant_id, compra_id)
    if compra.estado != "pendiente":
        raise ConflictError(
            mensajes.estado_no_permite("confirmar", "la compra", codigo_compra(compra.numero), compra.estado, ("pendiente",))
        )

    _aplicar_stock(db, tenant_id, compra, +1, usuario_nombre)
    compra.estado = "confirmada"
    db.commit()
    db.refresh(compra)
    return compra


def cancelar_compra(db: Session, tenant_id: uuid.UUID, compra_id: uuid.UUID) -> models.Compra:
    compra = obtener_compra_o_404(db, tenant_id, compra_id)
    if compra.estado != "pendiente":
        raise ConflictError(
            mensajes.estado_no_permite("cancelar", "la compra", codigo_compra(compra.numero), compra.estado, ("pendiente",))
        )

    compra.estado = "cancelada"
    db.commit()
    db.refresh(compra)
    return compra


def anular_compra(db: Session, tenant_id: uuid.UUID, compra_id: uuid.UUID, usuario_nombre: str | None = None) -> models.Compra:
    """Anula una compra pendiente o confirmada. Si estaba confirmada, el
    stock que había subido se revierte (no puede quedar negativo)."""
    compra = obtener_compra_o_404(db, tenant_id, compra_id)
    if compra.estado not in ("pendiente", "confirmada"):
        raise ConflictError(
            mensajes.estado_no_permite(
                "anular", "la compra", codigo_compra(compra.numero), compra.estado, ("pendiente", "confirmada")
            )
        )

    if compra.estado == "confirmada":
        for item in compra.items:
            producto = obtener_producto_o_404(db, tenant_id, item.producto_id)
            if producto.stock < item.cantidad:
                raise ConflictError(
                    f"No se puede anular la compra {codigo_compra(compra.numero)}: el producto {producto.nombre} "
                    f"solo tiene {mensajes.unidades(producto.stock)} en stock y esta compra ingresó "
                    f"{item.cantidad} — parte de ese stock ya se vendió y quedaría en negativo."
                )
        _aplicar_stock(db, tenant_id, compra, -1, usuario_nombre)

    compra.estado = "anulada"
    db.commit()
    db.refresh(compra)
    return compra
