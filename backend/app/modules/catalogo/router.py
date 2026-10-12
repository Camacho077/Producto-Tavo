"""
CARTA DEL RESTAURANTE (2026-10-12): categorías, platos (con receta y
modificadores) y combos/promociones. Costo, margen y porcentaje de costo de
cada plato salen de su receta; solo los ve quien tiene `costos.ver`.
"""
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import mensajes
from app.core.errors import ConflictError, NotFoundError
from app.core.exportar import campo, responder
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.permisos import tenant_con_permiso, tiene_permiso, usuario_con_permiso
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.ajustes.schemas import ConfiguracionRestaurante, configuracion_de
from app.modules.catalogo import models, schemas, services
from app.modules.imagenes import services as imagenes
from app.modules.inventario.unidades import legible
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/catalogo", tags=["Carta"])


def _config(db: Session, tenant_id: uuid.UUID) -> ConfiguracionRestaurante:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFoundError("La empresa de tu usuario ya no existe: vuelve a iniciar sesión.")
    return configuracion_de(tenant)


# =====================================================================
# Exportación a CSV
# =====================================================================
_ESTADO = ("Estado", lambda f: "Activo" if f.get("activo") else "Inactivo")
COLUMNAS_CATEGORIAS = [
    ("Nombre", campo("nombre")),
    ("Descripción", campo("descripcion")),
    ("Orden", campo("orden")),
    ("Productos", campo("productos_count")),
    _ESTADO,
]


def columnas_productos(ver_costos: bool):
    columnas = [
        ("Nombre", campo("nombre")),
        ("Tipo", lambda f: "Combo" if f.get("tipo") == "combo" else "Plato"),
        ("Categoría", campo("categoria_nombre")),
        ("Precio", campo("precio")),
        ("Va a cocina", campo("va_a_cocina")),
        ("Agotado hoy", campo("agotado_hoy")),
    ]
    if ver_costos:
        columnas += [
            ("Costo", campo("costo")),
            ("Precio sin impuesto", campo("precio_neto")),
            ("Margen", campo("margen")),
            ("% de costo", campo("porcentaje_costo")),
        ]
    return columnas + [
        ("Receta", lambda f: "; ".join(f"{l['insumo_nombre']} {legible(l['cantidad'], l['unidad'])}" for l in f.get("receta") or [])),
        ("Platos del combo", lambda f: "; ".join(f"{c['producto_nombre']} × {c['cantidad']}" for c in f.get("componentes") or [])),
        _ESTADO,
    ]


# =====================================================================
# Categorías
# =====================================================================
@router.get("/categorias", response_model=Pagina[schemas.CategoriaOut])
def listar_categorias(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "ver")),
):
    query = db.query(models.Categoria).filter(models.Categoria.tenant_id == tenant_id)
    if activo is not None:
        query = query.filter(models.Categoria.activo == activo)
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Categoria.nombre, models.Categoria.descripcion),
        orden=(models.Categoria.orden, models.Categoria.nombre),
    )
    conteos = services.conteo_productos_por_categoria(db, tenant_id)
    pagina["items"] = [services.serializar_categoria(c, conteos.get(c.id, 0)) for c in pagina["items"]]
    return responder(pagina, params, schemas.CategoriaOut, COLUMNAS_CATEGORIAS, "categorias")


@router.get("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def obtener_categoria(
    categoria_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "ver")),
):
    categoria = services.obtener_categoria_o_404(db, tenant_id, categoria_id)
    return services.serializar_categoria(categoria, services.conteo_productos_por_categoria(db, tenant_id).get(categoria.id, 0))


@router.post("/categorias", response_model=schemas.CategoriaOut, status_code=status.HTTP_201_CREATED)
def crear_categoria(
    payload: schemas.CategoriaCreate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "crear")),
):
    categoria = models.Categoria(tenant_id=tenant_id, **payload.model_dump())
    db.add(categoria)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una categoría", "nombre", payload.nombre))
    db.refresh(categoria)
    return services.serializar_categoria(categoria)


@router.put("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def actualizar_categoria(
    categoria_id: uuid.UUID,
    payload: schemas.CategoriaUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "editar")),
):
    categoria = services.obtener_categoria_o_404(db, tenant_id, categoria_id)
    for clave, valor in payload.model_dump(exclude_unset=True).items():
        if valor is not None or clave == "descripcion":
            setattr(categoria, clave, valor)
    nombre = categoria.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una categoría", "nombre", nombre))
    db.refresh(categoria)
    return services.serializar_categoria(categoria, services.conteo_productos_por_categoria(db, tenant_id).get(categoria.id, 0))


@router.patch("/categorias/{categoria_id}/estado", response_model=schemas.CategoriaOut)
def cambiar_estado_categoria(
    categoria_id: uuid.UUID,
    payload: schemas.CambioEstado,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "cambiar_estado")),
):
    categoria = services.obtener_categoria_o_404(db, tenant_id, categoria_id)
    categoria.activo = payload.activo
    db.commit()
    db.refresh(categoria)
    return services.serializar_categoria(categoria)


