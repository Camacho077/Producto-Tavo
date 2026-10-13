"""
Reglas de las órdenes (fase 4). Todo lo que mueve inventario pasa por aquí y
se hace en UNA transacción: o la orden queda numerada, con sus insumos
descontados y su comanda lista para imprimir, o no queda nada.
"""
import re
import uuid
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import exists, func, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError, NotFoundError
from app.core.tiempo import ahora_utc
from app.db.models import Tenant
from app.modules.ajustes.models import Mesa
from app.modules.ajustes.schemas import ConfiguracionRestaurante, configuracion_de
from app.modules.ajustes.services import fecha_jornada, obtener_mesa_o_404
from app.modules.catalogo import recetas
from app.modules.catalogo.models import Producto
from app.modules.catalogo.services import agotado_hoy, opciones_carga_producto, vigente
from app.modules.inventario import services as inventario
from app.modules.inventario.unidades import redondear
from app.modules.ordenes import models, schemas
from app.modules.seguridad.models import Usuario

NOMBRE_TIPO = {"local": "en el local", "llevar": "para llevar", "domicilio": "a domicilio"}
NOMBRE_ORIGEN = {"local": "en el local", "llamada": "por llamada", "whatsapp": "por WhatsApp"}
ORDEN_COCINA = {"entrante": 0, "en_preparacion": 1, "lista": 2, "entregada": 3}


def codigo_orden(o: models.Orden) -> str:
    """Código del documento (historial de inventario, factura): único en el
    tiempo. En pantalla la orden se nombra por su número de jornada (#5)."""
    return f"ORD-{o.jornada:%y%m%d}-{o.numero:03d}"


def obtener_orden_o_404(db: Session, tenant_id: uuid.UUID, orden_id: uuid.UUID) -> models.Orden:
    return obtener_del_tenant(db, models.Orden, tenant_id, orden_id, "La orden indicada")


def opciones_carga_orden(detalle: bool = False):
    opciones = [joinedload(models.Orden.mesa), selectinload(models.Orden.items), selectinload(models.Orden.comandas)]
    if detalle:
        opciones.append(selectinload(models.Orden.eventos))
    return opciones


# ---------------------------------------------------------------------------
# Estado de cocina
# ---------------------------------------------------------------------------
def comandas_vivas(o: models.Orden) -> list[models.Comanda]:
    return [c for c in o.comandas if c.estado != "anulada"]


def estado_cocina(o: models.Orden) -> str | None:
    """El de la comanda más atrasada: con una comanda entregada y otra
    entrando, la orden está "entrante" (todavía falta algo)."""
    if o.estado != "abierta":
        return None
    vivas = comandas_vivas(o)
    if not vivas:
        return None
    return min((c.estado for c in vivas), key=ORDEN_COCINA.__getitem__)


def filtro_activa():
    """SQL: orden abierta con alguna comanda que todavía no se entregó."""
    return exists().where(
        models.Comanda.orden_id == models.Orden.id,
        models.Comanda.estado.in_(("entrante", "en_preparacion", "lista")),
    )


# ---------------------------------------------------------------------------
# Serialización
# ---------------------------------------------------------------------------
def _serializar_item(it: models.OrdenItem, numeros: dict, ver_costos: bool) -> dict:
    return {
        "id": it.id,
        "comanda_id": it.comanda_id,
        "comanda_numero": numeros.get(it.comanda_id, 1),
        "producto_id": it.producto_id,
        "nombre": it.nombre,
        "cantidad": it.cantidad,
        "precio_unitario": it.precio_unitario,
        "subtotal": Decimal(it.precio_unitario) * it.cantidad,
        "costo_unitario": it.costo_unitario if ver_costos else None,
        "modificadores": it.modificadores or [],
        "nota": it.nota,
        "va_a_cocina": it.va_a_cocina,
        "anulado": it.anulado,
        "anulado_motivo": it.anulado_motivo,
    }


