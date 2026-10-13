"""
CONSULTAS DE REPORTES (fase 8, 2026-10-12) — las tres preguntas del dueño:
¿cuánto entró?, ¿cuánto costó? y ¿cuánto gané?

Todas reciben un tramo [desde, hasta) en UTC naive (los límites ya vienen
calculados en hora de Colombia) y son agregados: cuestan las mismas consultas
con 10 ventas que con 10.000. Las comparten el dashboard y la pantalla de
Reportes.

Definiciones (las mismas en todo el producto):
- Vendido (`total`): lo que pagaron los clientes por lo consumido, con el
  impuesto al consumo; sin propinas.
- Ingresos (`ingresos`): lo vendido SIN el impuesto al consumo (ese 8 % es de
  la DIAN, no del restaurante). Las propinas tampoco son ingreso.
- Costo de lo vendido: el costo por receta de cada plato el día que se pidió.
- Utilidad bruta = ingresos − costo. Utilidad real = bruta − gastos.
"""
from datetime import date, datetime, timedelta

from sqlalchemy import Integer, case, cast, func
from sqlalchemy.orm import Session

from app.core.validaciones import ZONA_NEGOCIO
from app.modules.caja.models import Venta, VentaItem, VentaPago
from app.modules.catalogo.models import Categoria, Producto
from app.modules.gastos.models import CATEGORIAS, Gasto
from app.modules.inventario.models import Insumo, MovimientoInsumo
from app.modules.ordenes.models import Orden

DESFASE = ZONA_NEGOCIO.utcoffset(None)  # -5 h
MAX_PARTES = 6  # una dona nunca muestra más: el resto va en "Otros"


def _num(valor) -> float:
    return round(float(valor or 0), 2)


def dias_negocio(desde: datetime, hasta: datetime) -> tuple[date, date]:
    """[primer día, último día] de Colombia que cubre el tramo UTC."""
    return (desde + DESFASE).date(), (hasta + DESFASE - timedelta(microseconds=1)).date()


def _ventas(db: Session, tenant_id, desde: datetime, hasta: datetime):
    return (
        Venta.tenant_id == tenant_id,
        Venta.estado == "completada",
        Venta.fecha >= desde,
        Venta.fecha < hasta,
    )


def resumen(db: Session, tenant_id, desde: datetime, hasta: datetime) -> dict:
    """Las cifras del tramo en tres consultas (ventas, costo y gastos)."""
    v = (
        db.query(
            func.coalesce(func.sum(Venta.total), 0).label("total"),
            func.coalesce(func.sum(Venta.subtotal), 0).label("ingresos"),
            func.coalesce(func.sum(Venta.impuesto), 0).label("impuesto"),
            func.coalesce(func.sum(Venta.propina), 0).label("propinas"),
            func.count(Venta.id).label("cobros"),
            func.count(func.distinct(Venta.orden_id)).label("ordenes"),
        )
        .filter(*_ventas(db, tenant_id, desde, hasta))
        .one()
    )
    costo, platos = (
        db.query(
            func.coalesce(func.sum(VentaItem.cantidad * func.coalesce(VentaItem.costo_unitario, 0)), 0),
            func.coalesce(func.sum(VentaItem.cantidad), 0),
        )
        .join(Venta, Venta.id == VentaItem.venta_id)
        .filter(*_ventas(db, tenant_id, desde, hasta))
        .one()
    )
    primero, ultimo = dias_negocio(desde, hasta)
    gastos = (
        db.query(func.coalesce(func.sum(Gasto.valor), 0))
        .filter(Gasto.tenant_id == tenant_id, Gasto.fecha >= primero, Gasto.fecha <= ultimo)
        .scalar()
    )
    ingresos, costo, gastos = _num(v.ingresos), _num(costo), _num(gastos)
    bruta = round(ingresos - costo, 2)
    return {
        "total": _num(v.total),
        "ingresos": ingresos,
        "impuesto": _num(v.impuesto),
        "propinas": _num(v.propinas),
        "costo": costo,
        "utilidad_bruta": bruta,
        "gastos": gastos,
        "utilidad_real": round(bruta - gastos, 2),
        "margen_bruto_pct": round(bruta / ingresos * 100, 1) if ingresos else None,
        "costo_pct": round(costo / ingresos * 100, 1) if ingresos else None,
        "cobros": int(v.cobros or 0),
        "ordenes": int(v.ordenes or 0),
        "platos": int(platos or 0),
        "ticket_promedio": round(_num(v.total) / int(v.ordenes), 2) if v.ordenes else 0.0,
    }