@router.delete("/categorias/{categoria_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_categoria(
    categoria_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "eliminar")),
):
    categoria = services.obtener_categoria_o_404(db, tenant_id, categoria_id)
    asociados = db.query(func.count(models.Producto.id)).filter(models.Producto.categoria_id == categoria.id).scalar()
    if asociados:
        raise ConflictError(
            mensajes.no_se_puede_eliminar(
                "la categoría", categoria.nombre, asociados, "producto", "productos",
                "Puedes desactivarla en su lugar para conservar el historial.",
            )
        )
    db.delete(categoria)
    db.commit()


# =====================================================================
# Productos: platos y combos
# =====================================================================
def _ver_costos(usuario: Usuario) -> bool:
    return tiene_permiso(usuario, "costos", "ver")


def _serializar(db: Session, usuario: Usuario, producto: models.Producto) -> dict:
    return services.serializar_producto(producto, _config(db, usuario.tenant_id), _ver_costos(usuario))


def _cargar(db: Session, tenant_id: uuid.UUID, producto_id: uuid.UUID) -> models.Producto:
    producto = (
        db.query(models.Producto)
        .options(*services.opciones_carga_producto())
        .filter(models.Producto.id == producto_id, models.Producto.tenant_id == tenant_id)
        .first()
    )
    if producto is None:
        raise NotFoundError(mensajes.no_existe("El producto indicado"))
    return producto


def _validar_categoria(db: Session, tenant_id: uuid.UUID, categoria_id) -> None:
    if categoria_id is not None:
        services.obtener_categoria_o_404(db, tenant_id, categoria_id)


def _commit_producto(db: Session, sku: str | None) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un producto", "código", sku or "indicado"))


@router.get("/productos", response_model=Pagina[schemas.ProductoOut])
def listar_productos(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    tipo: str | None = Query(default=None, pattern="^(plato|combo)$"),
    categoria_id: uuid.UUID | None = Query(default=None),
    insumo_id: uuid.UUID | None = Query(default=None, description="Solo los platos que usan este insumo"),
    disponible: bool | None = Query(default=None, description="Activos, vigentes y no agotados hoy"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "ver")),
):
    tenant_id = usuario.tenant_id
    config = _config(db, tenant_id)
    query = db.query(models.Producto).options(*services.opciones_carga_producto()).filter(models.Producto.tenant_id == tenant_id)
    if activo is not None:
        query = query.filter(models.Producto.activo == activo)
    if tipo:
        query = query.filter(models.Producto.tipo == tipo)
    if categoria_id:
        query = query.filter(models.Producto.categoria_id == categoria_id)
    if insumo_id:
        query = query.filter(models.Producto.receta.any(models.RecetaItem.insumo_id == insumo_id))
    if disponible is not None:
        jornada = services.jornada_actual(config)
        hoy = services.hoy_negocio()
        condicion = (
            models.Producto.activo.is_(True)
            & or_(models.Producto.agotado_fecha.is_(None), models.Producto.agotado_fecha != jornada)
            & or_(models.Producto.vigente_desde.is_(None), models.Producto.vigente_desde <= hoy)
            & or_(models.Producto.vigente_hasta.is_(None), models.Producto.vigente_hasta >= hoy)
        )
        query = query.filter(condicion if disponible else ~condicion)
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Producto.nombre, models.Producto.sku, models.Producto.descripcion),
        orden=models.Producto.nombre,
    )
    ver_costos = _ver_costos(usuario)
    jornada = services.jornada_actual(config)
    items = [services.serializar_producto(p, config, ver_costos, jornada) for p in pagina["items"]]
    if disponible:
        # Los días de la semana se filtran aquí (JSON): pocos combos por empresa.
        items = [i for i in items if i["disponible"]]
    pagina["items"] = items
    return responder(pagina, params, schemas.ProductoOut, columnas_productos(ver_costos), "carta")


@router.get("/productos/{producto_id}", response_model=schemas.ProductoOut)
def obtener_producto(
    producto_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "ver")),
):
    return _serializar(db, usuario, _cargar(db, usuario.tenant_id, producto_id))


@router.post("/productos", response_model=schemas.ProductoOut, status_code=status.HTTP_201_CREATED)
def crear_producto(
    payload: schemas.ProductoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "crear")),
):
    tenant_id = usuario.tenant_id
    _validar_categoria(db, tenant_id, payload.categoria_id)
    producto = models.Producto(
        tenant_id=tenant_id,
        **payload.model_dump(exclude={"receta", "modificadores", "componentes"}),
    )
    if payload.tipo == "combo":
        producto.va_a_cocina = False  # se deriva de sus platos
    db.add(producto)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un producto", "código", payload.sku or "indicado"))
    services.guardar_receta(db, tenant_id, producto, payload.receta)
    db.flush()
    services.guardar_modificadores(db, tenant_id, producto, payload.modificadores)
    if payload.tipo == "combo":
        services.guardar_componentes(db, tenant_id, producto, payload.componentes)
    _commit_producto(db, payload.sku)
    return _serializar(db, usuario, _cargar(db, tenant_id, producto.id))


