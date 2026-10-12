"""
AJUSTES DEL RESTAURANTE (2026-10-12): datos del negocio (salen en la comanda
y la factura), configuración operativa (tipos de orden, medios de pago,
impuesto, propina, cocina, jornada, impresoras), y zonas y mesas.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core import mensajes
from app.core.errors import ConflictError, NotFoundError
from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.permisos import tenant_con_permiso
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.ajustes import models, schemas, services
from app.modules.imagenes import services as imagenes

router = APIRouter(prefix="/ajustes", tags=["Ajustes"])


def _tenant(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("La empresa de tu usuario ya no existe: vuelve a iniciar sesión.")
    return tenant


# =====================================================================
# Datos del negocio
# =====================================================================
@router.get("/negocio", response_model=schemas.NegocioOut)
def ver_negocio(db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("ajustes", "ver"))):
    return _tenant(db, tenant_id)


@router.put("/negocio", response_model=schemas.NegocioOut)
def editar_negocio(
    payload: schemas.NegocioUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("ajustes", "editar")),
):
    tenant = _tenant(db, tenant_id)
    for clave, valor in payload.model_dump().items():
        setattr(tenant, clave, valor)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(f"El NIT {payload.nit} ya está registrado por otro restaurante en el sistema.")
    db.refresh(tenant)
    return tenant


@router.put("/negocio/logo", response_model=schemas.NegocioOut)
def subir_logo(
    archivo: tuple[bytes, str] = Depends(imagenes.leer_imagen_subida),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("ajustes", "editar")),
):
    """Cuerpo crudo de la imagen (JPG, PNG o WebP, máx. 5 MB). Se encoge a
    600 × 300 y se guarda en WebP; el logo anterior se borra."""
    tenant = _tenant(db, tenant_id)
    contenido, tipo = archivo
    imagen = imagenes.guardar(db, tenant_id, contenido, tipo, "logo", anterior_id=tenant.logo_id)
    tenant.logo_id = imagen.id
    db.commit()
    db.refresh(tenant)
    return tenant


@router.delete("/negocio/logo", response_model=schemas.NegocioOut)
def quitar_logo(db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("ajustes", "editar"))):
    tenant = _tenant(db, tenant_id)
    imagenes.borrar(db, tenant_id, tenant.logo_id)
    tenant.logo_id = None
    db.commit()
    db.refresh(tenant)
    return tenant


# =====================================================================
# Configuración operativa
# =====================================================================
@router.get("/restaurante", response_model=schemas.ConfiguracionRestaurante)
def ver_configuracion(db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("ajustes", "ver"))):
    return schemas.configuracion_de(_tenant(db, tenant_id))


@router.put("/restaurante", response_model=schemas.ConfiguracionRestaurante)
def editar_configuracion(
    payload: schemas.ConfiguracionRestaurante,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("ajustes", "editar")),
):
    tenant = _tenant(db, tenant_id)
    tenant.configuracion = payload.model_dump(mode="json")
    db.commit()
    return schemas.configuracion_de(tenant)


# =====================================================================
# Zonas
# =====================================================================
COLUMNAS_ZONAS = [("Zona", campo("nombre")), ("Orden", campo("orden")), ("Mesas", campo("mesas_count"))]
COLUMNAS_MESAS = [
    ("Mesa", campo("nombre")),
    ("Zona", campo("zona_nombre")),
    ("Puestos", campo("puestos")),
    ("Estado", lambda f: "Activa" if f.get("activo") else "Inactiva"),
]


@router.get("/zonas", response_model=Pagina[schemas.ZonaOut])
def listar_zonas(
    params: ParametrosPagina = Depends(),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "ver")),
):
    query = db.query(models.Zona).filter(models.Zona.tenant_id == tenant_id)
    pagina = paginar(query, params, columnas_busqueda=(models.Zona.nombre,), orden=(models.Zona.orden, models.Zona.nombre))
    conteos = services.conteo_mesas_por_zona(db, tenant_id)
    pagina["items"] = [services.serializar_zona(z, conteos.get(z.id, 0)) for z in pagina["items"]]
    return responder(pagina, params, schemas.ZonaOut, COLUMNAS_ZONAS, "zonas")


@router.get("/zonas/{zona_id}", response_model=schemas.ZonaOut)
def obtener_zona(zona_id: uuid.UUID, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "ver"))):
    zona = services.obtener_zona_o_404(db, tenant_id, zona_id)
    return services.serializar_zona(zona, services.conteo_mesas_por_zona(db, tenant_id).get(zona.id, 0))


@router.post("/zonas", response_model=schemas.ZonaOut, status_code=status.HTTP_201_CREATED)
def crear_zona(payload: schemas.ZonaCreate, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "crear"))):
    zona = models.Zona(tenant_id=tenant_id, **payload.model_dump())
    db.add(zona)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una zona", "nombre", payload.nombre))
    db.refresh(zona)
    return services.serializar_zona(zona)


@router.put("/zonas/{zona_id}", response_model=schemas.ZonaOut)
def editar_zona(
    zona_id: uuid.UUID,
    payload: schemas.ZonaUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "editar")),
):
    zona = services.obtener_zona_o_404(db, tenant_id, zona_id)
    for clave, valor in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(zona, clave, valor)
    nombre = zona.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una zona", "nombre", nombre))
    db.refresh(zona)
    return services.serializar_zona(zona, services.conteo_mesas_por_zona(db, tenant_id).get(zona.id, 0))


@router.delete("/zonas/{zona_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_zona(zona_id: uuid.UUID, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "eliminar"))):
    zona = services.obtener_zona_o_404(db, tenant_id, zona_id)
    mesas = db.query(func.count(models.Mesa.id)).filter(models.Mesa.zona_id == zona.id).scalar()
    if mesas:
        raise ConflictError(
            mensajes.no_se_puede_eliminar(
                "la zona", zona.nombre, mesas, "mesa", "mesas", "Pasa sus mesas a otra zona primero."
            )
        )
    db.delete(zona)
    db.commit()


# =====================================================================
# Mesas
# =====================================================================
def _validar_zona(db: Session, tenant_id: uuid.UUID, zona_id) -> None:
    if zona_id is not None:
        services.obtener_zona_o_404(db, tenant_id, zona_id)


@router.get("/mesas", response_model=Pagina[schemas.MesaOut])
def listar_mesas(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    zona_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "ver")),
):
    query = db.query(models.Mesa).options(joinedload(models.Mesa.zona)).filter(models.Mesa.tenant_id == tenant_id)
    if activo is not None:
        query = query.filter(models.Mesa.activo == activo)
    if zona_id is not None:
        query = query.filter(models.Mesa.zona_id == zona_id)
    # Orden natural: B2 antes que B10 (largo primero, luego texto).
    pagina = paginar(
        query, params, columnas_busqueda=(models.Mesa.nombre,),
        orden=(func.length(models.Mesa.nombre), models.Mesa.nombre),
    )
    pagina["items"] = [services.serializar_mesa(m) for m in pagina["items"]]
    return responder(pagina, params, schemas.MesaOut, COLUMNAS_MESAS, "mesas")


@router.get("/mesas/{mesa_id}", response_model=schemas.MesaOut)
def obtener_mesa(mesa_id: uuid.UUID, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "ver"))):
    return services.serializar_mesa(services.obtener_mesa_o_404(db, tenant_id, mesa_id))


@router.post("/mesas", response_model=schemas.MesaOut, status_code=status.HTTP_201_CREATED)
def crear_mesa(payload: schemas.MesaCreate, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "crear"))):
    _validar_zona(db, tenant_id, payload.zona_id)
    mesa = models.Mesa(tenant_id=tenant_id, **payload.model_dump())
    db.add(mesa)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una mesa", "nombre", payload.nombre))
    db.refresh(mesa)
    return services.serializar_mesa(mesa)


@router.put("/mesas/{mesa_id}", response_model=schemas.MesaOut)
def editar_mesa(
    mesa_id: uuid.UUID,
    payload: schemas.MesaUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "editar")),
):
    mesa = services.obtener_mesa_o_404(db, tenant_id, mesa_id)
    datos = payload.model_dump(exclude_unset=True)
    if "zona_id" in datos:
        _validar_zona(db, tenant_id, datos["zona_id"])
    for clave, valor in datos.items():
        if valor is not None or clave == "zona_id":
            setattr(mesa, clave, valor)
    nombre = mesa.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una mesa", "nombre", nombre))
    db.refresh(mesa)
    return services.serializar_mesa(mesa)


@router.patch("/mesas/{mesa_id}/estado", response_model=schemas.MesaOut)
def cambiar_estado_mesa(
    mesa_id: uuid.UUID,
    payload: schemas.CambioEstado,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "cambiar_estado")),
):
    mesa = services.obtener_mesa_o_404(db, tenant_id, mesa_id)
    mesa.activo = payload.activo
    db.commit()
    db.refresh(mesa)
    return services.serializar_mesa(mesa)


@router.delete("/mesas/{mesa_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_mesa(mesa_id: uuid.UUID, db: Session = Depends(get_db), tenant_id: uuid.UUID = Depends(tenant_con_permiso("mesas", "eliminar"))):
    mesa = services.obtener_mesa_o_404(db, tenant_id, mesa_id)
    try:
        db.delete(mesa)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            f"No se puede eliminar la mesa {mesa.nombre}: tiene órdenes registradas. "
            "Desactívala en su lugar para conservar el historial."
        )
