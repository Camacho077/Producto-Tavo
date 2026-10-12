"""
Avisos del dashboard: lo que merece atención HOY, calculado con los datos
reales del negocio (nunca inventado ni aleatorio).

Cada regla es una función pequeña que devuelve 0 o 1 aviso, y `calcular`
las corre en orden de urgencia. Si ninguna tiene algo que decir, el panel
muestra que todo está en orden — nunca queda vacío.

Un aviso es un diccionario:
    clave   identificador estable de la regla (para tests y para el icono)
    nivel   critico | advertencia | informativo | positivo
    titulo  una línea corta
    texto   la explicación con los datos concretos
    enlace  {"recurso": ..., "id": ...} — el frontend lo convierte en ruta
            (ver frontend/src/modules/dashboard/avisos.js). `id` en None
            significa "lleva al listado".
"""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.mensajes import plural, unidades
from app.core.tiempo import ahora_utc
from app.modules.compras.models import Producto
from app.modules.ventas.models import Pedido, PedidoEvento, Venta, VentaItem

# Umbrales de las reglas. Viven aquí, con nombre, para que cambiarlos sea
# un solo sitio y los tests puedan apoyarse en ellos.
DIAS_SEMANA = 7
DIAS_PEDIDO_ESTANCADO = 3
VARIACION_NOTABLE_PCT = 20.0
MAX_NOMBRES_EN_TEXTO = 3
ESTADOS_PEDIDO_ABIERTO = ("pendiente", "en_proceso", "listo")


def _aviso(clave: str, nivel: str, titulo: str, texto: str, recurso: str, id_: uuid.UUID | None = None) -> dict:
    return {
        "clave": clave,
        "nivel": nivel,
        "titulo": titulo,
        "texto": texto,
        "enlace": {"recurso": recurso, "id": str(id_) if id_ else None},
    }


def _enumerar(nombres: list[str]) -> str:
    """["A", "B", "C", "D"] → "A, B, C y 1 más" (el texto del aviso es breve)."""
    visibles = nombres[:MAX_NOMBRES_EN_TEXTO]
    restantes = len(nombres) - len(visibles)
    if restantes > 0:
        return f"{', '.join(visibles)} y {restantes} más"
    if len(visibles) == 1:
        return visibles[0]
    return f"{', '.join(visibles[:-1])} y {visibles[-1]}"


def _enlace_a_productos(productos: list[Producto]) -> tuple[str, uuid.UUID | None]:
    """Si es uno solo, el aviso lleva a su ficha; si son varios, al listado."""
    return ("producto", productos[0].id) if len(productos) == 1 else ("productos", None)


# =====================================================================
# Reglas
# =====================================================================
def productos_agotados(db: Session, tenant_id: uuid.UUID) -> dict | None:
    """Productos activos que se quedaron en cero: no se pueden vender."""
    productos = (
        db.query(Producto)
        .filter(Producto.tenant_id == tenant_id, Producto.activo.is_(True), Producto.stock <= 0)
        .order_by(Producto.nombre)
        .all()
    )
    if not productos:
        return None
    recurso, id_ = _enlace_a_productos(productos)
    return _aviso(
        "stock_agotado",
        "critico",
        f"{plural(len(productos), 'producto agotado', 'productos agotados')}",
        f"{_enumerar([p.nombre for p in productos])} en 0 unidades: no se pueden vender hasta que entre una compra.",
        recurso,
        id_,
    )


def productos_bajo_minimo(db: Session, tenant_id: uuid.UUID) -> dict | None:
    """Con existencias, pero por debajo del mínimo configurado."""
    productos = (
        db.query(Producto)
        .filter(
            Producto.tenant_id == tenant_id,
            Producto.activo.is_(True),
            Producto.stock > 0,
            Producto.stock_minimo > 0,
            Producto.stock <= Producto.stock_minimo,
        )
        .order_by(Producto.stock)
        .all()
    )
    if not productos:
        return None
    recurso, id_ = _enlace_a_productos(productos)
    detalle = ", ".join(f"{p.nombre} ({unidades(p.stock)}, mínimo {p.stock_minimo})" for p in productos[:MAX_NOMBRES_EN_TEXTO])
    restantes = len(productos) - min(len(productos), MAX_NOMBRES_EN_TEXTO)
    if restantes:
        detalle += f" y {restantes} más"
    return _aviso(
        "stock_bajo",
        "advertencia",
        f"{plural(len(productos), 'producto bajo el mínimo', 'productos bajo el mínimo')}",
        f"{detalle}. Conviene reponer antes de que se agoten.",
        recurso,
        id_,
    )


def _ventas_entre(db: Session, tenant_id: uuid.UUID, desde: datetime, hasta: datetime) -> float:
    total = (
        db.query(func.coalesce(func.sum(Venta.total), 0))
        .filter(
            Venta.tenant_id == tenant_id,
            Venta.estado == "completada",
            Venta.fecha >= desde,
            Venta.fecha < hasta,
        )
        .scalar()
    )
    return float(total or 0)


