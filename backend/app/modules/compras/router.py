import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.branding import NOMBRE_PRODUCTO
from app.core.permisos import tenant_con_permiso, usuario_con_permiso
from app.core import mensajes
from app.core.errors import ConflictError
from app.core.exportar import campo, humanizar, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.pdf import generar_documento_pdf
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.compras import models, schemas, services
from app.modules.inventario.unidades import legible
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/compras", tags=["Compras"])


# =====================================================================
# Columnas de la exportación a CSV (`?formato=csv`, app/core/exportar.py)
# =====================================================================
_ESTADO = ("Estado", lambda f: "Activo" if f.get("activo") else "Inactivo")
COLUMNAS_PROVEEDORES = [
    ("Nombre", campo("nombre")),
    ("Tipo de persona", campo("tipo_persona")),
    ("NIT", campo("nit")),
    ("Razón social", campo("razon_social")),
    ("Representante", campo("representante_nombre")),
    ("Tipo de documento", campo("tipo_documento")),
    ("Número de documento", campo("numero_documento")),
    ("Teléfono", campo("telefono")),
    ("Correo", campo("email")),
    ("Dirección", campo("direccion")),
    ("Compras", campo("compras_count")),
    ("Insumos que surte", lambda f: "; ".join(i["nombre"] for i in f.get("insumos") or [])),
    _ESTADO,
]
COLUMNAS_COMPRAS = [
    ("Código", campo("codigo")),
    ("Fecha", campo("fecha")),
    ("Proveedor", campo("proveedor_nombre")),
    ("Estado", lambda f: humanizar(f.get("estado"))),
    ("Insumos", lambda f: "; ".join(f"{i['insumo_nombre']} {legible(i['cantidad'], i['unidad'])}" for i in f.get("items") or [])),
    ("Total", campo("total")),
    ("Notas", campo("notas")),
]


# =====================================================================
# Proveedores
# =====================================================================
@router.get("/proveedores", response_model=Pagina[schemas.ProveedorOut])
def listar_proveedores(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "ver")),
):
    # `serializar_proveedor` lee `p.insumos` (muchos a muchos). Sin esto se
    # dispara una consulta por proveedor de la página: con 10 filas eran 10
    # consultas extra. `selectinload` las resuelve todas en UNA sola, y a
    # diferencia de `joinedload` no multiplica filas contra el LIMIT de la
    # paginación. Lo protege tests/test_rendimiento_consultas.py.
    query = (
        db.query(models.Proveedor)
        .options(selectinload(models.Proveedor.insumos))
        .filter(models.Proveedor.tenant_id == tenant_id)
    )
    if activo is not None:
        query = query.filter(models.Proveedor.activo == activo)
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Proveedor.nombre, models.Proveedor.nit, models.Proveedor.numero_documento, models.Proveedor.email, models.Proveedor.telefono),
        orden=models.Proveedor.nombre,
    )
    conteos = services.conteo_compras_por_proveedor(db, tenant_id)
    pagina["items"] = [services.serializar_proveedor(p, conteos.get(p.id, 0)) for p in pagina["items"]]
    return responder(pagina, params, schemas.ProveedorOut, COLUMNAS_PROVEEDORES, "proveedores")


@router.get("/proveedores/{proveedor_id}", response_model=schemas.ProveedorOut)
def obtener_proveedor(
    proveedor_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "ver")),
):
    proveedor = services.obtener_proveedor_o_404(db, tenant_id, proveedor_id)
    conteos = services.conteo_compras_por_proveedor(db, tenant_id)
    return services.serializar_proveedor(proveedor, conteos.get(proveedor.id, 0))


@router.post("/proveedores", response_model=schemas.ProveedorOut, status_code=status.HTTP_201_CREATED)
def crear_proveedor(
    payload: schemas.ProveedorCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "crear")),
):
    proveedor = models.Proveedor(tenant_id=tenant_id, nombre=payload.nombre_derivado, **payload.model_dump(exclude={"insumo_ids"}))
    db.add(proveedor)
    db.flush()
    services.sincronizar_insumos_proveedor(db, tenant_id, proveedor, payload.insumo_ids)
    db.commit()
    db.refresh(proveedor)
    return services.serializar_proveedor(proveedor)


@router.put("/proveedores/{proveedor_id}", response_model=schemas.ProveedorOut)
def actualizar_proveedor(
    proveedor_id: uuid.UUID,
    payload: schemas.ProveedorUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "editar")),
):
    proveedor = services.obtener_proveedor_o_404(db, tenant_id, proveedor_id)
    # El payload ya viene limpio por tipo de persona (model_validator): se
    # escriben TODOS los campos para que no queden valores fantasma.
    datos = payload.model_dump(exclude={"activo", "insumo_ids"})
    for campo, valor in datos.items():
        setattr(proveedor, campo, valor)
    if payload.activo is not None:
        proveedor.activo = payload.activo
    proveedor.nombre = payload.nombre_derivado
    services.sincronizar_insumos_proveedor(db, tenant_id, proveedor, payload.insumo_ids)
    db.commit()
    db.refresh(proveedor)
    conteos = services.conteo_compras_por_proveedor(db, tenant_id)
    return services.serializar_proveedor(proveedor, conteos.get(proveedor.id, 0))


