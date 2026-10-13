"""
INVENTARIO DE INSUMOS — la única puerta para mover existencias.

`registrar` aplica una cantidad (con signo) a un insumo y deja su movimiento
con quién, cuándo, cuánto, por qué y a qué costo. `descontar` y `devolver`
mueven VARIOS insumos a la vez (lo que gasta una venta o una orden según sus
recetas): `descontar` valida TODO antes de mover nada, así una orden que no
alcanza no deja la mitad del inventario descontado.
"""
import uuid
from datetime import timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError, NotFoundError
from app.modules.inventario import models
from app.modules.inventario.unidades import compatibles, convertir, legible, redondear

CENTAVOS = Decimal("0.01")
CUATRO_DECIMALES = Decimal("0.0001")


def obtener_insumo_o_404(db: Session, tenant_id: uuid.UUID, insumo_id: uuid.UUID) -> models.Insumo:
    return obtener_del_tenant(db, models.Insumo, tenant_id, insumo_id, "El insumo indicado")


def bajo_minimo(insumo: models.Insumo) -> bool:
    return bool(insumo.activo and insumo.minimo and insumo.minimo > 0 and insumo.existencia <= insumo.minimo)


def serializar_insumo(i: models.Insumo, ver_costos: bool = True, platos_count: int = 0, con_proveedores: bool = False) -> dict:
    datos = {
        "id": i.id,
        "nombre": i.nombre,
        "unidad": i.unidad,
        "grupo": i.grupo,
        "existencia": i.existencia,
        "minimo": i.minimo,
        "costo_unitario": i.costo_unitario if ver_costos else None,
        "costo_total": (Decimal(i.existencia) * Decimal(i.costo_unitario)).quantize(CENTAVOS) if ver_costos else None,
        "bajo_minimo": bajo_minimo(i),
        "activo": i.activo,
        "platos_count": platos_count,
        "created_at": i.created_at,
        "updated_at": i.updated_at,
    }
    if con_proveedores:
        from app.modules.compras.models import Proveedor, proveedor_insumos  # evita import circular

        sesion = Session.object_session(i)
        proveedores = (
            sesion.query(Proveedor)
            .join(proveedor_insumos, proveedor_insumos.c.proveedor_id == Proveedor.id)
            .filter(proveedor_insumos.c.insumo_id == i.id)
            .order_by(Proveedor.nombre)
            .all()
        )
        datos["proveedores"] = [{"id": p.id, "nombre": p.nombre} for p in proveedores]
    return datos


def serializar_movimiento(m: models.MovimientoInsumo, ver_costos: bool = True) -> dict:
    return {
        "id": m.id,
        "insumo_id": m.insumo_id,
        "insumo_nombre": m.insumo.nombre if m.insumo else None,
        "unidad": m.insumo.unidad if m.insumo else None,
        "tipo": m.tipo,
        "cantidad": m.cantidad,
        "existencia_resultante": m.existencia_resultante,
        "costo_unitario": m.costo_unitario if ver_costos else None,
        "valor": m.valor if ver_costos else None,
        "documento_tipo": m.documento_tipo,
        "documento_id": m.documento_id,
        "documento_codigo": m.documento_codigo,
        "motivo": m.motivo,
        "usuario_nombre": m.usuario_nombre,
        "created_at": m.created_at,
    }


