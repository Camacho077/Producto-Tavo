"""
Reglas de la caja (fase 6). Cobrar, abrir y cerrar se hacen en una
transacción cada uno; el cuadre se calcula SIEMPRE desde los pagos y los
gastos guardados, nunca desde un acumulado que pudiera desfasarse.
"""
import uuid
from collections import defaultdict
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.consultas import obtener_del_tenant
from app.core.errors import AppError, ConflictError, NotFoundError
from app.core.tiempo import ahora_utc
from app.db.models import Tenant
from app.modules.ajustes.schemas import ConfiguracionRestaurante, configuracion_de
from app.modules.caja import models, schemas
from app.modules.gastos.models import Gasto
from app.modules.ordenes import models as om
from app.modules.ordenes.services import codigo_orden, estado_cocina, opciones_carga_orden, registrar_evento
from app.modules.seguridad.models import Usuario

CENTAVOS = Decimal("0.01")
NOMBRE_MEDIO = {"efectivo": "Efectivo", "transferencia": "Transferencia", "nequi": "Nequi", "daviplata": "Daviplata", "tarjeta": "Tarjeta"}


class DatosInvalidos(AppError):
    status_code = 422
    detail = "Revisa los datos."


def pesos(valor) -> Decimal:
    return Decimal(valor).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def legible(valor) -> str:
    """$ 12.500 (sin centavos si no los hay)."""
    v = pesos(valor)
    entero = f"{abs(int(v)):,}".replace(",", ".")
    centavos = abs(v) - abs(int(v))
    return f"{'-' if v < 0 else ''}$ {entero}" + (f",{int(centavos * 100):02d}" if centavos else "")


def codigo_venta(numero: int) -> str:
    """Comprobante interno (no es factura electrónica)."""
    return f"CI-{numero:06d}"


def _config(db: Session, tenant_id: uuid.UUID) -> ConfiguracionRestaurante:
    return configuracion_de(db.get(Tenant, tenant_id))


def _siguiente(db: Session, tenant_id: uuid.UUID, modelo, clave: str) -> int:
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:clave))"), {"clave": f"{clave}:{tenant_id}"})
    actual = db.query(func.coalesce(func.max(modelo.numero), 0)).filter(modelo.tenant_id == tenant_id).scalar()
    return int(actual) + 1


# ---------------------------------------------------------------------------
# Impuesto al consumo
# ---------------------------------------------------------------------------
def desglose(total_platos: Decimal, config: ConfiguracionRestaurante) -> dict:
    """Base, impuesto y total de lo consumido según cómo cobre el
    restaurante el impuesto al consumo (Ajustes)."""
    imp = config.impuesto_consumo
    total_platos = pesos(total_platos)
    if not imp.aplica:
        return {"subtotal": total_platos, "impuesto": Decimal("0.00"), "total": total_platos, "tasa": Decimal("0")}
    tasa = Decimal(imp.tasa)
    if imp.incluido_en_precio:
        base = pesos(total_platos / (1 + tasa / 100))
        return {"subtotal": base, "impuesto": total_platos - base, "total": total_platos, "tasa": tasa}
    impuesto = pesos(total_platos * tasa / 100)
    return {"subtotal": total_platos, "impuesto": impuesto, "total": total_platos + impuesto, "tasa": tasa}


# ---------------------------------------------------------------------------
# Sesión de caja
# ---------------------------------------------------------------------------
def caja_abierta(db: Session, tenant_id: uuid.UUID) -> models.CajaSesion | None:
    return db.query(models.CajaSesion).filter(models.CajaSesion.tenant_id == tenant_id, models.CajaSesion.estado == "abierta").first()


