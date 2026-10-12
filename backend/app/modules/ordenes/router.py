import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import String, func, not_
from sqlalchemy.orm import Session, selectinload

from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.permisos import tiene_permiso, usuario_con_permiso
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.ajustes.schemas import configuracion_de
from app.modules.ajustes.services import fecha_jornada
from app.modules.catalogo.models import Categoria, Modificador, Producto
from app.modules.catalogo.services import agotado_hoy, vigente
from app.core.tiempo import ahora_utc
from app.modules.ordenes import models, schemas, services
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/ordenes", tags=["Órdenes"])

ESTADO_LEGIBLE = {
    "entrante": "Entrante", "en_preparacion": "En preparación", "lista": "Lista", "entregada": "Entregada",
    "abierta": "Abierta", "cobrada": "Cobrada", "anulada": "Anulada",
}
COLUMNAS = [
    ("Jornada", campo("jornada")),
    ("Número", campo("numero")),
    ("Tipo", lambda f: services.NOMBRE_TIPO.get(f.get("tipo"), f.get("tipo"))),
    ("Origen", lambda f: services.NOMBRE_ORIGEN.get(f.get("origen"), f.get("origen"))),
    ("Mesa", campo("mesa_nombre")),
    ("Cliente", campo("cliente_nombre")),
    ("Estado", lambda f: ESTADO_LEGIBLE.get(f.get("estado_cocina") or f.get("estado"), f.get("estado"))),
    ("Platos", campo("resumen")),
    ("Total", campo("total")),
    ("Mesero", campo("mesero_nombre")),
    ("Hora", campo("created_at")),
]


def _ver_costos(usuario: Usuario) -> bool:
    return tiene_permiso(usuario, "costos", "ver")


def _jornada_actual(db: Session, tenant_id: uuid.UUID) -> date:
    return fecha_jornada(configuracion_de(db.get(Tenant, tenant_id)), ahora_utc())


def _detalle(db: Session, orden: models.Orden, usuario: Usuario) -> dict:
    orden = (
        db.query(models.Orden).options(*services.opciones_carga_orden(detalle=True))
        .filter(models.Orden.id == orden.id).populate_existing().one()
    )
    return services.serializar_orden(orden, _ver_costos(usuario), detalle=True)


@router.get("/carta")
def carta_para_pedir(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "crear"))):
    """La carta tal como se pide: categorías en su orden y los platos activos
    y vigentes, con sus modificadores y si están agotados hoy. No trae
    costos ni recetas (quien toma pedidos no los necesita)."""
    tenant_id = usuario.tenant_id
    jornada = _jornada_actual(db, tenant_id)
    categorias = (
        db.query(Categoria).filter(Categoria.tenant_id == tenant_id, Categoria.activo.is_(True))
        .order_by(Categoria.orden, Categoria.nombre).all()
    )
    productos = (
        db.query(Producto)
        .options(selectinload(Producto.modificadores), selectinload(Producto.componentes))
        .filter(Producto.tenant_id == tenant_id, Producto.activo.is_(True))
        .order_by(Producto.nombre).all()
    )
    return {
        "jornada": jornada,
        "categorias": [{"id": c.id, "nombre": c.nombre} for c in categorias],
        "productos": [
            {
                "id": p.id, "tipo": p.tipo, "nombre": p.nombre, "descripcion": p.descripcion, "precio": p.precio,
                "categoria_id": p.categoria_id, "imagen_id": p.imagen_id, "va_a_cocina": services._va_a_cocina(p),
                "agotado_hoy": agotado_hoy(p, jornada),
                "modificadores": [
                    {"id": m.id, "tipo": m.tipo, "nombre": m.nombre, "precio": m.precio}
                    for m in sorted(p.modificadores, key=lambda m: (m.tipo != "sin", m.orden)) if m.activo
                ],
            }
            for p in productos if vigente(p, jornada)
        ],
    }


@router.get("/mesas", response_model=list[schemas.MesaEstado])
def mesas(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "ver"))):
    """Cuadrícula "¿Para qué mesa?": libre, ocupada (algo sin entregar) o
    por cobrar (todo entregado)."""
    return services.estado_mesas(db, usuario.tenant_id)


@router.get("/jornada")
def jornada(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "ver"))):
    return services.resumen_jornada(db, usuario.tenant_id, _jornada_actual(db, usuario.tenant_id))