def registrar(
    db: Session,
    tenant_id: uuid.UUID,
    insumo: models.Insumo,
    tipo: str,
    cantidad: Decimal,
    *,
    documento_tipo: str | None = None,
    documento_id: uuid.UUID | None = None,
    documento_codigo: str | None = None,
    motivo: str | None = None,
    usuario_nombre: str | None = None,
    costo_entrada: Decimal | None = None,
    permitir_negativo: bool = False,
    fecha=None,
) -> models.MovimientoInsumo:
    """Aplica `cantidad` (con signo, en la unidad del insumo).

    `costo_entrada` (costo de UNA unidad del insumo en esta entrada) actualiza
    el costo por PROMEDIO PONDERADO: lo que había vale lo que costó y lo que
    entra vale lo que se pagó. Las salidas no cambian el costo: se valoran al
    costo vigente, y esa es la cifra del costo de lo vendido."""
    cantidad = redondear(cantidad)
    existencia = Decimal(insumo.existencia)
    nueva = existencia + cantidad
    if nueva < 0 and not permitir_negativo:
        raise ConflictError(
            f"No se pudo registrar el movimiento de {insumo.nombre}: quedan {legible(existencia, insumo.unidad)} "
            f"y se intentó sacar {legible(-cantidad, insumo.unidad)}."
        )
    if cantidad > 0 and costo_entrada is not None:
        base = max(existencia, Decimal("0"))
        insumo.costo_unitario = ((base * Decimal(insumo.costo_unitario) + cantidad * Decimal(costo_entrada)) / (base + cantidad)).quantize(CUATRO_DECIMALES)
    costo = Decimal(insumo.costo_unitario)
    insumo.existencia = nueva
    movimiento = models.MovimientoInsumo(
        tenant_id=tenant_id,
        insumo_id=insumo.id,
        tipo=tipo,
        cantidad=cantidad,
        existencia_resultante=nueva,
        costo_unitario=costo,
        valor=(cantidad * costo).quantize(CENTAVOS),
        documento_tipo=documento_tipo,
        documento_id=documento_id,
        documento_codigo=documento_codigo,
        motivo=motivo,
        usuario_nombre=usuario_nombre,
    )
    if fecha is not None:
        movimiento.created_at = fecha.replace(tzinfo=None) if fecha.tzinfo is None else fecha.astimezone(timezone.utc).replace(tzinfo=None)
    db.add(movimiento)
    return movimiento


def revertir_costo_de_entrada(insumo: models.Insumo, cantidad: Decimal, costo_entrada: Decimal) -> None:
    """Al anular una entrada valorizada (una compra), se saca su peso del
    promedio: costo = (existencia × costo − cantidad × costo_entrada) /
    (existencia − cantidad). Si el resultado no tiene sentido (queda sin
    existencia o el costo saldría negativo porque después hubo más
    movimientos), se conserva el costo vigente."""
    existencia = Decimal(insumo.existencia)
    resto = existencia - cantidad
    if resto <= 0:
        return
    nuevo = (existencia * Decimal(insumo.costo_unitario) - cantidad * Decimal(costo_entrada)) / resto
    if nuevo > 0:
        insumo.costo_unitario = nuevo.quantize(CUATRO_DECIMALES)


def bloquear_insumos(db: Session, tenant_id: uuid.UUID, ids) -> dict[uuid.UUID, models.Insumo]:
    """Lee los insumos CON BLOQUEO de fila (SELECT … FOR UPDATE): dos órdenes
    que gastan el mismo queso al mismo tiempo no pueden leer las dos "quedan
    300 g" y dejarlo en negativo. Orden fijo por id para no tener bloqueos
    cruzados."""
    ids = sorted(set(ids), key=str)
    if not ids:
        return {}
    filas = (
        db.query(models.Insumo)
        .filter(models.Insumo.tenant_id == tenant_id, models.Insumo.id.in_(ids))
        .order_by(models.Insumo.id)
        .with_for_update()
        .all()
    )
    return {i.id: i for i in filas}


def faltantes(insumos: dict, consumo: dict[uuid.UUID, Decimal]) -> list[dict]:
    """Los insumos cuya existencia no alcanza para `consumo`."""
    lista = []
    for insumo_id, necesita in consumo.items():
        insumo = insumos[insumo_id]
        if necesita > 0 and Decimal(insumo.existencia) < necesita:
            lista.append({"insumo": insumo, "quedan": Decimal(insumo.existencia), "necesita": necesita})
    return lista


def mensaje_faltantes(accion: str, quien: str, lista: list[dict]) -> str:
    """"No se pudo enviar la orden: quedan 200 g de Queso y la orden necesita
    300 g." Con varios insumos, los nombra todos (hasta tres)."""
    partes = [
        f"quedan {legible(max(f['quedan'], Decimal('0')), f['insumo'].unidad)} de {f['insumo'].nombre} "
        f"y {quien} necesita {legible(f['necesita'], f['insumo'].unidad)}"
        for f in lista[:3]
    ]
    resto = len(lista) - len(partes)
    texto = "; ".join(partes) + (f"; y {resto} insumo(s) más" if resto > 0 else "")
    return f"No se pudo {accion}: {texto}."