def abrir(db: Session, usuario: Usuario, base: Decimal, ahora: datetime | None = None) -> models.CajaSesion:
    ahora = ahora or ahora_utc()
    tenant_id = usuario.tenant_id
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:clave))"), {"clave": f"caja-abrir:{tenant_id}"})
    actual = caja_abierta(db, tenant_id)
    if actual:
        raise ConflictError(f"La caja {actual.numero} ya está abierta (la abrió {actual.abierta_por}): ciérrala antes de abrir otra.")
    caja = models.CajaSesion(
        tenant_id=tenant_id, numero=_siguiente(db, tenant_id, models.CajaSesion, "caja"), estado="abierta",
        abierta_en=ahora, abierta_por_id=usuario.id, abierta_por=usuario.nombre_completo, base_inicial=base,
        created_at=ahora, updated_at=ahora,
    )
    db.add(caja)
    db.commit()
    db.refresh(caja)
    return caja


def cuadre(db: Session, caja: models.CajaSesion) -> dict:
    """Lo que la caja debería tener por medio de pago: los pagos de sus
    ventas vigentes, más la base y menos los gastos pagados desde ella (en
    efectivo)."""
    por_medio = dict(
        db.query(models.VentaPago.medio, func.sum(models.VentaPago.monto))
        .join(models.Venta, models.Venta.id == models.VentaPago.venta_id)
        .filter(models.Venta.caja_id == caja.id, models.Venta.estado == "completada")
        .group_by(models.VentaPago.medio)
        .all()
    )
    ventas = (
        db.query(
            func.count(models.Venta.id), func.coalesce(func.sum(models.Venta.total), 0),
            func.coalesce(func.sum(models.Venta.propina), 0), func.coalesce(func.sum(models.Venta.impuesto), 0),
        )
        .filter(models.Venta.caja_id == caja.id, models.Venta.estado == "completada")
        .one()
    )
    anuladas = db.query(func.count(models.Venta.id)).filter(models.Venta.caja_id == caja.id, models.Venta.estado == "anulada").scalar()
    gastos = db.query(func.coalesce(func.sum(Gasto.valor), 0)).filter(Gasto.caja_id == caja.id).scalar()
    esperado = {m: pesos(x) for m, x in por_medio.items()}
    esperado["efectivo"] = pesos(esperado.get("efectivo", 0) + Decimal(caja.base_inicial) - Decimal(gastos))
    return {
        "ventas": int(ventas[0]),
        "ventas_anuladas": int(anuladas or 0),
        "total_ventas": pesos(ventas[1]),
        "propinas": pesos(ventas[2]),
        "impuesto": pesos(ventas[3]),
        "gastos_de_caja": pesos(gastos),
        "base_inicial": pesos(caja.base_inicial),
        "esperado": esperado,
    }


def cerrar(db: Session, usuario: Usuario, payload: schemas.CerrarCaja, ahora: datetime | None = None) -> models.CajaSesion:
    ahora = ahora or ahora_utc()
    caja = caja_abierta(db, usuario.tenant_id)
    if caja is None:
        raise ConflictError("No hay ninguna caja abierta para cerrar.")
    esperado = cuadre(db, caja)["esperado"]
    medios = set(esperado) | set(payload.contado)
    contado = {m: pesos(payload.contado.get(m, 0)) for m in medios}
    diferencias = {m: contado[m] - esperado.get(m, Decimal("0")) for m in medios}
    total = sum(diferencias.values(), Decimal("0"))
    descuadre = {m: d for m, d in diferencias.items() if d != 0}
    if descuadre and not payload.motivo_diferencia:
        detalle = "; ".join(f"{NOMBRE_MEDIO.get(m, m)}: {'sobran' if d > 0 else 'faltan'} {legible(abs(d))}" for m, d in descuadre.items())
        raise DatosInvalidos(f"La caja no cuadra ({detalle}): escribe el motivo de la diferencia para poder cerrarla.")
    caja.estado = "cerrada"
    caja.cerrada_en = ahora
    caja.cerrada_por_id = usuario.id
    caja.cerrada_por = usuario.nombre_completo
    caja.esperado = {m: str(x) for m, x in esperado.items()}
    caja.contado = {m: str(x) for m, x in contado.items()}
    caja.diferencia = total
    caja.motivo_diferencia = payload.motivo_diferencia if descuadre else None
    db.commit()
    db.refresh(caja)
    return caja


