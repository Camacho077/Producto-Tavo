import uuid
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.consultas import obtener_del_tenant
from app.core.errors import ConflictError, NotFoundError
from app.core.tiempo import ahora_utc
from app.core.validaciones import ZONA_NEGOCIO
from app.modules.ajustes.schemas import ConfiguracionRestaurante
from app.modules.ajustes.services import fecha_jornada
from app.modules.catalogo import models, recetas
from app.modules.inventario.models import Insumo
from app.modules.inventario.unidades import compatibles, unidades_de_familia


# ---------- Búsquedas o 404 (siempre dentro del tenant) ----------
def obtener_categoria_o_404(db: Session, tenant_id: uuid.UUID, categoria_id: uuid.UUID) -> models.Categoria:
    return obtener_del_tenant(db, models.Categoria, tenant_id, categoria_id, "La categoría indicada")


def obtener_producto_o_404(db: Session, tenant_id: uuid.UUID, producto_id: uuid.UUID) -> models.Producto:
    return obtener_del_tenant(db, models.Producto, tenant_id, producto_id, "El producto indicado")


def opciones_carga_producto():
    """Lo que hace falta para costear y mostrar un producto sin una consulta
    por fila (lo exige tests/test_rendimiento_consultas.py)."""
    return (
        joinedload(models.Producto.categoria),
        selectinload(models.Producto.receta).joinedload(models.RecetaItem.insumo),
        selectinload(models.Producto.modificadores).joinedload(models.Modificador.insumo),
        selectinload(models.Producto.componentes)
        .joinedload(models.ComboItem.producto)
        .selectinload(models.Producto.receta)
        .joinedload(models.RecetaItem.insumo),
    )


# ---------- Disponibilidad ----------
def hoy_negocio() -> date:
    return (ahora_utc() + ZONA_NEGOCIO.utcoffset(None)).date()


def jornada_actual(config: ConfiguracionRestaurante) -> date:
    return fecha_jornada(config, ahora_utc())


def vigente(p: models.Producto, hoy: date | None = None) -> bool:
    """¿Se puede ofrecer HOY? Combos/promociones con fechas y días."""
    hoy = hoy or hoy_negocio()
    if p.vigente_desde and hoy < p.vigente_desde:
        return False
    if p.vigente_hasta and hoy > p.vigente_hasta:
        return False
    if p.dias_semana and hoy.weekday() not in p.dias_semana:
        return False
    return True


def agotado_hoy(p: models.Producto, jornada: date) -> bool:
    return p.agotado_fecha is not None and p.agotado_fecha == jornada


# ---------- Serialización ----------
def serializar_categoria(c: models.Categoria, productos_count: int = 0) -> dict:
    return {
        "id": c.id,
        "nombre": c.nombre,
        "descripcion": c.descripcion,
        "orden": c.orden,
        "activo": c.activo,
        "productos_count": productos_count,
        "created_at": c.created_at,
    }


def serializar_producto(p: models.Producto, config: ConfiguracionRestaurante, ver_costos: bool, jornada: date | None = None) -> dict:
    jornada = jornada or jornada_actual(config)
    agotado = agotado_hoy(p, jornada)
    esta_vigente = vigente(p)
    datos = {
        "id": p.id,
        "tipo": p.tipo,
        "nombre": p.nombre,
        "sku": p.sku,
        "descripcion": p.descripcion,
        "precio": p.precio,
        "activo": p.activo,
        "categoria_id": p.categoria_id,
        "categoria_nombre": p.categoria.nombre if p.categoria else None,
        "imagen_id": p.imagen_id,
        "va_a_cocina": p.va_a_cocina if p.tipo == "plato" else any(c.producto.va_a_cocina for c in p.componentes),
        "agotado_hoy": agotado,
        "vigente": esta_vigente,
        "disponible": bool(p.activo and esta_vigente and not agotado),
        "vigente_desde": p.vigente_desde,
        "vigente_hasta": p.vigente_hasta,
        "dias_semana": p.dias_semana,
        "tiene_receta": bool(p.receta) if p.tipo == "plato" else bool(p.componentes) and all(c.producto.receta for c in p.componentes),
        "receta": [
            {
                "id": l.id,
                "insumo_id": l.insumo_id,
                "insumo_nombre": l.insumo.nombre,
                "insumo_unidad": l.insumo.unidad,
                "cantidad": l.cantidad,
                "unidad": l.unidad,
                "merma_porcentaje": l.merma_porcentaje,
                "costo": recetas._a_pesos(recetas.costo_linea(l)) if ver_costos else None,
            }
            for l in p.receta
        ],
        "modificadores": [
            {
                "id": m.id,
                "tipo": m.tipo,
                "nombre": m.nombre,
                "precio": m.precio,
                "insumo_id": m.insumo_id,
                "insumo_nombre": m.insumo.nombre if m.insumo else None,
                "cantidad": m.cantidad,
                "unidad": m.unidad,
                "activo": m.activo,
                "costo": recetas.costo_modificador(m) if ver_costos else None,
            }
            for m in p.modificadores
        ],
        "componentes": [
            {
                "producto_id": c.producto_id,
                "producto_nombre": c.producto.nombre,
                "cantidad": c.cantidad,
                "va_a_cocina": c.producto.va_a_cocina,
                "precio": c.producto.precio,
                "costo": recetas.costo_de_producto(c.producto) if ver_costos else None,
            }
            for c in p.componentes
        ],
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }
    if ver_costos:
        datos.update(recetas.costeo(p, config))
    else:
        datos.update({"costo": None, "precio_neto": None, "margen": None, "porcentaje_costo": None})
    return datos