def platos(db: Session, tenant_id, desde: datetime, hasta: datetime) -> list[dict]:
    """Por plato: unidades, vendido, ingreso neto (sin impuesto, prorrateado
    por la venta), costo, margen y % de costo. Ordenados de más a menos
    vendido."""
    monto = VentaItem.cantidad * VentaItem.precio_unitario
    neto = monto * Venta.subtotal / func.nullif(Venta.total, 0)
    costo = VentaItem.cantidad * func.coalesce(VentaItem.costo_unitario, 0)
    filas = (
        db.query(
            Producto.id, Producto.nombre, Categoria.nombre.label("categoria"),
            func.sum(VentaItem.cantidad).label("unidades"), func.sum(monto).label("vendido"),
            func.coalesce(func.sum(neto), 0).label("ingresos"), func.sum(costo).label("costo"),
        )
        .join(VentaItem, VentaItem.producto_id == Producto.id)
        .join(Venta, Venta.id == VentaItem.venta_id)
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .filter(*_ventas(db, tenant_id, desde, hasta))
        .group_by(Producto.id, Producto.nombre, Categoria.nombre)
        .order_by(func.sum(VentaItem.cantidad).desc(), Producto.nombre)
        .all()
    )
    salida = []
    for f in filas:
        ingresos, c = _num(f.ingresos), _num(f.costo)
        salida.append({
            "producto_id": str(f.id), "nombre": f.nombre, "categoria": f.categoria, "unidades": int(f.unidades),
            "vendido": _num(f.vendido), "ingresos": ingresos, "costo": c, "margen": round(ingresos - c, 2),
            "costo_pct": round(c / ingresos * 100, 1) if ingresos else None,
        })
    return salida


def _por(db: Session, tenant_id, desde, hasta, clave, etiqueta=lambda x: x) -> list[dict]:
    filas = (
        db.query(clave.label("clave"), func.count(func.distinct(Venta.orden_id)).label("ordenes"), func.sum(Venta.total).label("total"))
        .join(Orden, Orden.id == Venta.orden_id)
        .filter(*_ventas(db, tenant_id, desde, hasta))
        .group_by(clave)
        .order_by(func.sum(Venta.total).desc())
        .all()
    )
    return [
        {"clave": f.clave, "nombre": etiqueta(f.clave), "ordenes": int(f.ordenes), "total": _num(f.total),
         "ticket": round(_num(f.total) / int(f.ordenes), 2) if f.ordenes else 0.0}
        for f in filas
    ]


NOMBRE_TIPO = {"local": "En el local", "llevar": "Para llevar", "domicilio": "Domicilio"}
NOMBRE_MEDIO = {"efectivo": "Efectivo", "transferencia": "Transferencia", "nequi": "Nequi", "daviplata": "Daviplata", "tarjeta": "Tarjeta"}
DIAS = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")


def por_tipo(db, tenant_id, desde, hasta) -> list[dict]:
    return _por(db, tenant_id, desde, hasta, Orden.tipo, lambda t: NOMBRE_TIPO.get(t, t))


def por_mesero(db, tenant_id, desde, hasta) -> list[dict]:
    return _por(db, tenant_id, desde, hasta, func.coalesce(Orden.mesero_nombre, "Sin registrar"))


def por_hora(db, tenant_id, desde, hasta) -> list[dict]:
    """Ventas por hora del día de Colombia (0 a 23), con las horas sin venta."""
    hora = cast(func.extract("hour", Venta.fecha + DESFASE), Integer)
    datos = {int(f.h): f for f in db.query(hora.label("h"), func.count(Venta.id).label("cobros"), func.sum(Venta.total).label("total"))
             .filter(*_ventas(db, tenant_id, desde, hasta)).group_by(hora).all()}
    return [{"hora": h, "cobros": int(datos[h].cobros) if h in datos else 0, "total": _num(datos[h].total) if h in datos else 0.0} for h in range(24)]


def por_dia_semana(db, tenant_id, desde, hasta) -> list[dict]:
    """Ventas por día de la semana de Colombia (lunes primero)."""
    isodow = cast(func.extract("isodow", Venta.fecha + DESFASE), Integer)
    datos = {int(f.d): f for f in db.query(isodow.label("d"), func.count(func.distinct(Venta.orden_id)).label("ordenes"), func.sum(Venta.total).label("total"))
             .filter(*_ventas(db, tenant_id, desde, hasta)).group_by(isodow).all()}
    return [{"dia": DIAS[d - 1], "ordenes": int(datos[d].ordenes) if d in datos else 0, "total": _num(datos[d].total) if d in datos else 0.0} for d in range(1, 8)]


def por_medio(db, tenant_id, desde, hasta) -> list[dict]:
    filas = (
        db.query(VentaPago.medio, func.sum(VentaPago.monto).label("total"))
        .join(Venta, Venta.id == VentaPago.venta_id)
        .filter(*_ventas(db, tenant_id, desde, hasta))
        .group_by(VentaPago.medio)
        .order_by(func.sum(VentaPago.monto).desc())
        .all()
    )
    return [{"clave": f.medio, "nombre": NOMBRE_MEDIO.get(f.medio, f.medio), "total": _num(f.total)} for f in filas]


