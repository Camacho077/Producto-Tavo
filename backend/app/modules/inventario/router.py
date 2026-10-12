"""
INSUMOS (2026-10-12): la materia prima con su unidad, existencia (suma de
movimientos, nunca editada a mano), mínimo para alertar, costo unitario
(promedio ponderado de las compras) y costo total. Los costos solo los ve
quien tiene `costos.ver`.
"""
import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core import mensajes
from app.core.consultas import obtener_del_tenant
from app.core.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.core.validaciones import ZONA_NEGOCIO
from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.permisos import tiene_permiso, usuario_con_permiso
from app.db.session import get_db
from app.modules.catalogo.models import RecetaItem
from app.modules.catalogo.services import mensaje_insumo_en_uso
from app.modules.inventario import carga, models, schemas, services
from app.modules.inventario.unidades import compatibles, convertir, legible
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/inventario", tags=["Inventario"])


class CargaConErrores(AppError):
    status_code = 422
    detail = "El archivo tiene errores."


async def leer_archivo_subido(request: Request) -> tuple[bytes, str]:
    """Cuerpo crudo del archivo (Excel o CSV) con su Content-Type."""
    tipo = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > carga.MAX_BYTES:
        raise carga.ArchivoInvalido(f"El archivo pesa {int(declarado) / 1024 / 1024:.1f} MB y el máximo es 5 MB.")
    return await request.body(), tipo

TIPOS_LEGIBLES = {
    "inicial": "Existencia inicial",
    "compra": "Compra",
    "anulacion_compra": "Anulación de compra",
    "venta": "Venta",
    "anulacion_venta": "Anulación de venta",
    "merma": "Merma",
    "ajuste": "Ajuste",
}


def columnas_insumos(ver_costos: bool):
    columnas = [
        ("Insumo", campo("nombre")),
        ("Grupo", campo("grupo")),
        ("Unidad", campo("unidad")),
        ("Existencia", campo("existencia")),
        ("Mínimo", campo("minimo")),
        ("Bajo el mínimo", campo("bajo_minimo")),
    ]
    if ver_costos:
        columnas += [("Costo unitario", campo("costo_unitario")), ("Costo total", campo("costo_total"))]
    return columnas + [("Platos que lo usan", campo("platos_count")), ("Estado", lambda f: "Activo" if f.get("activo") else "Inactivo")]


def _ver_costos(usuario: Usuario) -> bool:
    return tiene_permiso(usuario, "costos", "ver")


def _platos_por_insumo(db: Session, tenant_id: uuid.UUID) -> dict:
    filas = (
        db.query(RecetaItem.insumo_id, func.count(func.distinct(RecetaItem.producto_id)))
        .filter(RecetaItem.tenant_id == tenant_id)
        .group_by(RecetaItem.insumo_id)
        .all()
    )
    return dict(filas)


@router.get("/insumos", response_model=Pagina[schemas.InsumoOut])
def listar_insumos(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    grupo: str | None = Query(default=None, max_length=40),
    bajo_minimo: bool | None = Query(default=None),
    proveedor_id: uuid.UUID | None = Query(default=None, description="Solo los insumos que surte este proveedor"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("insumos", "ver")),
):
    tenant_id = usuario.tenant_id
    query = db.query(models.Insumo).filter(models.Insumo.tenant_id == tenant_id)
    if activo is not None:
        query = query.filter(models.Insumo.activo == activo)
    if grupo:
        query = query.filter(models.Insumo.grupo == grupo)
    if bajo_minimo is not None:
        condicion = (models.Insumo.minimo > 0) & (models.Insumo.existencia <= models.Insumo.minimo)
        query = query.filter(condicion if bajo_minimo else ~condicion)
    if proveedor_id is not None:
        from app.modules.compras.models import proveedor_insumos

        query = query.join(proveedor_insumos, proveedor_insumos.c.insumo_id == models.Insumo.id).filter(
            proveedor_insumos.c.proveedor_id == proveedor_id
        )
    pagina = paginar(query, params, columnas_busqueda=(models.Insumo.nombre, models.Insumo.grupo), orden=models.Insumo.nombre)
    ver_costos = _ver_costos(usuario)
    platos = _platos_por_insumo(db, tenant_id)
    pagina["items"] = [services.serializar_insumo(i, ver_costos, platos.get(i.id, 0)) for i in pagina["items"]]
    return responder(pagina, params, schemas.InsumoOut, columnas_insumos(ver_costos), "insumos")