@router.put("/productos/{producto_id}", response_model=schemas.ProductoOut)
def actualizar_producto(
    producto_id: uuid.UUID,
    payload: schemas.ProductoUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "editar")),
):
    tenant_id = usuario.tenant_id
    producto = _cargar(db, tenant_id, producto_id)
    datos = payload.model_dump(exclude_unset=True, exclude={"receta", "modificadores", "componentes"})
    if "categoria_id" in datos:
        _validar_categoria(db, tenant_id, datos["categoria_id"])
    for clave, valor in datos.items():
        if valor is not None or clave in ("categoria_id", "sku", "descripcion", "vigente_desde", "vigente_hasta", "dias_semana"):
            setattr(producto, clave, valor)
    if producto.vigente_desde and producto.vigente_hasta and producto.vigente_hasta < producto.vigente_desde:
        raise ConflictError("La vigencia termina antes de empezar: revisa las fechas.")
    if producto.tipo == "combo":
        if payload.receta or payload.modificadores:
            raise ConflictError("Un combo no lleva receta ni modificadores propios: los tiene cada plato.")
        if payload.componentes is not None:
            if not payload.componentes:
                raise ConflictError("Un combo necesita al menos un plato.")
            services.guardar_componentes(db, tenant_id, producto, payload.componentes)
    else:
        if payload.componentes:
            raise ConflictError("Solo los combos llevan platos dentro.")
        if payload.receta is not None:
            services.guardar_receta(db, tenant_id, producto, payload.receta)
            db.flush()
        if payload.modificadores is not None:
            services.guardar_modificadores(db, tenant_id, producto, payload.modificadores)
    _commit_producto(db, producto.sku)
    db.expire_all()
    return _serializar(db, usuario, _cargar(db, tenant_id, producto_id))


@router.patch("/productos/{producto_id}/estado", response_model=schemas.ProductoOut)
def cambiar_estado_producto(
    producto_id: uuid.UUID,
    payload: schemas.CambioEstado,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "cambiar_estado")),
):
    producto = _cargar(db, usuario.tenant_id, producto_id)
    producto.activo = payload.activo
    db.commit()
    return _serializar(db, usuario, _cargar(db, usuario.tenant_id, producto_id))


@router.patch("/productos/{producto_id}/agotado", response_model=schemas.ProductoOut)
def marcar_agotado(
    producto_id: uuid.UUID,
    payload: schemas.CambioAgotado,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "cambiar_estado")),
):
    """"Agotado hoy": no se ofrece en lo que queda de la jornada, sin
    desactivarlo. Al empezar la jornada siguiente vuelve solo."""
    producto = _cargar(db, usuario.tenant_id, producto_id)
    producto.agotado_fecha = services.jornada_actual(_config(db, usuario.tenant_id)) if payload.agotado else None
    db.commit()
    return _serializar(db, usuario, _cargar(db, usuario.tenant_id, producto_id))


@router.delete("/productos/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(
    producto_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("productos", "eliminar")),
):
    producto = services.obtener_producto_o_404(db, tenant_id, producto_id)
    combos = (
        db.query(models.Producto.nombre)
        .join(models.ComboItem, models.ComboItem.combo_id == models.Producto.id)
        .filter(models.ComboItem.producto_id == producto.id, models.ComboItem.tenant_id == tenant_id)
        .all()
    )
    if combos:
        raise ConflictError(
            f"No se puede eliminar {producto.nombre}: está en el combo {', '.join(n for (n,) in combos)}. "
            "Quítalo del combo o desactívalo."
        )
    imagen_id = producto.imagen_id
    nombre = producto.nombre
    try:
        db.delete(producto)
        db.flush()
        imagenes.borrar(db, tenant_id, imagen_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            f"No se puede eliminar {nombre}: ya tiene ventas u órdenes registradas. "
            "Desactívalo en su lugar para conservar el historial."
        )


@router.put("/productos/{producto_id}/imagen", response_model=schemas.ProductoOut)
def subir_imagen_producto(
    producto_id: uuid.UUID,
    archivo: tuple[bytes, str] = Depends(imagenes.leer_imagen_subida),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "editar")),
):
    """Foto del plato: se recorta al cuadrado central, 640 px, WebP."""
    producto = services.obtener_producto_o_404(db, usuario.tenant_id, producto_id)
    contenido, tipo = archivo
    anterior = producto.imagen_id
    imagen = imagenes.guardar(db, usuario.tenant_id, contenido, tipo, "plato")
    producto.imagen_id = imagen.id
    db.flush()
    imagenes.borrar(db, usuario.tenant_id, anterior)
    db.commit()
    return _serializar(db, usuario, _cargar(db, usuario.tenant_id, producto_id))


@router.delete("/productos/{producto_id}/imagen", response_model=schemas.ProductoOut)
def quitar_imagen_producto(
    producto_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "editar")),
):
    producto = services.obtener_producto_o_404(db, usuario.tenant_id, producto_id)
    anterior = producto.imagen_id
    producto.imagen_id = None
    db.flush()
    imagenes.borrar(db, usuario.tenant_id, anterior)
    db.commit()
    return _serializar(db, usuario, _cargar(db, usuario.tenant_id, producto_id))