def por_categoria(db, tenant_id, desde, hasta) -> list[dict]:
    nombre = func.coalesce(Categoria.nombre, "Sin categoría")
    filas = (
        db.query(nombre.label("nombre"), func.sum(VentaItem.cantidad * VentaItem.precio_unitario).label("total"))
        .join(Venta, Venta.id == VentaItem.venta_id)
        .join(Producto, Producto.id == VentaItem.producto_id)
        .outerjoin(Categoria, Categoria.id == Producto.categoria_id)
        .filter(*_ventas(db, tenant_id, desde, hasta))
        .group_by(nombre)
        .order_by(func.sum(VentaItem.cantidad * VentaItem.precio_unitario).desc())
        .all()
    )
    return [{"clave": f.nombre, "nombre": f.nombre, "total": _num(f.total)} for f in filas]


def insumos(db, tenant_id, desde, hasta) -> list[dict]:
    """Consumo por ventas (neto de devoluciones) y mermas, con su costo."""
    consumo_tipos = ("venta", "anulacion_orden")
    es_consumo = MovimientoInsumo.tipo.in_(consumo_tipos)
    es_merma = MovimientoInsumo.tipo == "merma"
    filas = (
        db.query(
            Insumo.id, Insumo.nombre, Insumo.unidad,
            func.coalesce(func.sum(case((es_consumo, -MovimientoInsumo.cantidad), else_=0)), 0).label("consumo"),
            func.coalesce(func.sum(case((es_consumo, -MovimientoInsumo.valor), else_=0)), 0).label("costo_consumo"),
            func.coalesce(func.sum(case((es_merma, -MovimientoInsumo.cantidad), else_=0)), 0).label("merma"),
            func.coalesce(func.sum(case((es_merma, -MovimientoInsumo.valor), else_=0)), 0).label("costo_merma"),
        )
        .join(MovimientoInsumo, MovimientoInsumo.insumo_id == Insumo.id)
        .filter(
            Insumo.tenant_id == tenant_id,
            MovimientoInsumo.tipo.in_((*consumo_tipos, "merma")),
            MovimientoInsumo.created_at >= desde,
            MovimientoInsumo.created_at < hasta,
        )
        .group_by(Insumo.id, Insumo.nombre, Insumo.unidad)
        .order_by(func.sum(case((es_consumo, -MovimientoInsumo.valor), else_=0)).desc())
        .all()
    )
    return [
        {
            "insumo_id": str(f.id), "nombre": f.nombre, "unidad": f.unidad,
            "consumo": float(f.consumo), "costo_consumo": _num(f.costo_consumo),
            "merma": float(f.merma), "costo_merma": _num(f.costo_merma),
            "merma_pct": round(float(f.merma) / (float(f.consumo) + float(f.merma)) * 100, 1) if (float(f.consumo) + float(f.merma)) > 0 else 0.0,
        }
        for f in filas
    ]


def gastos(db, tenant_id, desde, hasta) -> list[dict]:
    primero, ultimo = dias_negocio(desde, hasta)
    filas = (
        db.query(Gasto.categoria, func.sum(Gasto.valor).label("total"), func.count(Gasto.id).label("registros"))
        .filter(Gasto.tenant_id == tenant_id, Gasto.fecha >= primero, Gasto.fecha <= ultimo)
        .group_by(Gasto.categoria)
        .order_by(func.sum(Gasto.valor).desc())
        .all()
    )
    return [{"clave": f.categoria, "nombre": CATEGORIAS.get(f.categoria, f.categoria), "total": _num(f.total), "registros": int(f.registros)} for f in filas]


def partes(lista: list[dict], valor: str = "total") -> list[dict]:
    """Para una dona: como mucho MAX_PARTES; lo demás se suma en "Otros"."""
    ordenada = sorted(lista, key=lambda x: x[valor], reverse=True)
    if len(ordenada) <= MAX_PARTES:
        return [{"nombre": x["nombre"], "valor": x[valor]} for x in ordenada]
    visibles = ordenada[: MAX_PARTES - 1]
    resto = sum(x[valor] for x in ordenada[MAX_PARTES - 1 :])
    return [{"nombre": x["nombre"], "valor": x[valor]} for x in visibles] + [{"nombre": "Otros", "valor": round(resto, 2)}]


def participacion(db, tenant_id, desde, hasta) -> dict:
    return {
        "categorias": partes(por_categoria(db, tenant_id, desde, hasta)),
        "medios": partes(por_medio(db, tenant_id, desde, hasta)),
        "tipos": partes(por_tipo(db, tenant_id, desde, hasta)),
    }