@router.get("/grupos", response_model=list[str])
def listar_grupos(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("insumos", "ver"))):
    """Grupos ya usados, para sugerirlos al crear un insumo."""
    filas = (
        db.query(models.Insumo.grupo)
        .filter(models.Insumo.tenant_id == usuario.tenant_id, models.Insumo.grupo.isnot(None))
        .distinct()
        .order_by(models.Insumo.grupo)
        .all()
    )
    return [g for (g,) in filas]


@router.get("/insumos/{insumo_id}", response_model=schemas.InsumoOut)
def obtener_insumo(insumo_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("insumos", "ver"))):
    insumo = services.obtener_insumo_o_404(db, usuario.tenant_id, insumo_id)
    platos = _platos_por_insumo(db, usuario.tenant_id)
    return services.serializar_insumo(insumo, _ver_costos(usuario), platos.get(insumo.id, 0), con_proveedores=True)


@router.post("/insumos", response_model=schemas.InsumoOut, status_code=status.HTTP_201_CREATED)
def crear_insumo(payload: schemas.InsumoCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("insumos", "crear"))):
    tenant_id = usuario.tenant_id
    datos = payload.model_dump(exclude={"existencia_inicial"})
    if not _ver_costos(usuario):
        datos["costo_unitario"] = Decimal("0")  # quien no ve costos tampoco los escribe
    insumo = models.Insumo(tenant_id=tenant_id, existencia=Decimal("0"), **datos)
    db.add(insumo)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un insumo", "nombre", payload.nombre))
    if payload.existencia_inicial > 0:
        services.registrar(
            db, tenant_id, insumo, "inicial", payload.existencia_inicial,
            motivo="Existencia al crear el insumo", usuario_nombre=usuario.nombre_completo,
        )
    db.commit()
    db.refresh(insumo)
    return services.serializar_insumo(insumo, _ver_costos(usuario))


@router.put("/insumos/{insumo_id}", response_model=schemas.InsumoOut)
def actualizar_insumo(
    insumo_id: uuid.UUID,
    payload: schemas.InsumoUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("insumos", "editar")),
):
    tenant_id = usuario.tenant_id
    insumo = services.obtener_insumo_o_404(db, tenant_id, insumo_id)
    datos = payload.model_dump(exclude_unset=True)
    if not _ver_costos(usuario):
        datos.pop("costo_unitario", None)
    if "unidad" in datos and datos["unidad"] and datos["unidad"] != insumo.unidad:
        movimientos = db.query(func.count(models.MovimientoInsumo.id)).filter(models.MovimientoInsumo.insumo_id == insumo.id).scalar()
        usos = db.query(func.count(RecetaItem.id)).filter(RecetaItem.insumo_id == insumo.id).scalar()
        if movimientos or usos:
            raise ConflictError(
                f"No se puede cambiar la unidad de {insumo.nombre} de {insumo.unidad} a {datos['unidad']}: "
                "ya tiene movimientos o está en recetas, y sus cantidades quedarían mal. Crea un insumo nuevo."
            )
    for clave, valor in datos.items():
        if valor is not None or clave == "grupo":
            setattr(insumo, clave, valor)
    nombre = insumo.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un insumo", "nombre", nombre))
    db.refresh(insumo)
    return services.serializar_insumo(insumo, _ver_costos(usuario), _platos_por_insumo(db, tenant_id).get(insumo.id, 0))


@router.patch("/insumos/{insumo_id}/estado", response_model=schemas.InsumoOut)
def cambiar_estado_insumo(
    insumo_id: uuid.UUID,
    payload: schemas.CambioEstado,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("insumos", "cambiar_estado")),
):
    insumo = services.obtener_insumo_o_404(db, usuario.tenant_id, insumo_id)
    insumo.activo = payload.activo
    db.commit()
    db.refresh(insumo)
    return services.serializar_insumo(insumo, _ver_costos(usuario))


@router.delete("/insumos/{insumo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_insumo(insumo_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("insumos", "eliminar"))):
    tenant_id = usuario.tenant_id
    insumo = services.obtener_insumo_o_404(db, tenant_id, insumo_id)
    en_uso = mensaje_insumo_en_uso(db, tenant_id, insumo)
    if en_uso:
        raise ConflictError(en_uso)
    movimientos = db.query(func.count(models.MovimientoInsumo.id)).filter(models.MovimientoInsumo.insumo_id == insumo.id).scalar()
    if movimientos:
        raise ConflictError(
            mensajes.no_se_puede_eliminar(
                "el insumo", insumo.nombre, movimientos, "movimiento de inventario", "movimientos de inventario",
                "Desactívalo en su lugar para conservar el historial.",
            )
        )
    nombre = insumo.nombre
    try:
        db.delete(insumo)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            f"No se puede eliminar el insumo {nombre}: aparece en compras o modificadores. Desactívalo en su lugar."
        )


