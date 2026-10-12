import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import String, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.permisos import tenant_con_permiso, tiene_permiso, usuario_con_permiso
from app.core import mensajes
from app.core.errors import ConflictError
from app.core.exportar import campo, humanizar, responder, resumen_items
from app.core.paginacion import Pagina, ParametrosPagina, paginar
from app.core.pdf import generar_documento_pdf
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.compras import models, schemas, services
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/compras", tags=["Compras"])


def _aplicar_cambios(obj, payload) -> None:
    for campo, valor in payload.model_dump(exclude_unset=True).items():
        setattr(obj, campo, valor)


# =====================================================================
# Columnas de la exportación a CSV (`?formato=csv`, app/core/exportar.py)
# =====================================================================
_ESTADO = ("Estado", lambda f: "Activo" if f.get("activo") else "Inactivo")
COLUMNAS_CATALOGO = [
    ("Nombre", campo("nombre")),
    ("Descripción", campo("descripcion")),
    ("Productos", campo("productos_count")),
    _ESTADO,
    ("Creado", campo("created_at")),
]
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
    ("Productos que surte", lambda f: "; ".join(p["nombre"] for p in f.get("productos") or [])),
    _ESTADO,
]
COLUMNAS_COMPRAS = [
    ("Código", campo("codigo")),
    ("Fecha", campo("fecha")),
    ("Proveedor", campo("proveedor_nombre")),
    ("Estado", lambda f: humanizar(f.get("estado"))),
    ("Productos", resumen_items),
    ("Total", campo("total")),
    ("Notas", campo("notas")),
]


def columnas_productos(ver_costos: bool):
    """El costo solo va en el archivo de quien lo puede ver en pantalla."""
    columnas = [
        ("Nombre", campo("nombre")),
        ("SKU", campo("sku")),
        ("Categoría", campo("categoria_nombre")),
        ("Precio de venta", campo("precio")),
    ]
    if ver_costos:
        columnas.append(("Costo", campo("precio_compra")))
    return columnas + [
        ("Stock", campo("stock")),
        ("Stock mínimo", campo("stock_minimo")),
        ("Proveedores", lambda f: "; ".join(p["nombre"] for p in f.get("proveedores") or [])),
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
        orden=models.Categoria.nombre,
    )
    conteos = services.conteo_productos_por(db, tenant_id, models.Producto.categoria_id)
    pagina["items"] = [services.serializar_catalogo(c, conteos.get(c.id, 0)) for c in pagina["items"]]
    return responder(pagina, params, schemas.CategoriaOut, COLUMNAS_CATALOGO, "categorias")


@router.get("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def obtener_categoria(
    categoria_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "ver")),
):
    categoria = services.obtener_categoria_o_404(db, tenant_id, categoria_id)
    conteos = services.conteo_productos_por(db, tenant_id, models.Producto.categoria_id)
    return services.serializar_catalogo(categoria, conteos.get(categoria.id, 0))


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
    return services.serializar_catalogo(categoria)


@router.put("/categorias/{categoria_id}", response_model=schemas.CategoriaOut)
def actualizar_categoria(
    categoria_id: uuid.UUID,
    payload: schemas.CategoriaUpdate,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("categorias", "editar")),
):
    categoria = services.obtener_categoria_o_404(db, tenant_id, categoria_id)
    _aplicar_cambios(categoria, payload)
    nombre = categoria.nombre
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("una categoría", "nombre", nombre))
    db.refresh(categoria)
    conteos = services.conteo_productos_por(db, tenant_id, models.Producto.categoria_id)
    return services.serializar_catalogo(categoria, conteos.get(categoria.id, 0))


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
    return services.serializar_catalogo(categoria)


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
# Proveedores
# =====================================================================
@router.get("/proveedores", response_model=Pagina[schemas.ProveedorOut])
def listar_proveedores(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("proveedores", "ver")),
):
    # `serializar_proveedor` lee `p.productos` (muchos a muchos). Sin esto se
    # dispara una consulta por proveedor de la página: con 10 filas eran 10
    # consultas extra. `selectinload` las resuelve todas en UNA sola, y a
    # diferencia de `joinedload` no multiplica filas contra el LIMIT de la
    # paginación. Lo protege tests/test_rendimiento_consultas.py.
    query = (
        db.query(models.Proveedor)
        .options(selectinload(models.Proveedor.productos))
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
    proveedor = models.Proveedor(tenant_id=tenant_id, nombre=payload.nombre_derivado, **payload.model_dump(exclude={"producto_ids"}))
    db.add(proveedor)
    db.flush()
    services.sincronizar_productos_proveedor(db, tenant_id, proveedor, payload.producto_ids)
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
    datos = payload.model_dump(exclude={"activo", "producto_ids"})
    for campo, valor in datos.items():
        setattr(proveedor, campo, valor)
    if payload.activo is not None:
        proveedor.activo = payload.activo
    proveedor.nombre = payload.nombre_derivado
    services.sincronizar_productos_proveedor(db, tenant_id, proveedor, payload.producto_ids)
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
# Productos
# =====================================================================
def _producto_visible(usuario: Usuario, producto: models.Producto) -> dict:
    """El costo (`precio_compra`) delata el margen: solo lo ve quien puede ver
    compras. Un Cajero ve el precio de venta, nunca lo que costó."""
    datos = services.serializar_producto(producto)
    if not tiene_permiso(usuario, "compras", "ver"):
        datos["precio_compra"] = None
    return datos


def _sin_costo_si_no_ve_compras(usuario: Usuario, payload) -> None:
    """Quien no ve compras tampoco puede escribir el costo: se ignora el campo
    en lugar de dejar que lo sobrescriba sin saber cuánto vale."""
    if not tiene_permiso(usuario, "compras", "ver") and "precio_compra" in payload.model_fields_set:
        payload.precio_compra = None
        payload.model_fields_set.discard("precio_compra")


def _validar_relaciones_producto(db: Session, tenant_id: uuid.UUID, payload) -> None:
    datos = payload.model_dump(exclude_unset=True)
    if datos.get("categoria_id") is not None:
        services.obtener_categoria_o_404(db, tenant_id, datos["categoria_id"])


@router.get("/productos", response_model=Pagina[schemas.ProductoOut])
def listar_productos(
    params: ParametrosPagina = Depends(),
    activo: bool | None = Query(default=None),
    proveedor_id: uuid.UUID | None = Query(default=None, description="Solo productos que surte este proveedor"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "ver")),
):
    tenant_id = usuario.tenant_id
    query = (
        db.query(models.Producto)
        .options(joinedload(models.Producto.categoria), joinedload(models.Producto.proveedores))
        .filter(models.Producto.tenant_id == tenant_id)
    )
    if activo is not None:
        query = query.filter(models.Producto.activo == activo)
    if proveedor_id is not None:
        query = query.filter(models.Producto.proveedores.any(models.Proveedor.id == proveedor_id))
    pagina = paginar(
        query, params,
        columnas_busqueda=(models.Producto.nombre, models.Producto.sku, models.Producto.descripcion),
        orden=models.Producto.nombre,
    )
    pagina["items"] = [_producto_visible(usuario, p) for p in pagina["items"]]
    columnas = columnas_productos(tiene_permiso(usuario, "compras", "ver"))
    return responder(pagina, params, schemas.ProductoOut, columnas, "productos")


