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
from app.modules.catalogo.models import Producto, RecetaItem
from app.modules.inventario.models import Insumo
from app.modules.inventario.unidades import legible
from app.db.models import Tenant
from app.modules.ajustes.schemas import configuracion_de
from app.modules.ordenes.models import Comanda, Orden
from app.modules.caja.models import Venta, VentaItem

# Umbrales de las reglas. Viven aquí, con nombre, para que cambiarlos sea
# un solo sitio y los tests puedan apoyarse en ellos.
DIAS_SEMANA = 7
VARIACION_NOTABLE_PCT = 20.0
MAX_NOMBRES_EN_TEXTO = 3


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


def _enlace_a_insumos(insumos: list[Insumo]) -> tuple[str, uuid.UUID | None]:
    """Si es uno solo, el aviso lleva a su ficha; si son varios, al listado."""
    return ("insumo", insumos[0].id) if len(insumos) == 1 else ("insumos", None)


# =====================================================================
# Reglas
# =====================================================================
def insumos_agotados(db: Session, tenant_id: uuid.UUID) -> dict | None:
    """Insumos activos USADOS EN ALGUNA RECETA que se quedaron en cero (o en
    negativo, si el restaurante vende sin existencias): los platos que los
    llevan no se pueden preparar."""
    insumos = (
        db.query(Insumo)
        .filter(
            Insumo.tenant_id == tenant_id,
            Insumo.activo.is_(True),
            Insumo.existencia <= 0,
            Insumo.id.in_(db.query(RecetaItem.insumo_id).filter(RecetaItem.tenant_id == tenant_id)),
        )
        .order_by(Insumo.nombre)
        .all()
    )
    if not insumos:
        return None
    recurso, id_ = _enlace_a_insumos(insumos)
    return _aviso(
        "stock_agotado",
        "critico",
        f"{plural(len(insumos), 'insumo agotado', 'insumos agotados')}",
        f"{_enumerar([i.nombre for i in insumos])} sin existencias: los platos que los llevan no se pueden preparar hasta que entre una compra.",
        recurso,
        id_,
    )


def insumos_bajo_minimo(db: Session, tenant_id: uuid.UUID) -> dict | None:
    """Con existencias, pero en o por debajo del mínimo configurado."""
    insumos = (
        db.query(Insumo)
        .filter(
            Insumo.tenant_id == tenant_id,
            Insumo.activo.is_(True),
            Insumo.existencia > 0,
            Insumo.minimo > 0,
            Insumo.existencia <= Insumo.minimo,
        )
        .order_by(Insumo.nombre)
        .all()
    )
    if not insumos:
        return None
    recurso, id_ = _enlace_a_insumos(insumos)
    detalle = ", ".join(
        f"{i.nombre} ({legible(i.existencia, i.unidad)}, mínimo {legible(i.minimo, i.unidad)})" for i in insumos[:MAX_NOMBRES_EN_TEXTO]
    )
    restantes = len(insumos) - min(len(insumos), MAX_NOMBRES_EN_TEXTO)
    if restantes:
        detalle += f" y {restantes} más"
    return _aviso(
        "stock_bajo",
        "advertencia",
        f"{plural(len(insumos), 'insumo bajo el mínimo', 'insumos bajo el mínimo')}",
        f"{detalle}. Conviene comprar antes de que se agoten.",
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


def comandas_demoradas(db: Session, tenant_id: uuid.UUID, ahora: datetime) -> dict | None:
    """Comandas en cocina (entrantes o en preparación) que ya pasaron el
    tiempo de alerta configurado en Ajustes."""
    minutos = configuracion_de(db.get(Tenant, tenant_id)).alerta_cocina_minutos
    filas = (
        db.query(Orden.numero, Comanda.created_at)
        .join(Orden, Orden.id == Comanda.orden_id)
        .filter(
            Comanda.tenant_id == tenant_id,
            Comanda.estado.in_(("entrante", "en_preparacion")),
            Orden.estado != "anulada",
            Comanda.created_at <= ahora - timedelta(minutes=minutos),
        )
        .order_by(Comanda.created_at)
        .all()
    )
    if not filas:
        return None
    espera = int((ahora - filas[0][1]).total_seconds() // 60)
    numeros = list(dict.fromkeys(f"#{n}" for n, _ in filas))
    return _aviso(
        "comandas_demoradas",
        "advertencia",
        f"{plural(len(filas), 'comanda demorada', 'comandas demoradas')} en cocina",
        f"Órdenes {_enumerar(numeros)}: la más antigua lleva {espera} min (la alerta es a los {minutos} min).",
        "ordenes",
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
        f"{unidades(int(vendidas))} en los últimos {DIAS_SEMANA} días. Revisa que no te quedes corto de sus insumos.",
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
        insumos_agotados(db, tenant_id),
        insumos_bajo_minimo(db, tenant_id),
        variacion_de_ventas(db, tenant_id, ahora),
        comandas_demoradas(db, tenant_id, ahora),
        mas_vendido_de_la_semana(db, tenant_id, ahora),
    ]
    avisos = [a for a in candidatos if a is not None]
    return {
        "avisos": avisos,
        "todo_en_orden": not any(a["nivel"] in ("critico", "advertencia") for a in avisos),
    }