def descontar(
    db: Session,
    tenant_id: uuid.UUID,
    consumo: dict[uuid.UUID, Decimal],
    *,
    tipo: str,
    documento_tipo: str,
    documento_id: uuid.UUID,
    documento_codigo: str,
    usuario_nombre: str | None,
    accion: str,
    quien: str,
    permitir_negativo: bool = False,
    datos_error: dict | None = None,
    fecha=None,
) -> list[models.MovimientoInsumo]:
    """Saca de la bodega lo que gasta un documento (venta u orden). Valida
    TODO primero; si un insumo no alcanza, no mueve nada y responde 409 con
    la causa exacta y, en `datos`, los insumos que faltan."""
    consumo = {i: redondear(c) for i, c in consumo.items() if redondear(c) > 0}
    insumos = bloquear_insumos(db, tenant_id, consumo.keys())
    if not permitir_negativo:
        lista = faltantes(insumos, consumo)
        if lista:
            datos = {
                "faltantes": [
                    {
                        "insumo_id": str(f["insumo"].id),
                        "insumo": f["insumo"].nombre,
                        "unidad": f["insumo"].unidad,
                        "quedan": str(f["quedan"]),
                        "necesita": str(f["necesita"]),
                    }
                    for f in lista
                ],
                **(datos_error or {}),
            }
            raise ConflictError(mensaje_faltantes(accion, quien, lista), datos=datos)
    return [
        registrar(
            db, tenant_id, insumos[insumo_id], tipo, -cantidad,
            documento_tipo=documento_tipo, documento_id=documento_id, documento_codigo=documento_codigo,
            usuario_nombre=usuario_nombre, permitir_negativo=True, fecha=fecha,
        )
        for insumo_id, cantidad in consumo.items()
    ]


def devolver_documento(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    tipo_original: str,
    tipo: str,
    documento_tipo: str,
    documento_id: uuid.UUID,
    documento_codigo: str,
    usuario_nombre: str | None,
    motivo: str | None = None,
) -> list[models.MovimientoInsumo]:
    """Devuelve a la bodega EXACTAMENTE lo que un documento sacó (lee sus
    movimientos, no recalcula la receta: si la receta cambió después, se
    devuelve lo que de verdad salió)."""
    salidas = (
        db.query(models.MovimientoInsumo.insumo_id, func.sum(models.MovimientoInsumo.cantidad))
        .filter(
            models.MovimientoInsumo.tenant_id == tenant_id,
            models.MovimientoInsumo.documento_id == documento_id,
            models.MovimientoInsumo.tipo == tipo_original,
        )
        .group_by(models.MovimientoInsumo.insumo_id)
        .all()
    )
    insumos = bloquear_insumos(db, tenant_id, [i for i, _ in salidas])
    return [
        registrar(
            db, tenant_id, insumos[insumo_id], tipo, -Decimal(total),
            documento_tipo=documento_tipo, documento_id=documento_id, documento_codigo=documento_codigo,
            usuario_nombre=usuario_nombre, motivo=motivo, permitir_negativo=True,
        )
        for insumo_id, total in salidas
        if total and Decimal(total) < 0
    ]


def costo_de_documento(db: Session, tenant_id: uuid.UUID, documento_id: uuid.UUID, tipo: str) -> Decimal:
    """Costo de lo que salió por un documento (suma de los `valor`, en positivo)."""
    total = (
        db.query(func.coalesce(func.sum(models.MovimientoInsumo.valor), 0))
        .filter(
            models.MovimientoInsumo.tenant_id == tenant_id,
            models.MovimientoInsumo.documento_id == documento_id,
            models.MovimientoInsumo.tipo == tipo,
        )
        .scalar()
    )
    return -Decimal(total or 0)