@router.get("", response_model=Pagina[schemas.OrdenOut])
def listar(
    params: ParametrosPagina = Depends(),
    vista: str = Query(default="activas", pattern="^(activas|entregadas|anuladas|todas)$"),
    jornada: date | None = Query(default=None, description="Por defecto, la jornada actual"),
    tipo: str | None = Query(default=None, pattern="^(local|llevar|domicilio)$"),
    mesa_id: uuid.UUID | None = Query(default=None),
    mias: bool = Query(default=False, description="Solo las que tomó quien consulta"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ordenes", "ver")),
):
    """Tablero de órdenes. Activas: abiertas con algo sin entregar.
    Entregadas: todo entregado (por cobrar o ya cobradas). Anuladas."""
    tenant_id = usuario.tenant_id
    query = (
        db.query(models.Orden).options(*services.opciones_carga_orden())
        .filter(models.Orden.tenant_id == tenant_id, models.Orden.jornada == (jornada or _jornada_actual(db, tenant_id)))
    )
    if vista == "activas":
        query = query.filter(models.Orden.estado == "abierta", services.filtro_activa())
    elif vista == "entregadas":
        query = query.filter(models.Orden.estado != "anulada", not_(services.filtro_activa()))
    elif vista == "anuladas":
        query = query.filter(models.Orden.estado == "anulada")
    if tipo:
        query = query.filter(models.Orden.tipo == tipo)
    if mesa_id:
        query = query.filter(models.Orden.mesa_id == mesa_id)
    if mias:
        query = query.filter(models.Orden.mesero_id == usuario.id)
    busqueda = [models.Orden.cliente_nombre, models.Orden.mesero_nombre, models.Orden.nota]
    if params.q and params.q.strip().lstrip("#").isdigit():
        busqueda.append(func.cast(models.Orden.numero, String))
        params.q = params.q.strip().lstrip("#")
    orden_sql = models.Orden.numero.asc() if vista == "activas" else models.Orden.numero.desc()
    pagina = paginar(query, params, columnas_busqueda=busqueda, orden=orden_sql)
    ver = _ver_costos(usuario)
    pagina["items"] = [services.serializar_orden(o, ver) for o in pagina["items"]]
    return responder(pagina, params, schemas.OrdenOut, COLUMNAS, "ordenes")


@router.get("/{orden_id}", response_model=schemas.OrdenOut)
def obtener(orden_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "ver"))):
    return _detalle(db, services.obtener_orden_o_404(db, usuario.tenant_id, orden_id), usuario)


@router.post("", response_model=schemas.OrdenOut, status_code=status.HTTP_201_CREATED)
def crear(payload: schemas.OrdenCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "crear"))):
    """Envía la orden: consecutivo de la jornada + descuento de insumos +
    comanda 1, en una transacción. Si un insumo no alcanza: 409 con la causa
    y, en `datos`, los faltantes y los platos que los usan."""
    return _detalle(db, services.crear_orden(db, usuario, payload), usuario)


@router.post("/{orden_id}/items", response_model=schemas.OrdenOut, status_code=status.HTTP_201_CREATED)
def agregar(
    orden_id: uuid.UUID, payload: schemas.ItemsAgregar,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "editar")),
):
    orden, _ = services.agregar_items(db, usuario, orden_id, payload)
    return _detalle(db, orden, usuario)


@router.put("/{orden_id}", response_model=schemas.OrdenOut)
def editar(
    orden_id: uuid.UUID, payload: schemas.DatosOrden,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "editar")),
):
    return _detalle(db, services.editar_encabezado(db, usuario, orden_id, payload), usuario)


@router.post("/{orden_id}/items/{item_id}/anular", response_model=schemas.OrdenOut)
def anular_item(
    orden_id: uuid.UUID, item_id: uuid.UUID, payload: schemas.Motivo,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "editar")),
):
    return _detalle(db, services.anular_item(db, usuario, orden_id, item_id, payload.motivo), usuario)


@router.post("/{orden_id}/anular", response_model=schemas.OrdenOut)
def anular(
    orden_id: uuid.UUID, payload: schemas.Motivo,
    db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "anular")),
):
    return _detalle(db, services.anular_orden(db, usuario, orden_id, payload.motivo), usuario)


@router.post("/{orden_id}/entregar", response_model=schemas.OrdenOut)
def entregar(orden_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "cambiar_estado"))):
    return _detalle(db, services.entregar(db, usuario, orden_id), usuario)


@router.post("/agotados", status_code=status.HTTP_204_NO_CONTENT)
def agotar(payload: schemas.AgotarProducto, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ordenes", "crear"))):
    """Marca un plato "agotado hoy" desde la toma de pedidos (cuando falta
    un insumo de su receta). Vuelve solo con la jornada siguiente."""
    services.marcar_agotado(db, usuario, payload.producto_id)
