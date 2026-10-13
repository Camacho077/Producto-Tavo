import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.permisos import tenant_con_permiso
from app.db.session import get_db
from app.modules.catalogo.models import Categoria, Producto
from app.modules.compras.models import Compra
from app.modules.inventario.models import Insumo, MovimientoInsumo
from app.modules.dashboard import avisos as reglas_de_aviso
from app.modules.dashboard.periodos import (
    DESFASE_NEGOCIO,
    PERIODOS,
    RANGOS_GRAFICA,
    RangoGrafica,
    Ventana,
    a_hora_negocio,
    a_utc,
    ahora_utc,
    avanzar_meses,
    inicio_de_bucket,
    proyectar,
    rango_de_grafica,
    variacion,
    ventana_de_periodo,
)
from app.modules.ordenes.models import Orden
from app.modules.caja.models import Venta, VentaItem

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Cuántos productos y categorías caben en la pantalla: la lista de más
# vendidos y la rejilla 2x2 de inventario del dashboard.
TOPE_MAS_VENDIDOS = 4
TOPE_CATEGORIAS = 4
# Meses de histórico sobre los que se estima la proyección del mes siguiente.
MESES_DE_PROYECCION = 6


# =====================================================================
# Consultas del panel. Todas son agregados: cuestan el mismo número de
# consultas con 1 fila que con 10.000 (lo exige
# tests/test_rendimiento_consultas.py).
# =====================================================================
def _sumar_en_ventana(db: Session, tenant_id, modelo, estado: str, v: Ventana) -> tuple[float, float]:
    """(total del tramo actual, total del tramo anterior) en UNA consulta.
    Los dos tramos caben en el mismo rango de fechas, así que se separan con
    sumas condicionales en vez de dos viajes a la base."""
    fila = (
        db.query(
            func.coalesce(
                func.sum(case((modelo.fecha >= v.desde, modelo.total), else_=0)),
                0,
            ).label("actual"),
            func.coalesce(
                func.sum(case((modelo.fecha < v.hasta_anterior, modelo.total), else_=0)),
                0,
            ).label("anterior"),
        )
        .filter(
            modelo.tenant_id == tenant_id,
            modelo.estado == estado,
            modelo.fecha >= v.desde_anterior,
            modelo.fecha < v.hasta,
        )
        .one()
    )
    return float(fila.actual or 0), float(fila.anterior or 0)


def _totales_del_periodo(db: Session, tenant_id, v: Ventana) -> dict:
    ventas, ventas_anterior = _sumar_en_ventana(db, tenant_id, Venta, "completada", v)
    compras, compras_anterior = _sumar_en_ventana(db, tenant_id, Compra, "confirmada", v)

    fila = (
        db.query(
            func.count(Venta.id).label("numero"),
            func.count(func.distinct(func.lower(Venta.cliente_nombre))).label("clientes"),
        )
        .filter(
            Venta.tenant_id == tenant_id,
            Venta.estado == "completada",
            Venta.fecha >= v.desde,
            Venta.fecha < v.hasta,
        )
        .one()
    )
    productos_vendidos = (
        db.query(func.coalesce(func.sum(VentaItem.cantidad), 0))
        .join(Venta, Venta.id == VentaItem.venta_id)
        .filter(
            Venta.tenant_id == tenant_id,
            Venta.estado == "completada",
            Venta.fecha >= v.desde,
            Venta.fecha < v.hasta,
        )
        .scalar()
    )

    return {
        "ventas": ventas,
        "ventas_anterior": ventas_anterior,
        "ventas_variacion": variacion(ventas, ventas_anterior),
        "compras": compras,
        "compras_anterior": compras_anterior,
        "compras_variacion": variacion(compras, compras_anterior),
        "saldo": ventas - compras,
        "numero_ventas": int(fila.numero or 0),
        "numero_clientes": int(fila.clientes or 0),
        "productos_vendidos": int(productos_vendidos or 0),
    }


