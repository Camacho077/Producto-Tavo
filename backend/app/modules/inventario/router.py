"""
INSUMOS (2026-10-12): la materia prima con su unidad, existencia (suma de
movimientos, nunca editada a mano), mínimo para alertar, costo unitario
(promedio ponderado de las compras) y costo total. Los costos solo los ve
quien tiene `costos.ver`.
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core import mensajes
from app.core.errors import ConflictError
from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.permisos import tiene_permiso, usuario_con_permiso
from app.db.session import get_db
from app.modules.catalogo.models import RecetaItem
from app.modules.catalogo.services import mensaje_insumo_en_uso
from app.modules.inventario import models, schemas, services
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/inventario", tags=["Inventario"])

TIPOS_LEGIBLES = {
    "inicial": "Existencia inicial",
    "compra": "Compra",
    "anulacion_compra": "Anulación de compra",
    "venta": "Venta",
    "anulacion_venta": "Anulación de venta",
    "merma": "Merma",
    "ajuste": "Ajuste por conteo",
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
