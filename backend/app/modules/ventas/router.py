import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import String, case, func
from sqlalchemy.orm import Session, joinedload

from app.core.branding import NOMBRE_PRODUCTO
from app.core.permisos import tenant_con_permiso, usuario_con_permiso
from app.core.exportar import campo, humanizar, responder, resumen_items
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.pdf import generar_documento_pdf
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.seguridad.models import Usuario
from app.modules.ventas import models, schemas, services

router = APIRouter(prefix="/ventas", tags=["Ventas"])


def _nombre_empresa(db: Session, tenant_id: uuid.UUID) -> str:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    return tenant.nombre_empresa if tenant else NOMBRE_PRODUCTO


def _items_pdf(items: list[dict]) -> list[dict]:
    return [
        {"descripcion": i["producto_nombre"], "detalle": i.get("producto_sku"), "cantidad": i["cantidad"],
         "precio_unitario": i["precio_unitario"], "subtotal": i["subtotal"]}
        for i in items
    ]


def _respuesta_pdf(pdf: bytes, codigo: str) -> Response:
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{codigo}.pdf"'},
    )


def _busqueda_por_consecutivo(params: ParametrosPagina, prefijo: str, columna_numero, columnas: list) -> None:
    """Permite buscar 'VEN-000012', '000012' o '12' por el consecutivo."""
    if not params.q:
        return
    digitos = "".join(ch for ch in params.q if ch.isdigit())
    if digitos:
        columnas.append(func.cast(columna_numero, String))
        if params.q.upper().startswith(prefijo):
            params.q = digitos


# =====================================================================
# Ventas
# =====================================================================
# Columnas de la exportación a CSV (`?formato=csv`, app/core/exportar.py).
COLUMNAS_VENTAS = [
    ("Código", campo("codigo")),
    ("Fecha", campo("fecha")),
    ("Cliente", campo("cliente_nombre")),
    ("Documento del cliente", campo("cliente_documento")),
    ("Estado", lambda f: humanizar(f.get("estado"))),
    ("Productos", resumen_items),
    ("Total", campo("total")),
    ("Notas", campo("notas")),
]


@router.get("/ventas", response_model=Pagina[schemas.VentaOut])
def listar_ventas(
    params: ParametrosPagina = Depends(),
    estado: str | None = Query(default=None, description="pendiente, completada, cancelada o anulada"),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("ventas", "ver")),
):
    query = (
        db.query(models.Venta)
        .options(joinedload(models.Venta.items).joinedload(models.VentaItem.producto))
        .filter(models.Venta.tenant_id == tenant_id)
    )
    if estado is not None:
        query = query.filter(models.Venta.estado == estado)
    columnas = [models.Venta.cliente_nombre, models.Venta.cliente_documento, models.Venta.notas, models.Venta.estado]
    _busqueda_por_consecutivo(params, "VEN", models.Venta.numero, columnas)
    pagina = paginar(query, params, columnas_busqueda=columnas, orden=models.Venta.numero.desc())
    pagina["items"] = [services.serializar_venta(v) for v in pagina["items"]]
    return responder(pagina, params, schemas.VentaOut, COLUMNAS_VENTAS, "ventas")


@router.get("/ventas/{venta_id}", response_model=schemas.VentaOut)
def obtener_venta(
    venta_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("ventas", "ver")),
):
    return services.serializar_venta(services.obtener_venta_o_404(db, tenant_id, venta_id))


@router.get("/ventas/{venta_id}/pdf")
def pdf_venta(
    venta_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ventas", "ver")),
):
    venta = services.obtener_venta_o_404(db, usuario.tenant_id, venta_id)
    datos = services.serializar_venta(venta)
    pdf = generar_documento_pdf(
        titulo="Factura de venta",
        codigo=datos["codigo"],
        empresa=_nombre_empresa(db, usuario.tenant_id),
        estado=venta.estado,
        fecha=venta.fecha,
        datos=[
            ("Cliente", venta.cliente_nombre),
            ("Documento", venta.cliente_documento or "—"),
            ("Atendido por", usuario.nombre_completo),
        ],
        items=_items_pdf(datos["items"]),
        columna_detalle="Código",
        total=venta.total,
        notas=venta.notas,
    )
    return _respuesta_pdf(pdf, datos["codigo"])


@router.post("/ventas", response_model=schemas.VentaOut, status_code=201)
def crear_venta(
    payload: schemas.VentaCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ventas", "crear")),
):
    return services.serializar_venta(services.crear_venta(db, usuario.tenant_id, payload, usuario.nombre_completo))


@router.post("/ventas/{venta_id}/confirmar", response_model=schemas.VentaOut)
def confirmar_venta(
    venta_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ventas", "cambiar_estado")),
):
    return services.serializar_venta(services.confirmar_venta(db, usuario.tenant_id, venta_id, usuario.nombre_completo))


@router.post("/ventas/{venta_id}/cancelar", response_model=schemas.VentaOut)
def cancelar_venta(
    venta_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("ventas", "cambiar_estado")),
):
    return services.serializar_venta(services.cancelar_venta(db, tenant_id, venta_id))


@router.post("/ventas/{venta_id}/anular", response_model=schemas.VentaOut)
def anular_venta(
    venta_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ventas", "anular")),
):
    return services.serializar_venta(services.anular_venta(db, usuario.tenant_id, venta_id, usuario.nombre_completo))
