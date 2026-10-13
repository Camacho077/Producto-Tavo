import uuid
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import String, func
from sqlalchemy.orm import Session

from app.core.consultas import obtener_del_tenant
from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.pdf import generar_documento_pdf
from app.core.permisos import tiene_permiso, usuario_con_permiso
from app.core.validaciones import ZONA_NEGOCIO
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.caja import models, schemas, services
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/caja", tags=["Caja"])

# Texto obligatorio del comprobante (2026-10-12, decisión legal de la fase 6):
# hasta confirmar con el contador si el restaurante está obligado a facturar
# electrónicamente, lo que se entrega es un comprobante INTERNO.
LEYENDA_COMPROBANTE = "Comprobante interno, no válido como factura electrónica."

COLUMNAS_VENTAS = [
    ("Comprobante", campo("codigo")),
    ("Fecha", campo("fecha")),
    ("Orden", campo("orden_numero")),
    ("Cliente", campo("cliente_nombre")),
    ("Medios de pago", lambda f: ", ".join(services.NOMBRE_MEDIO.get(m, m) for m in f.get("medios", []))),
    ("Base", campo("subtotal")),
    ("Impuesto", campo("impuesto")),
    ("Total", campo("total")),
    ("Propina", campo("propina")),
    ("Estado", lambda f: "Anulado" if f.get("estado") == "anulada" else "Pagado"),
    ("Cajero", campo("cajero_nombre")),
]
COLUMNAS_CIERRES = [
    ("Caja", campo("numero")),
    ("Abrió", campo("abierta_por")),
    ("Apertura", campo("abierta_en")),
    ("Cierre", campo("cerrada_en")),
    ("Cerró", campo("cerrada_por")),
    ("Ventas", lambda f: f["resumen"]["total_ventas"]),
    ("Diferencia", campo("diferencia")),
    ("Motivo", campo("motivo_diferencia")),
]


def _ver_costos(usuario: Usuario) -> bool:
    return tiene_permiso(usuario, "costos", "ver")


def _venta(db: Session, tenant_id: uuid.UUID, venta_id: uuid.UUID) -> models.Venta:
    services.obtener_venta_o_404(db, tenant_id, venta_id)
    return db.query(models.Venta).options(*services.opciones_venta()).filter(models.Venta.id == venta_id).populate_existing().one()


# ---------- Sesión de caja ----------
@router.get("/actual")
def actual(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("caja", "ver"))):
    """La caja abierta con su cuadre en vivo, o `{"caja": null}`."""
    caja = services.caja_abierta(db, usuario.tenant_id)
    return {"caja": services.serializar_caja(db, caja) if caja else None}


@router.post("/abrir", status_code=status.HTTP_201_CREATED)
def abrir(payload: schemas.AbrirCaja, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("caja", "cambiar_estado"))):
    return services.serializar_caja(db, services.abrir(db, usuario, payload.base_inicial))


@router.post("/cerrar")
def cerrar(payload: schemas.CerrarCaja, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("caja", "cambiar_estado"))):
    """Cierre: lo contado contra lo esperado por medio de pago. Si no cuadra,
    el motivo es obligatorio y queda en el reporte."""
    return services.serializar_caja(db, services.cerrar(db, usuario, payload))


@router.get("/cierres", response_model=Pagina[dict])
def cierres(params: ParametrosPagina = Depends(), db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("caja", "ver"))):
    query = db.query(models.CajaSesion).filter(models.CajaSesion.tenant_id == usuario.tenant_id, models.CajaSesion.estado == "cerrada")
    pagina = paginar(query, params, columnas_busqueda=(models.CajaSesion.abierta_por, models.CajaSesion.cerrada_por, models.CajaSesion.motivo_diferencia),
                     orden=models.CajaSesion.numero.desc())
    pagina["items"] = [services.serializar_caja(db, c) for c in pagina["items"]]
    return responder(pagina, params, None, COLUMNAS_CIERRES, "cierres-de-caja")


@router.get("/cierres/{caja_id}")
def cierre(caja_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("caja", "ver"))):
    caja = obtener_del_tenant(db, models.CajaSesion, usuario.tenant_id, caja_id, "La caja indicada")
    return services.serializar_caja(db, caja)