def conteo_productos_por_categoria(db: Session, tenant_id: uuid.UUID) -> dict:
    filas = (
        db.query(models.Producto.categoria_id, func.count(models.Producto.id))
        .filter(models.Producto.tenant_id == tenant_id, models.Producto.categoria_id.isnot(None))
        .group_by(models.Producto.categoria_id)
        .all()
    )
    return dict(filas)


# ---------- Guardar receta, modificadores y componentes ----------
def _insumos_del_tenant(db: Session, tenant_id: uuid.UUID, ids) -> dict:
    ids = set(ids)
    if not ids:
        return {}
    encontrados = {i.id: i for i in db.query(Insumo).filter(Insumo.tenant_id == tenant_id, Insumo.id.in_(ids)).all()}
    if len(encontrados) != len(ids):
        raise NotFoundError("Uno de los insumos indicados ya no existe o pertenece a otra empresa: recarga la pantalla.")
    return encontrados


def _unidad_valida(insumo: Insumo, unidad: str, donde: str) -> None:
    if not compatibles(unidad, insumo.unidad):
        opciones = ", ".join(unidades_de_familia(insumo.unidad))
        raise ConflictError(
            f"{donde}: {insumo.nombre} se lleva en {insumo.unidad} y no se puede escribir en {unidad}. "
            f"Usa {opciones}."
        )


def guardar_receta(db: Session, tenant_id: uuid.UUID, producto: models.Producto, lineas) -> None:
    insumos = _insumos_del_tenant(db, tenant_id, [l.insumo_id for l in lineas])
    vistos = set()
    for l in lineas:
        if l.insumo_id in vistos:
            raise ConflictError(
                f"La receta de {producto.nombre} repite el insumo {insumos[l.insumo_id].nombre}: súmalo en una sola línea."
            )
        vistos.add(l.insumo_id)
        _unidad_valida(insumos[l.insumo_id], l.unidad, f"Receta de {producto.nombre}")
    producto.receta = [
        models.RecetaItem(
            tenant_id=tenant_id,
            insumo_id=l.insumo_id,
            cantidad=l.cantidad,
            unidad=l.unidad,
            merma_porcentaje=l.merma_porcentaje,
            orden=i,
        )
        for i, l in enumerate(lineas)
    ]


def guardar_modificadores(db: Session, tenant_id: uuid.UUID, producto: models.Producto, mods) -> None:
    insumos = _insumos_del_tenant(db, tenant_id, [m.insumo_id for m in mods if m.insumo_id])
    receta_ids = {l.insumo_id for l in producto.receta}
    existentes = {m.id: m for m in producto.modificadores}
    nombres = set()
    nuevos = []
    for i, m in enumerate(mods):
        clave = (m.tipo, m.nombre.strip().lower())
        if clave in nombres:
            raise ConflictError(f"{producto.nombre} ya tiene el modificador «{m.tipo} {m.nombre}»: no lo repitas.")
        nombres.add(clave)
        if m.insumo_id:
            insumo = insumos[m.insumo_id]
            if m.tipo == "sin" and m.insumo_id not in receta_ids:
                raise ConflictError(
                    f"«Sin {m.nombre}» quita {insumo.nombre}, pero ese insumo no está en la receta de {producto.nombre}."
                )
            if m.tipo == "extra":
                _unidad_valida(insumo, m.unidad, f"Extra «{m.nombre}»")
        obj = existentes.pop(m.id, None) if m.id else None
        if obj is None:
            obj = models.Modificador(tenant_id=tenant_id)
        obj.tipo, obj.nombre, obj.precio = m.tipo, m.nombre, m.precio
        obj.insumo_id, obj.cantidad, obj.unidad = m.insumo_id, m.cantidad, m.unidad
        obj.activo, obj.orden = m.activo, i
        nuevos.append(obj)
    producto.modificadores = nuevos


def guardar_componentes(db: Session, tenant_id: uuid.UUID, combo: models.Producto, componentes) -> None:
    ids = [c.producto_id for c in componentes]
    if len(set(ids)) != len(ids):
        raise ConflictError(f"El combo {combo.nombre} repite un plato: súbele la cantidad en vez de repetirlo.")
    platos = {
        p.id: p for p in db.query(models.Producto).filter(models.Producto.tenant_id == tenant_id, models.Producto.id.in_(ids)).all()
    }
    if len(platos) != len(set(ids)):
        raise NotFoundError("Uno de los platos del combo ya no existe o pertenece a otra empresa: recarga la pantalla.")
    for p in platos.values():
        if p.tipo == "combo":
            raise ConflictError(f"{p.nombre} es un combo: un combo solo puede llevar platos, no otros combos.")
    combo.componentes = [
        models.ComboItem(tenant_id=tenant_id, producto_id=c.producto_id, cantidad=c.cantidad, orden=i)
        for i, c in enumerate(componentes)
    ]


def mensaje_insumo_en_uso(db: Session, tenant_id: uuid.UUID, insumo: Insumo) -> str | None:
    """Por qué no se puede borrar un insumo, o None si se puede."""
    platos = (
        db.query(models.Producto.nombre)
        .join(models.RecetaItem, models.RecetaItem.producto_id == models.Producto.id)
        .filter(models.RecetaItem.tenant_id == tenant_id, models.RecetaItem.insumo_id == insumo.id)
        .order_by(models.Producto.nombre)
        .all()
    )
    if platos:
        nombres = ", ".join(n for (n,) in platos[:3]) + (f" y {len(platos) - 3} más" if len(platos) > 3 else "")
        return f"No se puede eliminar el insumo {insumo.nombre}: está en la receta de {nombres}. Quítalo de esas recetas o desactívalo."
    return None