def _mas_vendidos(db: Session, tenant_id, v: Ventana) -> list[dict]:
    """Los más vendidos del tramo actual, con su variación de monto frente al
    tramo anterior. Una sola consulta agrupada por producto."""
    monto = VentaItem.cantidad * VentaItem.precio_unitario
    es_actual = Venta.fecha >= v.desde
    es_anterior = Venta.fecha < v.hasta_anterior

    filas = (
        db.query(
            Producto.id.label("producto_id"),
            Producto.nombre.label("nombre"),
            Categoria.nombre.label("categoria"),
            func.coalesce(func.sum(case((es_actual, VentaItem.cantidad), else_=0)), 0).label("unidades"),
            func.coalesce(func.sum(case((es_actual, monto), else_=0)), 0).label("monto"),
            func.coalesce(func.sum(case((es_anterior, monto), else_=0)), 0).label("monto_anterior"),
        )
        .join(VentaItem, VentaItem.producto_id == Producto.id)
        .join(Venta, Venta.id == VentaItem.venta_id)
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .filter(
            Venta.tenant_id == tenant_id,
            Venta.estado == "completada",
            Venta.fecha >= v.desde_anterior,
            Venta.fecha < v.hasta,
        )
        .group_by(Producto.id, Producto.nombre, Categoria.nombre)
        .having(func.sum(case((es_actual, VentaItem.cantidad), else_=0)) > 0)
        .order_by(func.sum(case((es_actual, VentaItem.cantidad), else_=0)).desc())
        .limit(TOPE_MAS_VENDIDOS)
        .all()
    )

    return [
        {
            "producto_id": str(f.producto_id),
            "nombre": f.nombre,
            "categoria": f.categoria,
            "unidades": int(f.unidades),
            "monto": float(f.monto),
            "variacion": variacion(float(f.monto), float(f.monto_anterior)),
        }
        for f in filas
    ]