# ---------------------------------------------------------------------------
# Mermas y conteos físicos (fase 3). `ahora` solo lo usan los datos de
# demostración: la API siempre registra la hora del servidor.
# ---------------------------------------------------------------------------
def codigo_conteo(numero: int) -> str:
    return f"CON-{numero:06d}"


def registrar_merma(db: Session, usuario, insumo_id: uuid.UUID, payload, ahora=None) -> models.MovimientoInsumo:
    """Salida que no es venta (vencido, dañado, derramado…), siempre con su
    motivo. No puede dejar la existencia en negativo: si se perdió más de lo
    que dice el sistema, lo que corresponde es un conteo físico."""
    tenant_id = usuario.tenant_id
    insumo = bloquear_insumos(db, tenant_id, [insumo_id]).get(insumo_id)
    if insumo is None:
        obtener_insumo_o_404(db, tenant_id, insumo_id)
    if not compatibles(payload.unidad, insumo.unidad):
        raise ConflictError(f"{insumo.nombre} se lleva en {insumo.unidad}: la merma no puede ir en {payload.unidad}.")
    cantidad = convertir(payload.cantidad, payload.unidad, insumo.unidad)
    if Decimal(insumo.existencia) < cantidad:
        raise ConflictError(
            f"No se pudo registrar la merma de {insumo.nombre}: quedan {legible(insumo.existencia, insumo.unidad)} "
            f"y se intentó sacar {legible(cantidad, insumo.unidad)}. Si en la bodega hay menos de lo que dice el sistema, haz un conteo físico."
        )
    motivo = models.MOTIVOS_MERMA[payload.motivo] + (f": {payload.detalle}" if payload.detalle else "")
    movimiento = registrar(db, tenant_id, insumo, "merma", -cantidad, motivo=motivo, usuario_nombre=usuario.nombre_completo, fecha=ahora)
    db.commit()
    db.refresh(movimiento)
    return movimiento


def registrar_conteo(db: Session, usuario, payload, ahora=None) -> models.Conteo:
    """Ajuste por conteo físico: por cada insumo contado se compara con el
    sistema y la diferencia queda como movimiento "ajuste" (con su valor a
    costo) que apunta a este conteo. La existencia queda igual a lo contado."""
    tenant_id = usuario.tenant_id
    ids = [l.insumo_id for l in payload.lineas]
    if len(set(ids)) != len(ids):
        raise ConflictError("El conteo repite un insumo: cada insumo va una sola vez.")
    insumos = bloquear_insumos(db, tenant_id, ids)
    if len(insumos) != len(set(ids)):
        raise NotFoundError("Uno de los insumos contados ya no existe o pertenece a otra empresa: recarga la pantalla.")
    numero = (db.query(func.coalesce(func.max(models.Conteo.numero), 0)).filter(models.Conteo.tenant_id == tenant_id).scalar() or 0) + 1
    conteo = models.Conteo(tenant_id=tenant_id, numero=numero, motivo=payload.motivo, usuario_nombre=usuario.nombre_completo)
    if ahora is not None:
        conteo.created_at = conteo.updated_at = ahora
    db.add(conteo)
    db.flush()
    codigo = codigo_conteo(numero)
    total = Decimal("0")
    for i, linea in enumerate(payload.lineas):
        insumo = insumos[linea.insumo_id]
        sistema = Decimal(insumo.existencia)
        diferencia = Decimal(linea.contado) - sistema
        costo = Decimal(insumo.costo_unitario)
        valor = (diferencia * costo).quantize(Decimal("0.01"))
        total += valor
        conteo.items.append(models.ConteoItem(
            tenant_id=tenant_id, insumo_id=insumo.id, sistema=sistema, contado=linea.contado,
            diferencia=diferencia, costo_unitario=costo, valor=valor, orden=i,
        ))
        if diferencia != 0:
            registrar(
                db, tenant_id, insumo, "ajuste", diferencia,
                documento_tipo="conteo", documento_id=conteo.id, documento_codigo=codigo,
                motivo=payload.motivo or "Conteo físico", usuario_nombre=usuario.nombre_completo, permitir_negativo=True, fecha=ahora,
            )
    conteo.valor_diferencia = total
    db.commit()
    db.refresh(conteo)
    return conteo
