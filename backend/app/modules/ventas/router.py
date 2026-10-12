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
COLUMNAS_PEDIDOS = [
    ("Código", campo("codigo")),
    ("Fecha", campo("fecha")),
    ("Cliente", campo("cliente_nombre")),
    ("Teléfono", campo("cliente_telefono")),
    ("Dirección", campo("cliente_direccion")),
    ("Prioridad", campo("prioridad")),
    ("Estado", lambda f: humanizar(f.get("estado"))),
    ("Entrega", campo("fecha_entrega")),
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


# =====================================================================
# Pedidos (entidad propia con línea de tiempo de seguimiento)
# =====================================================================
@router.get("/pedidos", response_model=Pagina[schemas.PedidoOut])
def listar_pedidos(
    params: ParametrosPagina = Depends(),
    estado: str | None = Query(default=None),
    prioridad: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("pedidos", "ver")),
):
    query = (
        db.query(models.Pedido)
        .options(
            joinedload(models.Pedido.items).joinedload(models.PedidoItem.producto),
            joinedload(models.Pedido.eventos),
        )
        .filter(models.Pedido.tenant_id == tenant_id)
    )
    if estado:
        query = query.filter(models.Pedido.estado == estado)
    if prioridad:
        query = query.filter(models.Pedido.prioridad == prioridad)
    columnas = [
        models.Pedido.cliente_nombre,
        models.Pedido.cliente_telefono,
        models.Pedido.notas,
        models.Pedido.estado,
        models.Pedido.prioridad,
    ]
    _busqueda_por_consecutivo(params, "PED", models.Pedido.numero, columnas)
    # Orden por prioridad (urgente primero), luego los más recientes. Los
    # pedidos cerrados (entregado/cancelado) van al final.
    orden_prioridad = case(services.ORDEN_PRIORIDAD, value=models.Pedido.prioridad, else_=9)
    cerrado = case({"entregado": 1, "cancelado": 1}, value=models.Pedido.estado, else_=0)
    pagina = paginar(
        query, params,
        columnas_busqueda=columnas,
        orden=(cerrado, orden_prioridad, models.Pedido.numero.desc()),
    )
    pagina["items"] = [services.serializar_pedido(p) for p in pagina["items"]]
    return responder(pagina, params, schemas.PedidoOut, COLUMNAS_PEDIDOS, "pedidos")


@router.get("/pedidos/{pedido_id}", response_model=schemas.PedidoOut)
def obtener_pedido(
    pedido_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("pedidos", "ver")),
):
    return services.serializar_pedido(services.obtener_pedido_o_404(db, tenant_id, pedido_id))


@router.get("/pedidos/{pedido_id}/pdf")
def pdf_pedido(
    pedido_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("pedidos", "ver")),
):
    pedido = services.obtener_pedido_o_404(db, usuario.tenant_id, pedido_id)
    datos = services.serializar_pedido(pedido)
    pdf = generar_documento_pdf(
        titulo="Pedido",
        codigo=datos["codigo"],
        empresa=_nombre_empresa(db, usuario.tenant_id),
        estado=pedido.estado,
        fecha=pedido.fecha,
        datos=[
            ("Cliente", pedido.cliente_nombre),
            ("Teléfono", pedido.cliente_telefono or "—"),
            ("Dirección", pedido.cliente_direccion or "—"),
            ("Prioridad", pedido.prioridad.capitalize()),
            ("Entrega", pedido.fecha_entrega.strftime("%d/%m/%Y %H:%M") if pedido.fecha_entrega else "—"),
            ("Atendido por", usuario.nombre_completo),
        ],
        items=_items_pdf(datos["items"]),
        columna_detalle="Código",
        total=pedido.total,
        notas=pedido.notas,
    )
    return _respuesta_pdf(pdf, datos["codigo"])


@router.post("/pedidos", response_model=schemas.PedidoOut, status_code=201)
def crear_pedido(
    payload: schemas.PedidoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("pedidos", "crear")),
):
    return services.serializar_pedido(
        services.crear_pedido(db, usuario.tenant_id, payload, usuario.nombre_completo)
    )


@router.put("/pedidos/{pedido_id}", response_model=schemas.PedidoOut)
def actualizar_pedido(
    pedido_id: uuid.UUID,
    payload: schemas.PedidoUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("pedidos", "editar")),
):
    return services.serializar_pedido(
        services.actualizar_pedido(db, usuario.tenant_id, pedido_id, payload, usuario.nombre_completo)
    )


@router.patch("/pedidos/{pedido_id}/estado", response_model=schemas.PedidoOut)
def cambiar_estado_pedido(
    pedido_id: uuid.UUID,
    payload: schemas.PedidoCambioEstado,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("pedidos", "cambiar_estado")),
):
    return services.serializar_pedido(
        services.cambiar_estado_pedido(db, usuario.tenant_id, pedido_id, payload, usuario.nombre_completo)
    )