# ---------- Cobrar ----------
@router.get("/por-cobrar")
def por_cobrar(db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ventas", "crear"))):
    return services.por_cobrar(db, usuario.tenant_id)


@router.post("/cobros", status_code=status.HTTP_201_CREATED)
def cobrar(payload: schemas.CobroCreate, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ventas", "crear"))):
    """Cobra una orden (o los platos elegidos de ella, para dividir la
    cuenta) con uno o varios medios de pago. La suma de los pagos debe ser
    exactamente el total más la propina."""
    venta = services.cobrar(db, usuario, payload)
    return services.serializar_venta(_venta(db, usuario.tenant_id, venta.id), _ver_costos(usuario))


# ---------- Comprobantes ----------
@router.get("/ventas", response_model=Pagina[dict])
def ventas(
    params: ParametrosPagina = Depends(),
    estado: str | None = Query(default=None, pattern="^(completada|anulada)$"),
    medio: str | None = Query(default=None, max_length=15),
    desde: date | None = Query(default=None),
    hasta: date | None = Query(default=None),
    caja_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("ventas", "ver")),
):
    query = db.query(models.Venta).options(*services.opciones_venta()).filter(models.Venta.tenant_id == usuario.tenant_id)
    if estado:
        query = query.filter(models.Venta.estado == estado)
    if medio:
        query = query.filter(models.Venta.pagos.any(models.VentaPago.medio == medio))
    desfase = ZONA_NEGOCIO.utcoffset(None)
    if desde:
        query = query.filter(models.Venta.fecha >= datetime.combine(desde, time()) - desfase)
    if hasta:
        query = query.filter(models.Venta.fecha < datetime.combine(hasta + timedelta(days=1), time()) - desfase)
    if caja_id:
        query = query.filter(models.Venta.caja_id == caja_id)
    busqueda = [models.Venta.cliente_nombre, models.Venta.cajero_nombre, models.Venta.cliente_documento]
    if params.q:
        digitos = "".join(ch for ch in params.q if ch.isdigit())
        if digitos and (params.q.upper().startswith("CI") or params.q.strip().isdigit()):
            busqueda.append(func.cast(models.Venta.numero, String))
            params.q = digitos.lstrip("0") or digitos
    pagina = paginar(query, params, columnas_busqueda=busqueda, orden=models.Venta.numero.desc())
    ver = _ver_costos(usuario)
    pagina["items"] = [services.serializar_venta(v, ver) for v in pagina["items"]]
    return responder(pagina, params, None, COLUMNAS_VENTAS, "ventas")


@router.get("/ventas/{venta_id}")
def venta(venta_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ventas", "ver"))):
    return services.serializar_venta(_venta(db, usuario.tenant_id, venta_id), _ver_costos(usuario))


@router.post("/ventas/{venta_id}/anular")
def anular(venta_id: uuid.UUID, payload: schemas.Motivo, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ventas", "anular"))):
    services.anular_venta(db, usuario, venta_id, payload.motivo)
    return services.serializar_venta(_venta(db, usuario.tenant_id, venta_id), _ver_costos(usuario))


@router.get("/ventas/{venta_id}/pdf")
def pdf(venta_id: uuid.UUID, db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("ventas", "ver"))):
    v = services.serializar_venta(_venta(db, usuario.tenant_id, venta_id))
    tenant = db.get(Tenant, usuario.tenant_id)
    datos = [("Orden", f"#{v['orden_numero']}" + (f" · Mesa {v['mesa_nombre']}" if v["mesa_nombre"] else "")), ("Atendió", v["cajero_nombre"] or "—")]
    if v["cliente_nombre"]:
        datos.append(("Cliente", v["cliente_nombre"]))
    if v["cliente_documento"]:
        datos.append(("Documento", f"{v['cliente_documento_tipo']} {v['cliente_documento']}"))
    datos.append(("Pago", ", ".join(f"{services.NOMBRE_MEDIO[p['medio']]} {services.legible(p['monto'])}" for p in v["pagos"])))
    extra = [("Base", services.legible(v["subtotal"]))]
    if v["impuesto"]:
        extra.append((f"Impuesto al consumo {v['impuesto_tasa']:.0f} %", services.legible(v["impuesto"])))
    if v["propina"]:
        extra.append(("Propina (voluntaria)", services.legible(v["propina"])))
    contenido = generar_documento_pdf(
        titulo="Comprobante interno", codigo=v["codigo"], empresa=tenant.nombre_empresa,
        estado="anulado" if v["estado"] == "anulada" else "pagado", fecha=v["fecha"], datos=datos,
        items=[{"descripcion": i["nombre"], "detalle": None, "cantidad": i["cantidad"], "precio_unitario": i["precio_unitario"], "subtotal": i["subtotal"]} for i in v["items"]],
        columna_descripcion="Plato", total=v["total_pagado"], totales_extra=extra,
        pie=f"{LEYENDA_COMPROBANTE}{f' NIT {tenant.nit}.' if tenant.nit else ''}",
    )
    return Response(content=contenido, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{v["codigo"]}.pdf"'})