def resumen(o: models.Orden) -> str:
    activos = [i for i in o.items if not i.anulado]
    return ", ".join(f"{i.cantidad}× {i.nombre}" for i in activos)


def serializar_orden(o: models.Orden, ver_costos: bool = False, detalle: bool = False) -> dict:
    numeros = {c.id: c.numero for c in o.comandas}
    activos = [i for i in o.items if not i.anulado]
    datos = {
        "id": o.id,
        "jornada": o.jornada,
        "numero": o.numero,
        "codigo": codigo_orden(o),
        "tipo": o.tipo,
        "origen": o.origen,
        "mesa_id": o.mesa_id,
        "mesa_nombre": o.mesa.nombre if o.mesa else None,
        "cliente_nombre": o.cliente_nombre,
        "cliente_telefono": o.cliente_telefono,
        "cliente_direccion": o.cliente_direccion,
        "nota": o.nota,
        "estado": o.estado,
        "estado_cocina": estado_cocina(o),
        "total": o.total,
        "mesero_nombre": o.mesero_nombre,
        "anulada_motivo": o.anulada_motivo,
        "platos": sum(i.cantidad for i in activos),
        "resumen": resumen(o),
        "created_at": o.created_at,
        "cerrada_en": o.cerrada_en,
        "items": [_serializar_item(i, numeros, ver_costos) for i in o.items],
        "comandas": [
            {
                "id": c.id, "numero": c.numero, "estado": c.estado, "va_a_cocina": c.va_a_cocina, "created_at": c.created_at,
                "tomada_en": c.tomada_en, "tomada_por": c.tomada_por, "lista_en": c.lista_en, "lista_por": c.lista_por,
                "entregada_en": c.entregada_en, "entregada_por": c.entregada_por,
            }
            for c in o.comandas
        ],
        "eventos": [],
    }
    if detalle:
        datos["eventos"] = [
            {"id": e.id, "tipo": e.tipo, "nota": e.nota, "usuario_nombre": e.usuario_nombre, "created_at": e.created_at}
            for e in o.eventos
        ]
    return datos


# ---------------------------------------------------------------------------
# Tomar el pedido
# ---------------------------------------------------------------------------
def _config(db: Session, tenant_id: uuid.UUID) -> ConfiguracionRestaurante:
    return configuracion_de(db.get(Tenant, tenant_id))


def _validar_encabezado(db: Session, tenant_id: uuid.UUID, datos: schemas.DatosOrden, config: ConfiguracionRestaurante) -> None:
    if datos.tipo not in config.tipos_orden:
        raise ConflictError(f"El restaurante no tiene habilitadas las órdenes {NOMBRE_TIPO[datos.tipo]}: actívalas en Ajustes → Operación.")
    if datos.origen not in config.origenes:
        raise ConflictError(f"El restaurante no recibe órdenes {NOMBRE_ORIGEN[datos.origen]}: actívalo en Ajustes → Operación.")
    if datos.mesa_id:
        mesa = obtener_mesa_o_404(db, tenant_id, datos.mesa_id)
        if not mesa.activo:
            raise ConflictError(f"La mesa {mesa.nombre} está deshabilitada: elige otra o actívala en Ajustes → Mesas.")