@router.patch("/proveedores/{proveedor_id}/estado", response_model=schemas.ProveedorOut)
def cambiar_estado_proveedor(
    proveedor_id: uuid.UUID,
    payload: schemas.CambioEstado,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "cambiar_estado")),
):
    proveedor = services.obtener_proveedor_o_404(db, tenant_id, proveedor_id)
    proveedor.activo = payload.activo
    db.commit()
    db.refresh(proveedor)
    return services.serializar_proveedor(proveedor)


@router.delete("/proveedores/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proveedor(
    proveedor_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "eliminar")),
):
    proveedor = services.obtener_proveedor_o_404(db, tenant_id, proveedor_id)
    asociados = db.query(func.count(models.Compra.id)).filter(models.Compra.proveedor_id == proveedor.id).scalar()
    if asociados:
        raise ConflictError(
            mensajes.no_se_puede_eliminar(
                "el proveedor", proveedor.nombre, asociados, "compra", "compras",
                "Puedes desactivarlo en su lugar para conservar el historial.",
            )
        )
    db.delete(proveedor)
    db.commit()


# =====================================================================
# Compras
# =====================================================================
@router.get("/compras", response_model=Pagina[schemas.CompraOut])
def listar_compras(
    params: ParametrosPagina = Depends(),
    estado: str | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("compras", "ver")),
):
    query = (
        db.query(models.Compra)
        .join(models.Proveedor, models.Proveedor.id == models.Compra.proveedor_id)
        .options(joinedload(models.Compra.proveedor), joinedload(models.Compra.items).joinedload(models.CompraItem.insumo))
        .filter(models.Compra.tenant_id == tenant_id)
    )
    if estado:
        query = query.filter(models.Compra.estado == estado)
    columnas = [models.Proveedor.nombre, models.Compra.notas, models.Compra.estado]
    if params.q:
        # Permite buscar por el consecutivo: "COM-000012", "000012" o "12".
        digitos = "".join(ch for ch in params.q if ch.isdigit())
        if digitos:
            columnas.append(func.cast(models.Compra.numero, String))
            params.q = digitos if params.q.upper().startswith("COM") else params.q
    pagina = paginar(query, params, columnas_busqueda=columnas, orden=models.Compra.numero.desc())
    pagina["items"] = [services.serializar_compra(c) for c in pagina["items"]]
    return responder(pagina, params, schemas.CompraOut, COLUMNAS_COMPRAS, "compras")


@router.get("/compras/{compra_id}", response_model=schemas.CompraOut)
def obtener_compra(
    compra_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("compras", "ver")),
):
    return services.serializar_compra(services.obtener_compra_o_404(db, tenant_id, compra_id))


@router.get("/compras/{compra_id}/pdf")
def pdf_compra(
    compra_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("compras", "ver")),
):
    compra = services.obtener_compra_o_404(db, usuario.tenant_id, compra_id)
    tenant = db.query(Tenant).filter(Tenant.id == usuario.tenant_id).first()
    datos = services.serializar_compra(compra)
    pdf = generar_documento_pdf(
        titulo="Compra de insumos",
        codigo=datos["codigo"],
        empresa=tenant.nombre_empresa if tenant else NOMBRE_PRODUCTO,
        estado=compra.estado,
        fecha=compra.fecha,
        datos=[
            ("Proveedor", datos["proveedor_nombre"] or "—"),
            ("NIT", compra.proveedor.nit or "—"),
            ("Teléfono", compra.proveedor.telefono or "—"),
            ("Registrada por", usuario.nombre_completo),
        ],
        items=[
            {"descripcion": i["insumo_nombre"], "detalle": f"por {i['unidad']}", "cantidad": i["cantidad"], "precio_unitario": i["precio_unitario"], "subtotal": i["subtotal"]}
            for i in datos["items"]
        ],
        columna_descripcion="Insumo",
        columna_detalle="Unidad",
        total=compra.total,
        notas=compra.notas,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{datos["codigo"]}.pdf"'},
    )


@router.post("/compras", response_model=schemas.CompraOut, status_code=status.HTTP_201_CREATED)
def crear_compra(
    payload: schemas.CompraCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("compras", "crear")),
):
    return services.serializar_compra(services.crear_compra(db, usuario.tenant_id, payload, usuario.nombre_completo))


@router.post("/compras/{compra_id}/confirmar", response_model=schemas.CompraOut)
def confirmar_compra(
    compra_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("compras", "cambiar_estado")),
):
    return services.serializar_compra(services.confirmar_compra(db, usuario.tenant_id, compra_id, usuario.nombre_completo))


@router.post("/compras/{compra_id}/cancelar", response_model=schemas.CompraOut)
def cancelar_compra(
    compra_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("compras", "cambiar_estado")),
):
    return services.serializar_compra(services.cancelar_compra(db, tenant_id, compra_id))


@router.post("/compras/{compra_id}/anular", response_model=schemas.CompraOut)
def anular_compra(
    compra_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("compras", "anular")),
):
    return services.serializar_compra(services.anular_compra(db, usuario.tenant_id, compra_id, usuario.nombre_completo))