def variacion_de_ventas(db: Session, tenant_id: uuid.UUID, ahora: datetime) -> dict | None:
    """Compara los últimos 7 días con los 7 anteriores. Solo avisa si el
    cambio es notable (±20 %) y si el periodo anterior tuvo ventas: sin
    base de comparación un porcentaje no significa nada."""
    inicio_actual = ahora - timedelta(days=DIAS_SEMANA)
    inicio_anterior = inicio_actual - timedelta(days=DIAS_SEMANA)
    actual = _ventas_entre(db, tenant_id, inicio_actual, ahora)
    anterior = _ventas_entre(db, tenant_id, inicio_anterior, inicio_actual)
    if anterior <= 0:
        return None

    variacion = (actual - anterior) / anterior * 100
    if abs(variacion) < VARIACION_NOTABLE_PCT:
        return None

    cayo = variacion < 0
    return _aviso(
        "ventas_caida" if cayo else "ventas_subida",
        "advertencia" if cayo else "positivo",
        f"Las ventas {'cayeron' if cayo else 'subieron'} {abs(variacion):.0f}% esta semana",
        f"Últimos {DIAS_SEMANA} días: ${actual:,.0f} frente a ${anterior:,.0f} de los {DIAS_SEMANA} anteriores.".replace(",", "."),
        "ventas",
    )


def pedidos_estancados(db: Session, tenant_id: uuid.UUID, ahora: datetime) -> dict | None:
    """Pedidos abiertos cuyo último movimiento ya tiene varios días."""
    ultimo_evento = (
        db.query(PedidoEvento.pedido_id, func.max(PedidoEvento.created_at).label("ultimo"))
        .filter(PedidoEvento.tenant_id == tenant_id)
        .group_by(PedidoEvento.pedido_id)
        .subquery()
    )
    corte = ahora - timedelta(days=DIAS_PEDIDO_ESTANCADO)
    filas = (
        db.query(Pedido, ultimo_evento.c.ultimo)
        .outerjoin(ultimo_evento, ultimo_evento.c.pedido_id == Pedido.id)
        .filter(
            Pedido.tenant_id == tenant_id,
            Pedido.estado.in_(ESTADOS_PEDIDO_ABIERTO),
            func.coalesce(ultimo_evento.c.ultimo, Pedido.created_at) <= corte,
        )
        .order_by(func.coalesce(ultimo_evento.c.ultimo, Pedido.created_at))
        .all()
    )
    if not filas:
        return None

    pedidos = [p for p, _ in filas]
    dias = (ahora - (filas[0][1] or pedidos[0].created_at)).days
    codigos = [f"PED-{p.numero:06d}" for p in pedidos]
    recurso, id_ = ("pedido", pedidos[0].id) if len(pedidos) == 1 else ("pedidos", None)
    return _aviso(
        "pedidos_estancados",
        "advertencia",
        f"{plural(len(pedidos), 'pedido sin avanzar', 'pedidos sin avanzar')}",
        f"{_enumerar(codigos)} sin cambios desde hace {plural(dias, 'día', 'días')} o más.",
        recurso,
        id_,
    )


def mas_vendido_de_la_semana(db: Session, tenant_id: uuid.UUID, ahora: datetime) -> dict | None:
    fila = (
        db.query(Producto.id, Producto.nombre, func.sum(VentaItem.cantidad).label("unidades"))
        .join(VentaItem, VentaItem.producto_id == Producto.id)
        .join(Venta, Venta.id == VentaItem.venta_id)
        .filter(
            Venta.tenant_id == tenant_id,
            Venta.estado == "completada",
            Venta.fecha >= ahora - timedelta(days=DIAS_SEMANA),
        )
        .group_by(Producto.id, Producto.nombre)
        .order_by(func.sum(VentaItem.cantidad).desc())
        .first()
    )
    if fila is None:
        return None
    producto_id, nombre, vendidas = fila
    return _aviso(
        "mas_vendido",
        "informativo",
        f"Lo más vendido de la semana: {nombre}",
        f"{unidades(int(vendidas))} en los últimos {DIAS_SEMANA} días. Revisa que no se quede corto de stock.",
        "producto",
        producto_id,
    )


# =====================================================================
# Panel completo
# =====================================================================
def calcular(db: Session, tenant_id: uuid.UUID, ahora: datetime | None = None) -> dict:
    """Corre todas las reglas en orden de urgencia y arma el panel."""
    ahora = ahora or ahora_utc()
    candidatos = [
        productos_agotados(db, tenant_id),
        productos_bajo_minimo(db, tenant_id),
        variacion_de_ventas(db, tenant_id, ahora),
        pedidos_estancados(db, tenant_id, ahora),
        mas_vendido_de_la_semana(db, tenant_id, ahora),
    ]
    avisos = [a for a in candidatos if a is not None]
    return {
        "avisos": avisos,
        "todo_en_orden": not any(a["nivel"] in ("critico", "advertencia") for a in avisos),
    }