def _preparar(db: Session, tenant_id: uuid.UUID, items: list[schemas.ItemPedido], jornada: date) -> list[tuple]:
    """Valida cada plato pedido (existe, está activo, vigente, no agotado y
    sus modificadores son suyos) y devuelve (producto, item, modificadores)."""
    ids = {i.producto_id for i in items}
    productos = {
        p.id: p
        for p in db.query(Producto).options(*opciones_carga_producto()).filter(Producto.tenant_id == tenant_id, Producto.id.in_(ids)).all()
    }
    preparados = []
    for item in items:
        p = productos.get(item.producto_id)
        if p is None:
            raise NotFoundError("Uno de los platos de la orden ya no existe o pertenece a otra empresa: recarga la carta.")
        if not p.activo:
            raise ConflictError(f"{p.nombre} ya no está en la carta (está inactivo): quítalo de la orden.")
        if not vigente(p, jornada):
            raise ConflictError(f"{p.nombre} no está vigente hoy: quítalo de la orden.")
        if agotado_hoy(p, jornada):
            raise ConflictError(f"{p.nombre} está agotado hoy: quítalo de la orden.")
        disponibles = {m.id: m for m in p.modificadores if m.activo}
        mods = []
        for mid in dict.fromkeys(item.modificador_ids):
            if mid not in disponibles:
                raise ConflictError(f"Uno de los modificadores pedidos no es de {p.nombre} o ya no está activo: recarga la carta.")
            mods.append(disponibles[mid])
        preparados.append((p, item, mods))
    return preparados


def _va_a_cocina(p: Producto) -> bool:
    return p.va_a_cocina if p.tipo == "plato" else any(c.producto.va_a_cocina for c in p.componentes)


def _nueva_comanda(
    db: Session, orden: models.Orden, preparados: list[tuple], usuario_nombre: str | None,
    config: ConfiguracionRestaurante, ahora: datetime, accion: str,
) -> models.Comanda:
    tenant_id = orden.tenant_id
    va = any(_va_a_cocina(p) for p, _, _ in preparados)
    comanda = models.Comanda(
        tenant_id=tenant_id, numero=len(orden.comandas) + 1, va_a_cocina=va,
        estado="entrante" if va else "lista", lista_en=None if va else ahora, created_at=ahora, updated_at=ahora,
    )
    orden.comandas.append(comanda)
    total_consumo: dict = defaultdict(lambda: Decimal("0"))
    productos_error = []
    posicion = len(orden.items)
    for p, item, mods in preparados:
        extras = sum((Decimal(m.precio) for m in mods if m.tipo == "extra"), Decimal("0"))
        consumo = recetas.consumo([recetas.LineaVendida(p, item.cantidad, mods)])
        for insumo_id, cantidad in consumo.items():
            total_consumo[insumo_id] += cantidad
        productos_error.append({"producto_id": str(p.id), "nombre": p.nombre, "insumo_ids": [str(i) for i in consumo]})
        it = models.OrdenItem(
            tenant_id=tenant_id, producto_id=p.id, nombre=p.nombre, cantidad=item.cantidad,
            precio_unitario=Decimal(p.precio) + extras, costo_unitario=recetas.costo_unitario_vendido(p, mods),
            modificadores=[{"id": str(m.id), "tipo": m.tipo, "nombre": m.nombre, "precio": str(m.precio)} for m in mods],
            nota=item.nota, va_a_cocina=_va_a_cocina(p),
            consumo={str(i): str(redondear(c)) for i, c in consumo.items() if redondear(c) > 0},
            posicion=posicion, comanda=comanda,
        )
        posicion += 1
        orden.items.append(it)
    db.flush()
    inventario.descontar(
        db, tenant_id, dict(total_consumo),
        tipo="venta", documento_tipo="orden", documento_id=orden.id, documento_codigo=codigo_orden(orden),
        usuario_nombre=usuario_nombre, accion=accion, quien="la orden",
        permitir_negativo=config.vender_sin_existencias, datos_error={"productos": productos_error}, fecha=ahora,
    )
    _recalcular_total(orden)
    return comanda


def _recalcular_total(orden: models.Orden) -> None:
    orden.total = sum((Decimal(i.precio_unitario) * i.cantidad for i in orden.items if not i.anulado), Decimal("0"))


def registrar_evento(orden: models.Orden, tipo: str, nota: str | None, usuario_nombre: str | None, ahora: datetime) -> None:
    orden.eventos.append(models.OrdenEvento(
        tenant_id=orden.tenant_id, tipo=tipo, nota=nota, usuario_nombre=usuario_nombre, created_at=ahora, updated_at=ahora,
    ))