@router.get("/productos/{producto_id}", response_model=schemas.ProductoOut)
def obtener_producto(
    producto_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "ver")),
):
    return _producto_visible(usuario, services.obtener_producto_o_404(db, usuario.tenant_id, producto_id))


@router.get("/productos/{producto_id}/movimientos", response_model=Pagina[schemas.MovimientoOut])
def movimientos_producto(
    producto_id: uuid.UUID,
    params: ParametrosPagina = Depends(),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("productos", "ver")),
):
    """Trazabilidad del stock: cada compra, venta o anulación que lo movió."""
    services.obtener_producto_o_404(db, tenant_id, producto_id)
    query = db.query(models.MovimientoInventario).filter(
        models.MovimientoInventario.tenant_id == tenant_id, models.MovimientoInventario.producto_id == producto_id
    )
    return paginar(
        query, params,
        columnas_busqueda=(models.MovimientoInventario.documento_codigo, models.MovimientoInventario.tipo),
        orden=models.MovimientoInventario.created_at.desc(),
    )


@router.post("/productos", response_model=schemas.ProductoOut, status_code=status.HTTP_201_CREATED)
def crear_producto(
    payload: schemas.ProductoCreate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "crear")),
):
    tenant_id = usuario.tenant_id
    _sin_costo_si_no_ve_compras(usuario, payload)
    _validar_relaciones_producto(db, tenant_id, payload)
    # El stock nace en 0: solo lo mueven compras y ventas (ver movimientos).
    producto = models.Producto(tenant_id=tenant_id, stock=0, **payload.model_dump())
    db.add(producto)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un producto", "SKU", payload.sku))
    db.refresh(producto)
    return _producto_visible(usuario, producto)


@router.put("/productos/{producto_id}", response_model=schemas.ProductoOut)
def actualizar_producto(
    producto_id: uuid.UUID,
    payload: schemas.ProductoUpdate,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "editar")),
):
    tenant_id = usuario.tenant_id
    _sin_costo_si_no_ve_compras(usuario, payload)
    producto = services.obtener_producto_o_404(db, tenant_id, producto_id)
    _validar_relaciones_producto(db, tenant_id, payload)
    _aplicar_cambios(producto, payload)
    sku = producto.sku
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(mensajes.ya_existe("un producto", "SKU", sku))
    db.refresh(producto)
    return _producto_visible(usuario, producto)


@router.patch("/productos/{producto_id}/estado", response_model=schemas.ProductoOut)
def cambiar_estado_producto(
    producto_id: uuid.UUID,
    payload: schemas.CambioEstado,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("productos", "cambiar_estado")),
):
    producto = services.obtener_producto_o_404(db, usuario.tenant_id, producto_id)
    producto.activo = payload.activo
    db.commit()
    db.refresh(producto)
    return _producto_visible(usuario, producto)


@router.delete("/productos/{producto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_producto(
    producto_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("productos", "eliminar")),
):
    producto = services.obtener_producto_o_404(db, tenant_id, producto_id)
    try:
        db.delete(producto)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ConflictError(
            f"No se puede eliminar el producto {producto.nombre}: tiene movimientos de inventario, "
            "compras o ventas registradas. Desactívalo en su lugar para conservar el historial."
        )


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
        .options(joinedload(models.Compra.proveedor), joinedload(models.Compra.items).joinedload(models.CompraItem.producto))
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
        titulo="Orden de compra",
        codigo=datos["codigo"],
        empresa=tenant.nombre_empresa if tenant else "JS Company",
        estado=compra.estado,
        fecha=compra.fecha,
        datos=[
            ("Proveedor", datos["proveedor_nombre"] or "—"),
            ("NIT", compra.proveedor.nit or "—"),
            ("Teléfono", compra.proveedor.telefono or "—"),
            ("Registrada por", usuario.nombre_completo),
        ],
        items=datos["items"],
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