@router.get("/insumos/{insumo_id}/movimientos", response_model=Pagina[schemas.MovimientoOut])
def movimientos_insumo(
    insumo_id: uuid.UUID,
    params: ParametrosPagina = Depends(),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("insumos", "ver")),
):
    """Historial de un insumo: cada entrada y salida con quién, cuándo,
    cuánto, por qué y la existencia que dejó."""
    tenant_id = usuario.tenant_id
    services.obtener_insumo_o_404(db, tenant_id, insumo_id)
    query = (
        db.query(models.MovimientoInsumo)
        .options(joinedload(models.MovimientoInsumo.insumo))
        .filter(models.MovimientoInsumo.tenant_id == tenant_id, models.MovimientoInsumo.insumo_id == insumo_id)
    )
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.MovimientoInsumo.documento_codigo, models.MovimientoInsumo.tipo, models.MovimientoInsumo.motivo),
        orden=(models.MovimientoInsumo.created_at.desc(), models.MovimientoInsumo.id),
    )
    ver_costos = _ver_costos(usuario)
    pagina["items"] = [services.serializar_movimiento(m, ver_costos) for m in pagina["items"]]
    columnas = [
        ("Fecha", campo("created_at")),
        ("Tipo", lambda f: TIPOS_LEGIBLES.get(f.get("tipo"), f.get("tipo"))),
        ("Cantidad", campo("cantidad")),
        ("Existencia resultante", campo("existencia_resultante")),
        ("Documento", campo("documento_codigo")),
        ("Motivo", campo("motivo")),
        ("Usuario", campo("usuario_nombre")),
    ]
    return responder(pagina, params, schemas.MovimientoOut, columnas, "movimientos")


# =====================================================================
# Historial general, mermas y conteos físicos
# =====================================================================
def _codigo_conteo(numero: int) -> str:
    return f"CON-{numero:06d}"


@router.get("/movimientos", response_model=Pagina[schemas.MovimientoOut])
def listar_movimientos(
    params: ParametrosPagina = Depends(),
    tipo: str | None = Query(default=None, max_length=20),
    insumo_id: uuid.UUID | None = Query(default=None),
    desde: date | None = Query(default=None, description="Día de Colombia, inclusive"),
    hasta: date | None = Query(default=None, description="Día de Colombia, inclusive"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("movimientos", "ver")),
):
    """Todas las entradas y salidas de la bodega: quién, cuándo, cuánto y por qué."""
    tenant_id = usuario.tenant_id
    query = (
        db.query(models.MovimientoInsumo)
        .join(models.Insumo, models.Insumo.id == models.MovimientoInsumo.insumo_id)
        .options(joinedload(models.MovimientoInsumo.insumo))
        .filter(models.MovimientoInsumo.tenant_id == tenant_id)
    )
    if tipo:
        query = query.filter(models.MovimientoInsumo.tipo == tipo)
    if insumo_id:
        query = query.filter(models.MovimientoInsumo.insumo_id == insumo_id)
    desfase = ZONA_NEGOCIO.utcoffset(None)
    if desde:
        query = query.filter(models.MovimientoInsumo.created_at >= datetime.combine(desde, time()) - desfase)
    if hasta:
        query = query.filter(models.MovimientoInsumo.created_at < datetime.combine(hasta + timedelta(days=1), time()) - desfase)
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Insumo.nombre, models.MovimientoInsumo.documento_codigo, models.MovimientoInsumo.motivo, models.MovimientoInsumo.usuario_nombre),
        orden=(models.MovimientoInsumo.created_at.desc(), models.MovimientoInsumo.id),
    )
    ver_costos = _ver_costos(usuario)
    pagina["items"] = [services.serializar_movimiento(m, ver_costos) for m in pagina["items"]]
    columnas = [
        ("Fecha", campo("created_at")),
        ("Insumo", campo("insumo_nombre")),
        ("Tipo", lambda f: TIPOS_LEGIBLES.get(f.get("tipo"), f.get("tipo"))),
        ("Cantidad", campo("cantidad")),
        ("Unidad", campo("unidad")),
        ("Existencia resultante", campo("existencia_resultante")),
        *([("Valor a costo", campo("valor"))] if ver_costos else []),
        ("Documento", campo("documento_codigo")),
        ("Motivo", campo("motivo")),
        ("Usuario", campo("usuario_nombre")),
    ]
    return responder(pagina, params, schemas.MovimientoOut, columnas, "movimientos")