def serializar_caja(db: Session, caja: models.CajaSesion) -> dict:
    datos = {
        "id": caja.id, "numero": caja.numero, "estado": caja.estado, "abierta_en": caja.abierta_en, "abierta_por": caja.abierta_por,
        "base_inicial": caja.base_inicial, "cerrada_en": caja.cerrada_en, "cerrada_por": caja.cerrada_por,
        "contado": caja.contado, "diferencia": caja.diferencia, "motivo_diferencia": caja.motivo_diferencia,
    }
    resumen = cuadre(db, caja)
    if caja.estado == "cerrada" and caja.esperado is not None:
        resumen["esperado"] = {m: Decimal(x) for m, x in caja.esperado.items()}
    datos["resumen"] = resumen
    return datos


# ---------------------------------------------------------------------------
# Cobrar
# ---------------------------------------------------------------------------
def pendientes(o: om.Orden) -> list[om.OrdenItem]:
    return [i for i in o.items if not i.anulado and i.venta_id is None]


def _partir(orden: om.Orden, item: om.OrdenItem, cantidad: int) -> om.OrdenItem:
    """Divide una línea: `item` queda con `cantidad` (lo que se cobra ahora)
    y una línea nueva con el resto, con su parte del consumo."""
    resto = item.cantidad - cantidad
    fraccion = Decimal(resto) / Decimal(item.cantidad)
    consumo_resto = {k: str((Decimal(x) * fraccion).quantize(Decimal("0.001"))) for k, x in (item.consumo or {}).items()}
    item.consumo = {k: str(Decimal(x) - Decimal(consumo_resto[k])) for k, x in (item.consumo or {}).items()}
    nueva = om.OrdenItem(
        tenant_id=item.tenant_id, comanda_id=item.comanda_id, producto_id=item.producto_id, nombre=item.nombre,
        cantidad=resto, precio_unitario=item.precio_unitario, costo_unitario=item.costo_unitario,
        modificadores=item.modificadores, nota=item.nota, va_a_cocina=item.va_a_cocina, consumo=consumo_resto,
        posicion=item.posicion,
    )
    item.cantidad = cantidad
    orden.items.append(nueva)
    return nueva