def _siguiente_numero(db: Session, tenant_id: uuid.UUID, jornada: date) -> int:
    """Consecutivo de la jornada. El candado de transacción por (empresa,
    jornada) evita que dos meseros que envían a la vez saquen el mismo
    número; se suelta solo al terminar la transacción."""
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:clave))"), {"clave": f"orden:{tenant_id}:{jornada}"})
    actual = (
        db.query(func.coalesce(func.max(models.Orden.numero), 0))
        .filter(models.Orden.tenant_id == tenant_id, models.Orden.jornada == jornada)
        .scalar()
    )
    return int(actual) + 1


def crear_orden(
    db: Session, usuario: Usuario, payload: schemas.OrdenCreate, ahora: datetime | None = None,
) -> models.Orden:
    """Numera la orden, descuenta los insumos de sus recetas y deja su
    comanda 1, todo en una transacción. `ahora` solo lo usan los datos de
    demostración (la API siempre toma la hora del servidor)."""
    tenant_id = usuario.tenant_id
    ahora = ahora or ahora_utc()
    config = _config(db, tenant_id)
    _validar_encabezado(db, tenant_id, payload, config)
    jornada = fecha_jornada(config, ahora)
    preparados = _preparar(db, tenant_id, payload.items, jornada)
    orden = models.Orden(
        tenant_id=tenant_id, jornada=jornada, numero=_siguiente_numero(db, tenant_id, jornada),
        tipo=payload.tipo, origen=payload.origen, mesa_id=payload.mesa_id, cliente_nombre=payload.cliente_nombre,
        cliente_telefono=payload.cliente_telefono, cliente_direccion=payload.cliente_direccion, nota=payload.nota,
        estado="abierta", total=Decimal("0"), mesero_id=usuario.id, mesero_nombre=usuario.nombre_completo,
        created_at=ahora, updated_at=ahora,
    )
    db.add(orden)
    try:
        db.flush()
        _nueva_comanda(db, orden, preparados, usuario.nombre_completo, config, ahora, accion="enviar la orden")
    except ConflictError:
        db.rollback()
        raise
    registrar_evento(orden, "creada", f"Orden {NOMBRE_TIPO[orden.tipo]}, {NOMBRE_ORIGEN[orden.origen]}", usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(orden)
    return orden


def _exigir_abierta(orden: models.Orden, accion: str) -> None:
    if orden.estado != "abierta":
        raise ConflictError(f"No se puede {accion} la orden #{orden.numero}: ya está {orden.estado}.")


def agregar_items(
    db: Session, usuario: Usuario, orden_id: uuid.UUID, payload: schemas.ItemsAgregar, ahora: datetime | None = None,
) -> tuple[models.Orden, models.Comanda]:
    """Platos nuevos en una orden ya enviada: sale una comanda SOLO con lo
    nuevo y se descuenta solo lo nuevo."""
    ahora = ahora or ahora_utc()
    tenant_id = usuario.tenant_id
    orden = obtener_orden_o_404(db, tenant_id, orden_id)
    _exigir_abierta(orden, "agregarle platos a")
    config = _config(db, tenant_id)
    preparados = _preparar(db, tenant_id, payload.items, fecha_jornada(config, ahora))
    try:
        comanda = _nueva_comanda(db, orden, preparados, usuario.nombre_completo, config, ahora, accion=f"agregar platos a la orden #{orden.numero}")
    except ConflictError:
        db.rollback()
        raise
    agregados = ", ".join(f"{i.cantidad}× {p.nombre}" for p, i, _ in preparados)
    registrar_evento(orden, "agregado", f"Comanda {comanda.numero}: {agregados}", usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(orden)
    return orden, comanda


def editar_encabezado(db: Session, usuario: Usuario, orden_id: uuid.UUID, payload: schemas.DatosOrden) -> models.Orden:
    tenant_id = usuario.tenant_id
    orden = obtener_orden_o_404(db, tenant_id, orden_id)
    _exigir_abierta(orden, "editar")
    _validar_encabezado(db, tenant_id, payload, _config(db, tenant_id))
    for campo in ("tipo", "origen", "mesa_id", "cliente_nombre", "cliente_telefono", "cliente_direccion", "nota"):
        setattr(orden, campo, getattr(payload, campo))
    registrar_evento(orden, "editada", "Datos de la orden actualizados", usuario.nombre_completo, ahora_utc())
    db.commit()
    db.refresh(orden)
    return orden


def _devolver_items(db: Session, orden: models.Orden, items: list[models.OrdenItem], usuario_nombre: str | None, motivo: str, ahora: datetime) -> None:
    """Devuelve a la bodega EXACTAMENTE lo que esos platos sacaron."""
    total: dict = defaultdict(lambda: Decimal("0"))
    for it in items:
        for insumo_id, cantidad in (it.consumo or {}).items():
            total[uuid.UUID(insumo_id)] += Decimal(cantidad)
    insumos = inventario.bloquear_insumos(db, orden.tenant_id, total.keys())
    for insumo_id, cantidad in total.items():
        if insumo_id in insumos and cantidad > 0:
            inventario.registrar(
                db, orden.tenant_id, insumos[insumo_id], "anulacion_orden", cantidad,
                documento_tipo="orden", documento_id=orden.id, documento_codigo=codigo_orden(orden),
                usuario_nombre=usuario_nombre, motivo=motivo, permitir_negativo=True, fecha=ahora,
            )


def anular_item(
    db: Session, usuario: Usuario, orden_id: uuid.UUID, item_id: uuid.UUID, motivo: str, ahora: datetime | None = None,
) -> models.Orden:
    ahora = ahora or ahora_utc()
    orden = obtener_orden_o_404(db, usuario.tenant_id, orden_id)
    _exigir_abierta(orden, "quitar platos de")
    item = next((i for i in orden.items if i.id == item_id), None)
    if item is None:
        raise NotFoundError("El plato indicado no está en esta orden: recarga la pantalla.")
    if item.anulado:
        raise ConflictError(f"{item.nombre} ya estaba anulado en la orden #{orden.numero}.")
    if not [i for i in orden.items if not i.anulado and i.id != item.id]:
        raise ConflictError(f"{item.nombre} es lo único que queda en la orden #{orden.numero}: anula la orden completa.")
    _devolver_items(db, orden, [item], usuario.nombre_completo, motivo, ahora)
    item.anulado = True
    item.anulado_motivo = motivo
    comanda = item.comanda
    if all(i.anulado for i in comanda.items) and comanda.estado != "entregada":
        comanda.estado = "anulada"
    _recalcular_total(orden)
    registrar_evento(orden, "item_anulado", f"{item.cantidad}× {item.nombre}: {motivo}", usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(orden)
    return orden


def anular_orden(db: Session, usuario: Usuario, orden_id: uuid.UUID, motivo: str, ahora: datetime | None = None) -> models.Orden:
    """Antes de cobrarla: devuelve los insumos de todo lo que seguía en pie y
    retira sus comandas de la cocina."""
    ahora = ahora or ahora_utc()
    orden = obtener_orden_o_404(db, usuario.tenant_id, orden_id)
    _exigir_abierta(orden, "anular")
    _devolver_items(db, orden, [i for i in orden.items if not i.anulado], usuario.nombre_completo, motivo, ahora)
    for c in orden.comandas:
        if c.estado != "entregada":
            c.estado = "anulada"
    orden.estado = "anulada"
    orden.anulada_motivo = motivo
    orden.cerrada_en = ahora
    registrar_evento(orden, "anulada", motivo, usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(orden)
    return orden


def entregar(db: Session, usuario: Usuario, orden_id: uuid.UUID, ahora: datetime | None = None) -> models.Orden:
    """El mesero entrega lo que la cocina dejó listo."""
    ahora = ahora or ahora_utc()
    orden = obtener_orden_o_404(db, usuario.tenant_id, orden_id)
    _exigir_abierta(orden, "entregar")
    listas = [c for c in orden.comandas if c.estado == "lista"]
    if not listas:
        pendientes = [c for c in comandas_vivas(orden) if c.estado in ("entrante", "en_preparacion")]
        if pendientes:
            raise ConflictError(
                f"Nada de la orden #{orden.numero} está listo todavía: la cocina tiene la comanda {pendientes[0].numero} "
                f"{'en preparación' if pendientes[0].estado == 'en_preparacion' else 'por empezar'}."
            )
        raise ConflictError(f"La orden #{orden.numero} ya se entregó completa.")
    for c in listas:
        c.estado = "entregada"
        c.entregada_en = ahora
        c.entregada_por = usuario.nombre_completo
    registrar_evento(orden, "entregada", ", ".join(f"Comanda {c.numero}" for c in listas), usuario.nombre_completo, ahora)
    db.commit()
    db.refresh(orden)
    return orden


def marcar_agotado(db: Session, usuario: Usuario, producto_id: uuid.UUID) -> Producto:
    """"Agotado hoy" desde la toma de pedidos, cuando un insumo no alcanza."""
    producto = obtener_del_tenant(db, Producto, usuario.tenant_id, producto_id, "El plato indicado")
    producto.agotado_fecha = fecha_jornada(_config(db, usuario.tenant_id), ahora_utc())
    db.commit()
    return producto


# ---------------------------------------------------------------------------
# Mesas y jornada
# ---------------------------------------------------------------------------
def estado_mesas(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    mesas = (
        db.query(Mesa).options(joinedload(Mesa.zona))
        .filter(Mesa.tenant_id == tenant_id, Mesa.activo.is_(True)).all()
    )
    abiertas = (
        db.query(models.Orden).options(selectinload(models.Orden.comandas), selectinload(models.Orden.items))
        .filter(models.Orden.tenant_id == tenant_id, models.Orden.estado == "abierta", models.Orden.mesa_id.isnot(None))
        .order_by(models.Orden.created_at).all()
    )
    por_mesa = defaultdict(list)
    for o in abiertas:
        por_mesa[o.mesa_id].append(o)
    salida = []
    for m in mesas:
        ordenes = por_mesa.get(m.id, [])
        if not ordenes:
            estado = "libre"
        elif any(estado_cocina(o) in ("entrante", "en_preparacion", "lista") for o in ordenes):
            estado = "ocupada"
        else:
            estado = "por_cobrar"
        salida.append({
            "id": m.id, "nombre": m.nombre, "zona_id": m.zona_id, "zona_nombre": m.zona.nombre if m.zona else None,
            "zona_orden": m.zona.orden if m.zona else 999, "puestos": m.puestos, "estado": estado,
            "ordenes": [
                {"id": o.id, "numero": o.numero, "total": o.total, "estado_cocina": estado_cocina(o), "created_at": o.created_at}
                for o in ordenes
            ],
        })
    salida.sort(key=lambda m: (m["zona_orden"], _clave_natural(m["nombre"])))
    return salida


def _clave_natural(nombre: str) -> tuple:
    """"B2" antes que "B10"."""
    return tuple(int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", nombre))


def resumen_jornada(db: Session, tenant_id: uuid.UUID, jornada: date) -> dict:
    base = db.query(models.Orden).filter(models.Orden.tenant_id == tenant_id, models.Orden.jornada == jornada)
    en_curso = base.filter(models.Orden.estado == "abierta", filtro_activa()).count()
    total = base.filter(models.Orden.estado != "anulada").count()
    return {"jornada": jornada, "en_curso": en_curso, "ordenes": total}