@router.post("/insumos/{insumo_id}/merma", response_model=schemas.MovimientoOut, status_code=status.HTTP_201_CREATED)
def registrar_merma(
    insumo_id: uuid.UUID,
    payload: schemas.MermaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("movimientos", "crear")),
):
    """Salida que no es venta (vencido, dañado, derramado…), siempre con su
    motivo. No puede dejar la existencia en negativo: si se perdió más de lo
    que dice el sistema, lo que corresponde es un conteo físico."""
    tenant_id = usuario.tenant_id
    insumo = services.bloquear_insumos(db, tenant_id, [insumo_id]).get(insumo_id)
    if insumo is None:
        services.obtener_insumo_o_404(db, tenant_id, insumo_id)
    if not compatibles(payload.unidad, insumo.unidad):
        raise ConflictError(f"{insumo.nombre} se lleva en {insumo.unidad}: la merma no puede ir en {payload.unidad}.")
    cantidad = convertir(payload.cantidad, payload.unidad, insumo.unidad)
    if Decimal(insumo.existencia) < cantidad:
        raise ConflictError(
            f"No se pudo registrar la merma de {insumo.nombre}: quedan {legible(insumo.existencia, insumo.unidad)} "
            f"y se intentó sacar {legible(cantidad, insumo.unidad)}. Si en la bodega hay menos de lo que dice el sistema, haz un conteo físico."
        )
    motivo = models.MOTIVOS_MERMA[payload.motivo] + (f": {payload.detalle}" if payload.detalle else "")
    movimiento = services.registrar(db, tenant_id, insumo, "merma", -cantidad, motivo=motivo, usuario_nombre=usuario.nombre_completo)
    db.commit()
    db.refresh(movimiento)
    return services.serializar_movimiento(movimiento, _ver_costos(usuario))


def _serializar_conteo(c: models.Conteo, ver_costos: bool, con_items: bool) -> dict:
    return {
        "id": c.id,
        "numero": c.numero,
        "codigo": _codigo_conteo(c.numero),
        "motivo": c.motivo,
        "usuario_nombre": c.usuario_nombre,
        "lineas": len(c.items),
        "con_diferencia": sum(1 for i in c.items if i.diferencia != 0),
        "valor_diferencia": c.valor_diferencia if ver_costos else None,
        "created_at": c.created_at,
        "items": [
            {
                "insumo_id": i.insumo_id, "insumo_nombre": i.insumo.nombre, "unidad": i.insumo.unidad,
                "sistema": i.sistema, "contado": i.contado, "diferencia": i.diferencia,
                "valor": i.valor if ver_costos else None,
            }
            for i in c.items
        ] if con_items else [],
    }


@router.get("/conteos", response_model=Pagina[schemas.ConteoOut])
def listar_conteos(
    params: ParametrosPagina = Depends(),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("movimientos", "ver")),
):
    query = (
        db.query(models.Conteo)
        .options(selectinload(models.Conteo.items).joinedload(models.ConteoItem.insumo))
        .filter(models.Conteo.tenant_id == usuario.tenant_id)
    )
    pagina = paginar(query, params, columnas_busqueda=(models.Conteo.motivo, models.Conteo.usuario_nombre), orden=models.Conteo.numero.desc())
    ver_costos = _ver_costos(usuario)
    pagina["items"] = [_serializar_conteo(c, ver_costos, False) for c in pagina["items"]]
    columnas = [
        ("Conteo", campo("codigo")), ("Fecha", campo("created_at")), ("Insumos contados", campo("lineas")),
        ("Con diferencia", campo("con_diferencia")), *([("Valor de la diferencia", campo("valor_diferencia"))] if ver_costos else []),
        ("Motivo", campo("motivo")), ("Usuario", campo("usuario_nombre")),
    ]
    return responder(pagina, params, schemas.ConteoOut, columnas, "conteos")


@router.get("/conteos/{conteo_id}", response_model=schemas.ConteoOut)
def obtener_conteo(conteo_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("movimientos", "ver"))):
    conteo = obtener_del_tenant(db, models.Conteo, usuario.tenant_id, conteo_id, "El conteo indicado")
    return _serializar_conteo(conteo, _ver_costos(usuario), True)