def cobrar(db: Session, usuario: Usuario, payload: schemas.CobroCreate, ahora: datetime | None = None) -> models.Venta:
    ahora = ahora or ahora_utc()
    tenant_id = usuario.tenant_id
    caja = caja_abierta(db, tenant_id)
    if caja is None:
        raise ConflictError("La caja está cerrada: ábrela con su base antes de cobrar.")
    orden = obtener_del_tenant(db, om.Orden, tenant_id, payload.orden_id, "La orden indicada")
    if orden.estado != "abierta":
        raise ConflictError(f"No se puede cobrar la orden #{orden.numero}: ya está {orden.estado}.")
    por_cobrar = {i.id: i for i in pendientes(orden)}
    if not por_cobrar:
        raise ConflictError(f"La orden #{orden.numero} no tiene nada por cobrar.")

    if payload.items is None:
        elegidos = list(por_cobrar.values())
    else:
        elegidos = []
        for sel in payload.items:
            item = por_cobrar.get(sel.orden_item_id)
            if item is None:
                raise NotFoundError("Uno de los platos elegidos ya se cobró, se anuló o no es de esta orden: recarga la pantalla.")
            if sel.cantidad and sel.cantidad > item.cantidad:
                raise ConflictError(f"De {item.nombre} hay {item.cantidad} por cobrar y se intentó cobrar {sel.cantidad}.")
            if sel.cantidad and sel.cantidad < item.cantidad:
                _partir(orden, item, sel.cantidad)
            elegidos.append(item)
        if not elegidos:
            raise ConflictError("Elige al menos un plato para cobrar.")

    config = _config(db, tenant_id)
    medios_no = sorted({p.medio for p in payload.pagos} - set(config.medios_pago))
    if medios_no:
        raise ConflictError(f"El restaurante no recibe {', '.join(NOMBRE_MEDIO[m] for m in medios_no)}: actívalo en Ajustes → Operación.")
    montos = desglose(sum((Decimal(i.precio_unitario) * i.cantidad for i in elegidos), Decimal("0")), config)
    requerido = montos["total"] + payload.propina
    pagado = sum((p.monto for p in payload.pagos), Decimal("0"))
    if pagado != requerido:
        diferencia = requerido - pagado
        raise ConflictError(
            f"Los pagos suman {legible(pagado)} y la cuenta es {legible(requerido)}"
            f"{' con propina' if payload.propina else ''}: {'faltan' if diferencia > 0 else 'sobran'} {legible(abs(diferencia))}."
        )

    cliente = payload.cliente or schemas.ClienteComprobante()
    venta = models.Venta(
        tenant_id=tenant_id, numero=_siguiente(db, tenant_id, models.Venta, "venta"), fecha=ahora, estado="completada",
        orden_id=orden.id, caja_id=caja.id, cajero_id=usuario.id, cajero_nombre=usuario.nombre_completo,
        cliente_nombre=cliente.nombre or orden.cliente_nombre, cliente_documento_tipo=cliente.documento_tipo,
        cliente_documento=cliente.documento, cliente_correo=cliente.correo,
        subtotal=montos["subtotal"], impuesto=montos["impuesto"], impuesto_tasa=montos["tasa"], total=montos["total"],
        propina=payload.propina, created_at=ahora, updated_at=ahora,
        items=[
            models.VentaItem(
                tenant_id=tenant_id, orden_item_id=i.id, producto_id=i.producto_id, nombre=i.nombre, cantidad=i.cantidad,
                precio_unitario=i.precio_unitario, costo_unitario=i.costo_unitario,
            )
            for i in elegidos
        ],
        pagos=[
            models.VentaPago(
                tenant_id=tenant_id, medio=p.medio, monto=p.monto, recibido=p.recibido,
                cambio=(p.recibido - p.monto) if p.recibido is not None else None,
            )
            for p in payload.pagos
        ],
    )
    db.add(venta)
    db.flush()
    for i in elegidos:
        i.venta_id = venta.id
    codigo = codigo_venta(venta.numero)
    if pendientes(orden):
        registrar_evento(orden, "cobro_parcial", f"Comprobante {codigo}: {legible(venta.total)}", usuario.nombre_completo, ahora)
    else:
        orden.estado = "cobrada"
        orden.cerrada_en = ahora
        registrar_evento(orden, "cobrada", f"Comprobante {codigo}", usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(venta)
    return venta


def anular_venta(db: Session, usuario: Usuario, venta_id: uuid.UUID, motivo: str, ahora: datetime | None = None) -> models.Venta:
    """Deshace un cobro mientras su caja siga abierta: los platos vuelven a
    quedar por cobrar (los insumos NO vuelven: la comida ya se sirvió; para
    eso se anula la orden)."""
    ahora = ahora or ahora_utc()
    venta = obtener_venta_o_404(db, usuario.tenant_id, venta_id)
    codigo = codigo_venta(venta.numero)
    if venta.estado != "completada":
        raise ConflictError(f"El comprobante {codigo} ya está anulado.")
    if venta.caja.estado != "abierta":
        raise ConflictError(f"No se puede anular el comprobante {codigo}: la caja {venta.caja.numero} ya se cerró y su cuadre no se toca.")
    for i in db.query(om.OrdenItem).filter(om.OrdenItem.venta_id == venta.id):
        i.venta_id = None
    orden = venta.orden
    if orden.estado == "cobrada":
        orden.estado = "abierta"
        orden.cerrada_en = None
    registrar_evento(orden, "cobro_anulado", f"Comprobante {codigo}: {motivo}", usuario.nombre_completo, ahora)
    venta.estado = "anulada"
    venta.anulada_motivo = motivo
    db.commit()
    db.refresh(venta)
    return venta


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------
def obtener_venta_o_404(db: Session, tenant_id: uuid.UUID, venta_id: uuid.UUID) -> models.Venta:
    return obtener_del_tenant(db, models.Venta, tenant_id, venta_id, "El comprobante indicado")


def opciones_venta():
    return (selectinload(models.Venta.items), selectinload(models.Venta.pagos), joinedload(models.Venta.orden).joinedload(om.Orden.mesa))


def serializar_venta(v: models.Venta, ver_costos: bool = False) -> dict:
    o = v.orden
    return {
        "id": v.id, "numero": v.numero, "codigo": codigo_venta(v.numero), "fecha": v.fecha, "estado": v.estado,
        "orden_id": v.orden_id, "orden_numero": o.numero if o else None, "orden_codigo": codigo_orden(o) if o else None,
        "orden_tipo": o.tipo if o else None, "mesa_nombre": o.mesa.nombre if o and o.mesa else None,
        "caja_id": v.caja_id, "cajero_nombre": v.cajero_nombre,
        "cliente_nombre": v.cliente_nombre, "cliente_documento_tipo": v.cliente_documento_tipo,
        "cliente_documento": v.cliente_documento, "cliente_correo": v.cliente_correo,
        "subtotal": v.subtotal, "impuesto": v.impuesto, "impuesto_tasa": v.impuesto_tasa, "total": v.total, "propina": v.propina,
        "total_pagado": Decimal(v.total) + Decimal(v.propina),
        "anulada_motivo": v.anulada_motivo, "fe_estado": v.fe_estado,
        "medios": sorted({p.medio for p in v.pagos}),
        "items": [
            {
                "id": i.id, "producto_id": i.producto_id, "nombre": i.nombre, "cantidad": i.cantidad,
                "precio_unitario": i.precio_unitario, "subtotal": Decimal(i.precio_unitario) * i.cantidad,
                "costo_unitario": i.costo_unitario if ver_costos else None,
            }
            for i in v.items
        ],
        "pagos": [{"medio": p.medio, "monto": p.monto, "recibido": p.recibido, "cambio": p.cambio} for p in v.pagos],
    }


def por_cobrar(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    """Órdenes abiertas con algo por cobrar, con lo que falta (antes de
    impuesto si no va incluido)."""
    ordenes = (
        db.query(om.Orden).options(*opciones_carga_orden())
        .filter(om.Orden.tenant_id == tenant_id, om.Orden.estado == "abierta")
        .order_by(om.Orden.created_at).all()
    )
    config = _config(db, tenant_id)
    salida = []
    for o in ordenes:
        items = pendientes(o)
        if not items:
            continue
        montos = desglose(sum((Decimal(i.precio_unitario) * i.cantidad for i in items), Decimal("0")), config)
        cobrado = sum((Decimal(i.precio_unitario) * i.cantidad for i in o.items if not i.anulado and i.venta_id), Decimal("0"))
        salida.append({
            "id": o.id, "numero": o.numero, "tipo": o.tipo, "mesa_nombre": o.mesa.nombre if o.mesa else None,
            "cliente_nombre": o.cliente_nombre, "mesero_nombre": o.mesero_nombre, "created_at": o.created_at,
            "estado_cocina": estado_cocina(o), "por_cobrar": montos["total"], "ya_cobrado": pesos(cobrado),
            "platos": sum(i.cantidad for i in items),
        })
    return salida


def resumen_por_medio(db: Session, caja_ids: list) -> dict:
    filas = (
        db.query(models.Venta.caja_id, models.VentaPago.medio, func.sum(models.VentaPago.monto))
        .join(models.Venta, models.Venta.id == models.VentaPago.venta_id)
        .filter(models.Venta.caja_id.in_(caja_ids), models.Venta.estado == "completada")
        .group_by(models.Venta.caja_id, models.VentaPago.medio)
        .all()
    )
    salida: dict = defaultdict(dict)
    for caja_id, medio, total in filas:
        salida[caja_id][medio] = pesos(total)
    return salida