def _inventario(db: Session, tenant_id, v: Ventana) -> dict:
    """Inventario de INSUMOS (2026-10-12): cuántos hay activos, cuántos bajo
    su mínimo, el valor de la bodega a costo y la rejilla 2x2 por grupo de
    insumo (valor a costo y cuánto se CONSUMIÓ en el tramo, frente al
    anterior)."""
    valor = Insumo.existencia * Insumo.costo_unitario
    fila = (
        db.query(
            func.coalesce(func.sum(case((Insumo.activo.is_(True), 1), else_=0)), 0).label("activos"),
            func.coalesce(
                func.sum(
                    case(
                        (Insumo.activo.is_(True) & (Insumo.minimo > 0) & (Insumo.existencia <= Insumo.minimo), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("bajo_minimo"),
            func.coalesce(func.sum(case((Insumo.existencia > 0, valor), else_=0)), 0).label("valor"),
        )
        .filter(Insumo.tenant_id == tenant_id)
        .one()
    )
    ordenes_abiertas = (
        db.query(func.count(Orden.id)).filter(Orden.tenant_id == tenant_id, Orden.estado == "abierta").scalar()
    )

    grupo = func.coalesce(Insumo.grupo, "Sin grupo")
    por_grupo = (
        db.query(
            grupo.label("grupo"),
            func.coalesce(func.sum(case((Insumo.existencia > 0, valor), else_=0)), 0).label("valor"),
            func.count(Insumo.id).label("insumos"),
        )
        .filter(Insumo.tenant_id == tenant_id, Insumo.activo.is_(True))
        .group_by(grupo)
        .order_by(func.coalesce(func.sum(case((Insumo.existencia > 0, valor), else_=0)), 0).desc(), grupo)
        .limit(TOPE_CATEGORIAS)
        .all()
    )

    # Consumo (costo de lo que salió por ventas) de cada grupo en los dos tramos.
    salida = -MovimientoInsumo.valor
    consumo = (
        db.query(
            grupo.label("grupo"),
            func.coalesce(func.sum(case((MovimientoInsumo.created_at >= v.desde, salida), else_=0)), 0).label("actual"),
            func.coalesce(func.sum(case((MovimientoInsumo.created_at < v.hasta_anterior, salida), else_=0)), 0).label("anterior"),
        )
        .join(Insumo, Insumo.id == MovimientoInsumo.insumo_id)
        .filter(
            MovimientoInsumo.tenant_id == tenant_id,
            MovimientoInsumo.tipo == "venta",
            MovimientoInsumo.created_at >= v.desde_anterior,
            MovimientoInsumo.created_at < v.hasta,
        )
        .group_by(grupo)
        .all()
    )
    movimiento = {f.grupo: (float(f.actual), float(f.anterior)) for f in consumo}

    grupos = []
    for f in por_grupo:
        actual, anterior = movimiento.get(f.grupo, (0.0, 0.0))
        grupos.append(
            {
                "categoria_id": f.grupo,
                "nombre": f.grupo,
                "valor": float(f.valor),
                "unidades": int(f.insumos),
                "vendido": actual,
                "variacion": variacion(actual, anterior),
            }
        )

    return {
        "insumos_activos": int(fila.activos or 0),
        "bajo_minimo": int(fila.bajo_minimo or 0),
        "valor_inventario": float(fila.valor or 0),
        "ordenes_abiertas": int(ordenes_abiertas or 0),
        "categorias": grupos,
    }


def _proyeccion_mensual(db: Session, tenant_id, ahora: datetime) -> dict:
    """
    Regresión lineal sobre los últimos seis meses de ventas completadas. El
    mes en curso va incompleto, así que se extrapola al mes completo antes de
    entrar en la regresión: si no, la tendencia siempre parecería a la baja.

    Meses y día del mes son los de Bogotá (ver periodos.py): `meses` va en
    hora del negocio y solo el filtro de SQL se pasa a UTC.
    """
    ahora_negocio = a_hora_negocio(ahora)
    inicio = avanzar_meses(inicio_de_bucket(ahora_negocio, "month"), -(MESES_DE_PROYECCION - 1))
    mes_negocio = func.date_trunc("month", Venta.fecha + DESFASE_NEGOCIO)
    filas = (
        db.query(
            mes_negocio.label("mes"),
            func.coalesce(func.sum(Venta.total), 0).label("total"),
        )
        .filter(Venta.tenant_id == tenant_id, Venta.estado == "completada", Venta.fecha >= a_utc(inicio))
        .group_by(mes_negocio)
        .all()
    )
    por_mes = {f.mes: float(f.total) for f in filas}
    meses = [avanzar_meses(inicio, i) for i in range(MESES_DE_PROYECCION)]
    historial = [por_mes.get(m, 0.0) for m in meses]

    dias_del_mes = (avanzar_meses(meses[-1], 1) - meses[-1]).days
    if ahora_negocio.day < dias_del_mes and historial[-1] > 0:
        historial[-1] = historial[-1] * dias_del_mes / ahora_negocio.day

    return {
        "mes": avanzar_meses(meses[-1], 1).date().isoformat(),
        "ventas": round(proyectar(historial), 2),
        "base_meses": MESES_DE_PROYECCION,
        "historial": [
            {"mes": m.date().isoformat(), "ventas": round(v, 2)} for m, v in zip(meses, historial)
        ],
    }


@router.get("/panel")
def panel(
    periodo: str = Query(default="mes", pattern="^(hoy|mes|anio)$"),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("dashboard", "ver")),
):
    """
    Las cifras del dashboard para el periodo elegido con las píldoras
    Hoy / Mes / Año: totales con su variación, clientes y unidades vendidas,
    los más vendidos, el inventario (agregados y rejilla por categoría) y la
    proyección del mes siguiente.

    La SERIE de la gráfica no va aquí: vive en /dashboard/serie y tiene sus
    propios rangos, para que mover la gráfica no vuelva a pedir las cifras
    (ni al revés).
    """
    ahora = ahora_utc()
    v = ventana_de_periodo(periodo, ahora)

    return {
        "periodo": periodo,
        "ventana": {
            "desde": v.desde.isoformat(),
            "hasta": v.hasta.isoformat(),
            "desde_anterior": v.desde_anterior.isoformat(),
            "hasta_anterior": v.hasta_anterior.isoformat(),
            "dias": v.dias,
        },
        "totales": _totales_del_periodo(db, tenant_id, v),
        "mas_vendidos": _mas_vendidos(db, tenant_id, v),
        "inventario": _inventario(db, tenant_id, v),
        "proyeccion": _proyeccion_mensual(db, tenant_id, ahora),
    }


def _serie_de_rango(db: Session, tenant_id, r: RangoGrafica) -> list[dict]:
    """Ventas completadas por bucket, en el tramo actual y en el anterior.
    Una consulta: los dos tramos son contiguos.

    Se trunca en hora de Bogotá (fecha - 5 h) para que la hora/el día/el mes
    sean los del negocio, y la clave se devuelve a UTC naive para casarla con
    `r.inicios()`."""
    truncado = func.date_trunc(r.unidad_sql, Venta.fecha + DESFASE_NEGOCIO)
    filas = (
        db.query(truncado.label("bucket"), func.coalesce(func.sum(Venta.total), 0).label("total"))
        .filter(
            Venta.tenant_id == tenant_id,
            Venta.estado == "completada",
            Venta.fecha >= r.desde_anterior,
            Venta.fecha < r.hasta,
        )
        .group_by(truncado)
        .all()
    )
    por_bucket = {a_utc(f.bucket): float(f.total) for f in filas}

    return [
        {
            "inicio": actual.isoformat(),
            "inicio_anterior": anterior.isoformat(),
            "actual": por_bucket.get(actual, 0.0),
            "anterior": por_bucket.get(anterior, 0.0),
        }
        for actual, anterior in zip(r.inicios(), r.inicios_anteriores())
    ]


@router.get("/serie")
def serie(
    rango: str = Query(default="1m", pattern="^(1d|1s|1m|6m|1a)$"),
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("dashboard", "ver")),
):
    """
    La serie de la gráfica de rendimiento para uno de los cinco rangos:
    1D (últimas 24 horas), 1S (7 días), 1M (30 días), 6M (6 meses), 1A (12
    meses). El tramo termina en el bucket que contiene a este momento. Cada punto trae el valor del tramo actual y el del tramo anterior
    del mismo tamaño, más una proyección de un bucket hacia adelante
    (regresión lineal sobre la propia serie), etiquetada aparte para que la
    pantalla la dibuje punteada y nunca se confunda con un dato real.
    """
    r = rango_de_grafica(rango, ahora_utc())
    puntos = _serie_de_rango(db, tenant_id, r)

    return {
        "rango": rango,
        "unidad": r.unidad,
        "puntos": puntos,
        "proyeccion": {
            "inicio": r.siguiente_inicio().isoformat(),
            "valor": round(proyectar([p["actual"] for p in puntos]), 2),
        },
    }


@router.get("/avisos")
def avisos_del_negocio(
    db: Session = Depends(get_db),
    tenant_id: uuid.UUID = Depends(tenant_con_permiso("dashboard", "ver")),
):
    """
    Lo que merece atención hoy, calculado con los datos reales del tenant:
    stock agotado o bajo el mínimo, variación notable de ventas frente a la
    semana anterior, comandas demoradas en cocina y el más vendido de la
    semana. Las reglas viven en `avisos.py`.
    """
    return reglas_de_aviso.calcular(db, tenant_id)


# Se exportan para los tests y para que el frontend y el backend hablen del
# mismo conjunto de periodos y rangos.
__all__ = ["router", "PERIODOS", "RANGOS_GRAFICA"]
