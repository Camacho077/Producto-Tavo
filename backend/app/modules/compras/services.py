import uuid
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core import mensajes
from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError, NotFoundError
from app.modules.compras import models, schemas
from app.modules.inventario import services as inventario
from app.modules.inventario.models import Insumo
from app.modules.inventario.unidades import compatibles, convertir, legible, unidades_de_familia

CENTAVOS = Decimal("0.01")


# ---------- Serialización (campos calculados que el ORM no tiene) ----------
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
        "insumos": [{"id": x.id, "nombre": x.nombre, "unidad": x.unidad, "existencia": x.existencia} for x in p.insumos],
        "created_at": p.created_at,
    }


def codigo_compra(numero: int) -> str:
    return f"COM-{numero:06d}"


def subtotal(item: models.CompraItem) -> Decimal:
    return (Decimal(item.precio_unitario) * Decimal(item.cantidad)).quantize(CENTAVOS)


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
                "insumo_id": it.insumo_id,
                "insumo_nombre": it.insumo.nombre if it.insumo else None,
                "insumo_unidad": it.insumo.unidad if it.insumo else None,
                "cantidad": it.cantidad,
                "unidad": it.unidad,
                "precio_unitario": it.precio_unitario,
                "subtotal": subtotal(it),
            }
            for it in c.items
        ],
    }


def conteo_compras_por_proveedor(db: Session, tenant_id: uuid.UUID) -> dict:
    filas = (
        db.query(models.Compra.proveedor_id, func.count(models.Compra.id))
        .filter(models.Compra.tenant_id == tenant_id)
        .group_by(models.Compra.proveedor_id)
        .all()
    )
    return {clave: total for clave, total in filas}


# ---------- Búsquedas o 404 ----------
def obtener_proveedor_o_404(db: Session, tenant_id: uuid.UUID, proveedor_id: uuid.UUID) -> models.Proveedor:
    return obtener_del_tenant(db, models.Proveedor, tenant_id, proveedor_id, "El proveedor indicado")


def obtener_compra_o_404(db: Session, tenant_id: uuid.UUID, compra_id: uuid.UUID) -> models.Compra:
    return obtener_del_tenant(db, models.Compra, tenant_id, compra_id, "La compra indicada")


def siguiente_numero(db: Session, tenant_id: uuid.UUID, modelo) -> int:
    actual = db.query(func.coalesce(func.max(modelo.numero), 0)).filter(modelo.tenant_id == tenant_id).scalar()
    return int(actual) + 1


def sincronizar_insumos_proveedor(db: Session, tenant_id: uuid.UUID, proveedor: models.Proveedor, insumo_ids) -> None:
    """Reemplaza la lista de insumos que surte el proveedor (solo del tenant).
    Se escribe la tabla intermedia a mano para dejar tenant_id en cada fila."""
    ids = list(dict.fromkeys(insumo_ids or []))
    insumos = db.query(Insumo).filter(Insumo.tenant_id == tenant_id, Insumo.id.in_(ids)).all() if ids else []
    if len(insumos) != len(ids):
        faltantes = len(ids) - len(insumos)
        raise NotFoundError(
            f"No se pudo guardar el proveedor: {mensajes.plural(faltantes, 'insumo')} de los seleccionados "
            "ya no existe(n) o pertenece(n) a otra empresa."
        )
    if proveedor.id is None:
        db.flush()
    tabla = models.proveedor_insumos
    db.execute(tabla.delete().where(tabla.c.proveedor_id == proveedor.id))
    if insumos:
        db.execute(tabla.insert(), [{"proveedor_id": proveedor.id, "insumo_id": i.id, "tenant_id": tenant_id} for i in insumos])
    db.expire(proveedor, ["insumos"])


# ---------- Compras ----------
def _entrada(item: models.CompraItem) -> tuple[Decimal, Decimal]:
    """(cantidad en la unidad del insumo, costo de UNA unidad del insumo)."""
    cantidad = convertir(Decimal(item.cantidad), item.unidad, item.insumo.unidad)
    costo = (subtotal(item) / cantidad) if cantidad > 0 else Decimal("0")
    return cantidad, costo