@router.post("/conteos", response_model=schemas.ConteoOut, status_code=status.HTTP_201_CREATED)
def registrar_conteo(
    payload: schemas.ConteoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("movimientos", "crear")),
):
    """Ajuste por conteo físico: por cada insumo contado se compara con el
    sistema y la diferencia queda como movimiento "ajuste" (con su valor a
    costo) que apunta a este conteo. La existencia queda igual a lo contado."""
    tenant_id = usuario.tenant_id
    ids = [l.insumo_id for l in payload.lineas]
    if len(set(ids)) != len(ids):
        raise ConflictError("El conteo repite un insumo: cada insumo va una sola vez.")
    insumos = services.bloquear_insumos(db, tenant_id, ids)
    if len(insumos) != len(set(ids)):
        raise NotFoundError("Uno de los insumos contados ya no existe o pertenece a otra empresa: recarga la pantalla.")
    numero = (db.query(func.coalesce(func.max(models.Conteo.numero), 0)).filter(models.Conteo.tenant_id == tenant_id).scalar() or 0) + 1
    conteo = models.Conteo(tenant_id=tenant_id, numero=numero, motivo=payload.motivo, usuario_nombre=usuario.nombre_completo)
    db.add(conteo)
    db.flush()
    codigo = _codigo_conteo(numero)
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
            services.registrar(
                db, tenant_id, insumo, "ajuste", diferencia,
                documento_tipo="conteo", documento_id=conteo.id, documento_codigo=codigo,
                motivo=payload.motivo or "Conteo físico", usuario_nombre=usuario.nombre_completo, permitir_negativo=True,
            )
    conteo.valor_diferencia = total
    db.commit()
    db.refresh(conteo)
    return _serializar_conteo(conteo, _ver_costos(usuario), True)


# =====================================================================
# Carga inicial desde plantilla
# =====================================================================
@router.get("/carga-inicial/plantilla")
def descargar_plantilla(
    formato: str = Query(default="xlsx", pattern="^(xlsx|csv)$"),
    hoja: str | None = Query(default=None),
    _: Usuario = Depends(usuario_con_permiso("insumos", "ver")),
):
    """La plantilla la genera el sistema: Excel con las hojas Insumos, Platos
    y Recetas (con ejemplos y listas de unidades), o un CSV por hoja."""
    if formato == "csv":
        if hoja not in carga.HOJAS:
            raise ConflictError("Para el CSV indica la hoja: Insumos, Platos o Recetas.")
        return Response(
            content=carga.plantilla_csv(hoja), media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="plantilla-{hoja.lower()}.csv"'},
        )
    return Response(
        content=carga.plantilla_xlsx(), media_type=carga.TIPO_XLSX,
        headers={"Content-Disposition": 'attachment; filename="plantilla-carga-inicial.xlsx"'},
    )


def _plan_de_archivo(db: Session, usuario: Usuario, archivo: tuple[bytes, str], hoja: str | None) -> carga.Plan:
    contenido, tipo = archivo
    hojas, errores = carga.leer(contenido, tipo, hoja)
    if (hojas["Platos"] or hojas["Recetas"]) and not tiene_permiso(usuario, "productos", "crear"):
        raise ForbiddenError(
            "El archivo trae platos o recetas y tu rol no puede crear platos: carga solo la hoja de insumos "
            "o pídele a un administrador el permiso de la carta."
        )
    return carga.validar(db, usuario.tenant_id, hojas, errores)


@router.post("/carga-inicial/validar")
def validar_carga(
    hoja: str | None = Query(default=None, description="Solo para CSV: Insumos, Platos o Recetas"),
    archivo: tuple[bytes, str] = Depends(leer_archivo_subido),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("insumos", "crear")),
):
    """Revisa el archivo fila por fila SIN guardar nada y devuelve el informe."""
    return carga.informe(_plan_de_archivo(db, usuario, archivo, hoja))


@router.post("/carga-inicial/aplicar")
def aplicar_carga(
    hoja: str | None = Query(default=None, description="Solo para CSV: Insumos, Platos o Recetas"),
    archivo: tuple[bytes, str] = Depends(leer_archivo_subido),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("insumos", "crear")),
):
    """Vuelve a revisar el archivo y, si no tiene ningún error, lo guarda
    entero en una transacción. Con un solo error, no guarda nada (422)."""
    plan = _plan_de_archivo(db, usuario, archivo, hoja)
    if plan.errores:
        raise CargaConErrores(
            f"El archivo tiene {len(plan.errores)} error(es): corrígelos y vuelve a subirlo. No se guardó nada.",
            datos=carga.informe(plan),
        )
    carga.aplicar(db, usuario.tenant_id, plan, usuario.nombre_completo)
    db.commit()
    return carga.informe(plan, aplicado=True)