def _aplicar_entrada(db: Session, tenant_id: uuid.UUID, compra: models.Compra, usuario_nombre: str | None) -> None:
    insumos = inventario.bloquear_insumos(db, tenant_id, [it.insumo_id for it in compra.items])
    for item in compra.items:
        item.insumo = insumos[item.insumo_id]
        cantidad, costo = _entrada(item)
        inventario.registrar(
            db, tenant_id, item.insumo, "compra", cantidad,
            documento_tipo="compra", documento_id=compra.id, documento_codigo=codigo_compra(compra.numero),
            usuario_nombre=usuario_nombre, costo_entrada=costo, fecha=compra.fecha,
        )


def crear_compra(db: Session, tenant_id: uuid.UUID, payload: schemas.CompraCreate, usuario_nombre: str | None = None) -> models.Compra:
    obtener_proveedor_o_404(db, tenant_id, payload.proveedor_id)
    ids = [it.insumo_id for it in payload.items]
    insumos = {i.id: i for i in db.query(Insumo).filter(Insumo.tenant_id == tenant_id, Insumo.id.in_(ids)).all()}
    if len(insumos) != len(set(ids)):
        raise NotFoundError("Uno de los insumos de la compra ya no existe o pertenece a otra empresa: recarga la pantalla.")
    if len(set(ids)) != len(ids):
        repetido = next(insumos[i].nombre for i in ids if ids.count(i) > 1)
        raise ConflictError(f"La compra repite el insumo {repetido}: súmalo en una sola línea.")

    total = Decimal("0")
    items = []
    for item in payload.items:
        insumo = insumos[item.insumo_id]
        if not compatibles(item.unidad, insumo.unidad):
            raise ConflictError(
                f"{insumo.nombre} se lleva en {insumo.unidad}: no se puede comprar en {item.unidad}. "
                f"Usa {', '.join(unidades_de_familia(insumo.unidad))}."
            )
        total += (item.precio_unitario * item.cantidad).quantize(CENTAVOS)
        items.append(
            models.CompraItem(
                tenant_id=tenant_id, insumo_id=item.insumo_id, cantidad=item.cantidad,
                unidad=item.unidad, precio_unitario=item.precio_unitario, insumo=insumo,
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
        _aplicar_entrada(db, tenant_id, compra, usuario_nombre)
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
    _aplicar_entrada(db, tenant_id, compra, usuario_nombre)
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
    """Anula una compra pendiente o confirmada. Si estaba confirmada, lo que
    sumó sale de la bodega (no puede quedar negativo) y su peso sale del
    costo promedio del insumo."""
    compra = obtener_compra_o_404(db, tenant_id, compra_id)
    if compra.estado not in ("pendiente", "confirmada"):
        raise ConflictError(
            mensajes.estado_no_permite("anular", "la compra", codigo_compra(compra.numero), compra.estado, ("pendiente", "confirmada"))
        )
    codigo = codigo_compra(compra.numero)
    if compra.estado == "confirmada":
        insumos = inventario.bloquear_insumos(db, tenant_id, [it.insumo_id for it in compra.items])
        for item in compra.items:
            item.insumo = insumos[item.insumo_id]
            cantidad, _ = _entrada(item)
            if Decimal(item.insumo.existencia) < cantidad:
                raise ConflictError(
                    f"No se puede anular la compra {codigo}: de {item.insumo.nombre} quedan "
                    f"{legible(item.insumo.existencia, item.insumo.unidad)} y esta compra ingresó "
                    f"{legible(cantidad, item.insumo.unidad)}: parte ya se gastó y la existencia quedaría en negativo."
                )
        for item in compra.items:
            cantidad, costo = _entrada(item)
            inventario.revertir_costo_de_entrada(item.insumo, cantidad, costo)
            inventario.registrar(
                db, tenant_id, item.insumo, "anulacion_compra", -cantidad,
                documento_tipo="compra", documento_id=compra.id, documento_codigo=codigo, usuario_nombre=usuario_nombre,
            )
    compra.estado = "anulada"
    db.commit()
    db.refresh(compra)
    return compra
