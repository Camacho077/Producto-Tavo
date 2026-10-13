"""
SUGERENCIAS DE NEGOCIO (módulo IA, add-on de pago) — 2026-10-01; adaptado al
restaurante el 2026-10-12 (inventario de INSUMOS y costo por RECETA).

Todo se calcula AQUÍ, dentro del sistema, con estadística sobre los datos
reales del tenant (ventas completadas, compras confirmadas, consumo de
insumos y recetas). No se llama a ningún modelo ni servicio externo: no sale
ningún dato del sistema (ver docs/ia/README.md). Tampoco se usa ningún dato
personal de clientes: solo cantidades, montos, fechas, platos e insumos.

Reglas de oro:
- Cada sugerencia dice POR QUÉ se generó (`por_que`) y con QUÉ datos
  (`datos`: pares etiqueta/valor con las cifras usadas).
- Si no hay datos suficientes, se dice (`sin_datos` de la sección), nunca se
  inventa una cifra. Cada regla tiene su propio umbral mínimo.
- Costos y márgenes solo para quien puede verlos (`costos.ver`, la misma
  regla que el costeo de la carta): a los demás la sección les explica por
  qué no la ven.
- Pocas consultas agregadas: cuesta lo mismo con 10 ventas que con 10.000.

Secciones:
    alertas       insumos que se acabarían pronto, caídas de venta
    reponer       lista de compras sugerida (insumos y cuánto)
    ganadores     platos que más crecen
    patrones      días de la semana y franjas horarias fuertes
    rotacion      insumos quietos (capital inmovilizado)
    precios       platos con costo alto según su receta        (costos)
    proveedores   proveedor más barato por insumo                (costos)
"""
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.mensajes import plural, unidades
from app.db.models import Tenant
from app.modules.ajustes.schemas import configuracion_de
from app.modules.catalogo import recetas
from app.modules.catalogo.models import Producto
from app.modules.catalogo.services import opciones_carga_producto
from app.modules.compras.models import Compra, CompraItem, Proveedor
from app.modules.dashboard.periodos import DESFASE_NEGOCIO
from app.modules.inventario.models import Insumo, MovimientoInsumo
from app.modules.inventario.unidades import convertir, legible
from app.modules.caja.models import Venta, VentaItem

# ---------------------------------------------------------------------------
# Umbrales con nombre: cambiarlos es un solo sitio y los tests se apoyan aquí.
# ---------------------------------------------------------------------------
VENTANA_DIAS = 30  # ritmo de venta y de consumo actual
HISTORIA_DIAS = 90  # base mínima para hablar de "el negocio"
COSTOS_DIAS = 180  # compras que cuentan para comparar proveedores
MIN_VENTAS_BASE = 5  # ventas completadas en 90 días para cualquier análisis
MIN_DIAS_BASE = 3  # días distintos con ventas en 90 días

MIN_DIAS_RITMO = 2  # días distintos con consumo del insumo en 30 días
DIAS_QUIEBRE = 7  # cobertura por debajo de esto: quiebre previsible
DIAS_REPONER = 21  # cobertura por debajo de esto: conviene comprar
DIAS_A_CUBRIR = 30  # la compra sugerida cubre este horizonte

MIN_UNIDADES_CAIDA = 5  # unidades del tramo anterior para medir una caída
CAIDA_PRODUCTO_PCT = 40.0
CAIDA_TOTAL_PCT = 20.0
CRECIMIENTO_GANADOR_PCT = 20.0
MIN_UNIDADES_GANADOR = 5
MAX_GANADORES = 5

DIAS_INSUMO_NUEVO = 30  # un insumo más nuevo no puede estar "quieto"
ROTACION_DIAS = 60
ROTACION_MINIMA = 0.25  # gastar menos de 1/4 de la existencia en 60 días es lento

# Restaurante: el indicador es el PORCENTAJE DE COSTO del plato (costo de la
# receta sobre el precio sin impuesto). Una carta sana anda cerca del 30-35 %.
COSTO_OBJETIVO_PCT = 35.0
COSTO_ALTO_PCT = 45.0
AHORRO_MINIMO_PCT = 5.0

MIN_VENTAS_PATRON = 10
MIN_SEMANAS_PATRON = 4
SEMANAS_PATRON = 8

DIAS_SEMANA = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]  # dow de Postgres
DIAS_PLURAL = ["domingos", "lunes", "martes", "miércoles", "jueves", "viernes", "sábados"]

PRIVACIDAD = (
    "Calculado dentro del sistema con estadística sobre tus ventas, compras, "
    "recetas e inventario. No se envía ningún dato a servicios externos ni se "
    "usan datos personales de tus clientes."
)


# ---------------------------------------------------------------------------
# Formato (español de Colombia, como los avisos del dashboard)
# ---------------------------------------------------------------------------
def _pesos(valor) -> str:
    return "$" + f"{float(valor):,.0f}".replace(",", ".")


def _pct(valor: float) -> str:
    return f"{valor:.0f} %"


def _num(valor: float, decimales: int = 1) -> str:
    texto = f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return texto.rstrip("0").rstrip(",") if decimales else texto


def _fecha(d: datetime) -> str:
    meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
    local = d + DESFASE_NEGOCIO
    return f"{local.day} {meses[local.month - 1]}"


def _sugerencia(tipo, nivel, titulo, por_que, datos, accion, recurso=None, id_=None, clave=None):
    return {
        "clave": f"{tipo}:{clave or id_ or titulo}",
        "tipo": tipo,
        "nivel": nivel,  # critico | advertencia | oportunidad | informativo
        "titulo": titulo,
        "por_que": por_que,
        "datos": [{"etiqueta": e, "valor": v} for e, v in datos],
        "accion": accion,
        "enlace": {"recurso": recurso, "id": str(id_) if id_ else None} if recurso else None,
    }


def _seccion(clave, titulo, descripcion, sugerencias=None, sin_datos=None, requiere_costos=False):
    return {
        "clave": clave,
        "titulo": titulo,
        "descripcion": descripcion,
        "sugerencias": sugerencias or [],
        # Por qué no hay sugerencias cuando no las hay: datos insuficientes,
        # nada que reportar, o el rol no ve costos. Nunca una lista vacía muda.
        "sin_datos": sin_datos,
        "requiere_costos": requiere_costos,
    }


# ---------------------------------------------------------------------------
# Datos: pocas consultas agregadas, todas filtradas por tenant
# ---------------------------------------------------------------------------
def _ventas_por_producto(db, tenant_id, ahora):
    """Unidades y monto por producto en el tramo actual (30 d) y el anterior
    (30 d antes), días distintos con venta y última venta. Una consulta."""
    inicio_act = ahora - timedelta(days=VENTANA_DIAS)
    inicio_ant = ahora - timedelta(days=2 * VENTANA_DIAS)
    inicio_rot = ahora - timedelta(days=ROTACION_DIAS)
    en_act = Venta.fecha >= inicio_act
    en_ant = (Venta.fecha >= inicio_ant) & (Venta.fecha < inicio_act)
    monto = VentaItem.cantidad * VentaItem.precio_unitario
    dia = func.date_trunc("day", Venta.fecha + DESFASE_NEGOCIO)
    filas = (
        db.query(
            VentaItem.producto_id,
            func.coalesce(func.sum(case((en_act, VentaItem.cantidad), else_=0)), 0).label("u_act"),
            func.coalesce(func.sum(case((en_ant, VentaItem.cantidad), else_=0)), 0).label("u_ant"),
            func.coalesce(func.sum(case((en_act, monto), else_=0)), 0).label("m_act"),
            func.coalesce(func.sum(case((en_ant, monto), else_=0)), 0).label("m_ant"),
            func.coalesce(func.sum(case((Venta.fecha >= inicio_rot, VentaItem.cantidad), else_=0)), 0).label("u_rot"),
            func.count(func.distinct(case((en_act, dia)))).label("dias_act"),
            func.max(Venta.fecha).label("ultima"),
        )
        .join(Venta, Venta.id == VentaItem.venta_id)
        .filter(Venta.tenant_id == tenant_id, VentaItem.tenant_id == tenant_id, Venta.estado == "completada")
        .group_by(VentaItem.producto_id)
        .all()
    )
    return {f.producto_id: f for f in filas}


def _base(db, tenant_id, ahora):
    inicio = ahora - timedelta(days=HISTORIA_DIAS)
    dia = func.date_trunc("day", Venta.fecha + DESFASE_NEGOCIO)
    ventas, dias = (
        db.query(func.count(Venta.id), func.count(func.distinct(dia)))
        .filter(Venta.tenant_id == tenant_id, Venta.estado == "completada", Venta.fecha >= inicio, Venta.fecha <= ahora)
        .one()
    )
    return int(ventas), int(dias)


def _consumo_por_insumo(db, tenant_id, ahora):
    """Lo que salió de cada insumo por ventas (en su unidad): últimos 30 días,
    días distintos con salida, últimos 60 días y la última salida."""
    inicio_act = ahora - timedelta(days=VENTANA_DIAS)
    inicio_rot = ahora - timedelta(days=ROTACION_DIAS)
    salida = -MovimientoInsumo.cantidad
    en_act = MovimientoInsumo.created_at >= inicio_act
    dia = func.date_trunc("day", MovimientoInsumo.created_at + DESFASE_NEGOCIO)
    filas = (
        db.query(
            MovimientoInsumo.insumo_id,
            func.coalesce(func.sum(case((en_act, salida), else_=0)), 0).label("c_act"),
            func.coalesce(func.sum(case((MovimientoInsumo.created_at >= inicio_rot, salida), else_=0)), 0).label("c_rot"),
            func.count(func.distinct(case((en_act, dia)))).label("dias_act"),
            func.max(MovimientoInsumo.created_at).label("ultima"),
        )
        .filter(MovimientoInsumo.tenant_id == tenant_id, MovimientoInsumo.tipo == "venta")
        .group_by(MovimientoInsumo.insumo_id)
        .all()
    )
    return {f.insumo_id: f for f in filas}


def _compras_por_insumo(db, tenant_id, ahora, insumos):
    """Precio promedio por UNIDAD DEL INSUMO, por proveedor, en 180 días (la
    compra puede venir en kg aunque el insumo se lleve en g)."""
    inicio = ahora - timedelta(days=COSTOS_DIAS)
    filas = (
        db.query(
            CompraItem.insumo_id,
            Compra.proveedor_id,
            CompraItem.unidad,
            func.sum(CompraItem.cantidad).label("cantidad"),
            func.sum(CompraItem.cantidad * CompraItem.precio_unitario).label("monto"),
            func.count(func.distinct(Compra.id)).label("compras"),
            func.max(Compra.fecha).label("ultima"),
        )
        .join(Compra, Compra.id == CompraItem.compra_id)
        .filter(Compra.tenant_id == tenant_id, CompraItem.tenant_id == tenant_id, Compra.estado == "confirmada", Compra.fecha >= inicio)
        .group_by(CompraItem.insumo_id, Compra.proveedor_id, CompraItem.unidad)
        .all()
    )
    por_insumo: dict = defaultdict(dict)
    for f in filas:
        insumo = insumos.get(f.insumo_id)
        if insumo is None:
            continue
        acumulado = por_insumo[f.insumo_id].setdefault(
            f.proveedor_id,
            {"proveedor_id": f.proveedor_id, "cantidad": Decimal(0), "monto": Decimal(0), "compras": 0, "ultima": f.ultima},
        )
        acumulado["cantidad"] += convertir(Decimal(f.cantidad), f.unidad, insumo.unidad)
        acumulado["monto"] += Decimal(f.monto)
        acumulado["compras"] += int(f.compras)
        acumulado["ultima"] = max(acumulado["ultima"], f.ultima)
    return por_insumo


def _ritmo_insumo(c) -> float | None:
    """Consumo por día en los últimos 30, o None sin base suficiente."""
    if c is None or float(c.c_act) <= 0 or int(c.dias_act) < MIN_DIAS_RITMO:
        return None
    return float(c.c_act) / VENTANA_DIAS


def _cantidad(valor: float, unidad: str) -> str:
    return legible(Decimal(str(round(valor, 3))), unidad)


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------
def _insumos_a_comprar(insumos, consumo, ahora):
    """Quiebres previsibles (alerta) y lista de compras sugerida."""
    alertas, reponer = [], []
    sin_ritmo = 0
    for i in insumos:
        c = consumo.get(i.id)
        ritmo = _ritmo_insumo(c)
        existencia, minimo = float(i.existencia), float(i.minimo)
        if ritmo is None:
            if minimo > 0 and existencia <= minimo:
                faltan = minimo * 2 - existencia
                reponer.append(
                    _sugerencia(
                        "reponer", "advertencia", f"Comprar {i.nombre}",
                        f"Quedan {_cantidad(existencia, i.unidad)} y su mínimo es {_cantidad(minimo, i.unidad)}. "
                        "Sin consumo suficiente en 30 días para estimar un ritmo, la cantidad sugerida deja la "
                        "existencia en el doble del mínimo.",
                        [("Existencia", _cantidad(existencia, i.unidad)), ("Mínimo", _cantidad(minimo, i.unidad))],
                        f"Comprar al menos {_cantidad(faltan, i.unidad)}.", "insumo", i.id,
                    )
                )
            elif c is not None:
                sin_ritmo += 1
            continue
        cobertura = max(existencia, 0.0) / ritmo
        datos = [
            ("Consumo en 30 días", f"{_cantidad(float(c.c_act), i.unidad)} en {plural(int(c.dias_act), 'día', 'días')}"),
            ("Ritmo", f"{_cantidad(ritmo, i.unidad)} por día"),
            ("Existencia", _cantidad(existencia, i.unidad)),
            ("Cobertura", "agotado" if existencia <= 0 else f"{_num(cobertura, 0)} días"),
        ]
        sugerida = max(0.0, ritmo * DIAS_A_CUBRIR + minimo - existencia)
        if cobertura < DIAS_QUIEBRE:
            titulo = (
                f"{i.nombre} ya se acabó y se sigue gastando"
                if existencia <= 0
                else f"{i.nombre} se acabaría hacia el {_fecha(ahora + timedelta(days=cobertura))}"
            )
            alertas.append(
                _sugerencia(
                    "quiebre", "critico", titulo,
                    f"Al ritmo de los últimos 30 días ({_cantidad(ritmo, i.unidad)} por día) quedan "
                    f"{_cantidad(existencia, i.unidad)}: alcanza para unos {_num(cobertura, 0)} días, menos que los "
                    f"{DIAS_QUIEBRE} que dan margen para comprar.",
                    datos, f"Comprar {_cantidad(sugerida, i.unidad)} para cubrir {DIAS_A_CUBRIR} días.", "insumo", i.id,
                )
            )
        if cobertura < DIAS_REPONER or (minimo > 0 and existencia <= minimo):
            motivo = (
                f"está en {_cantidad(existencia, i.unidad)}, en o por debajo de su mínimo ({_cantidad(minimo, i.unidad)})"
                if minimo > 0 and existencia <= minimo
                else f"alcanza para unos {_num(cobertura, 0)} días, menos de {DIAS_REPONER}"
            )
            reponer.append(
                _sugerencia(
                    "reponer", "critico" if cobertura < DIAS_QUIEBRE else "advertencia", f"Comprar {i.nombre}",
                    f"Se gastan {_cantidad(ritmo, i.unidad)} por día y su existencia {motivo}. La cantidad sugerida "
                    f"cubre {DIAS_A_CUBRIR} días de consumo más el mínimo configurado.",
                    datos + [("Sugerido", _cantidad(sugerida, i.unidad))],
                    f"Comprar {_cantidad(sugerida, i.unidad)}.", "insumo", i.id,
                )
            )
    orden = {"critico": 0, "advertencia": 1}
    reponer.sort(key=lambda s: orden.get(s["nivel"], 2))
    return alertas, reponer, sin_ritmo


def _caidas(productos, ventas):
    alertas = []
    tot_act = sum(float(v.m_act) for v in ventas.values())
    tot_ant = sum(float(v.m_ant) for v in ventas.values())
    if tot_ant > 0:
        cambio = (tot_act - tot_ant) / tot_ant * 100
        if cambio <= -CAIDA_TOTAL_PCT:
            alertas.append(
                _sugerencia(
                    "caida_total", "advertencia", f"Las ventas cayeron {_pct(abs(cambio))} en 30 días",
                    f"Los últimos {VENTANA_DIAS} días suman {_pesos(tot_act)} frente a {_pesos(tot_ant)} de los "
                    f"{VENTANA_DIAS} anteriores (tramos del mismo largo).",
                    [("Últimos 30 días", _pesos(tot_act)), ("30 días anteriores", _pesos(tot_ant)), ("Cambio", f"▼ {_pct(abs(cambio))}")],
                    "Revisa qué platos explican la caída (abajo) y si faltaron insumos.", "ventas", clave="total",
                )
            )
    nombres = {p.id: p for p in productos}
    for pid, v in ventas.items():
        u_ant, u_act = int(v.u_ant), int(v.u_act)
        if u_ant < MIN_UNIDADES_CAIDA or pid not in nombres:
            continue
        cambio = (u_act - u_ant) / u_ant * 100
        if cambio <= -CAIDA_PRODUCTO_PCT:
            p = nombres[pid]
            agotado = " Además está marcado como agotado: parte de la caída puede ser falta de insumos." if p.agotado_fecha else ""
            alertas.append(
                _sugerencia(
                    "caida_producto", "advertencia", f"{p.nombre} vende {_pct(abs(cambio))} menos",
                    f"Pasó de {unidades(u_ant)} a {unidades(u_act)} entre los dos últimos tramos de {VENTANA_DIAS} días.{agotado}",
                    [("30 días anteriores", unidades(u_ant)), ("Últimos 30 días", unidades(u_act)), ("Cambio", f"▼ {_pct(abs(cambio))}")],
                    "Revisa su precio, cómo se ofrece y si le faltaron insumos.", "producto", pid,
                )
            )
    return alertas


def _ganadores(productos, ventas):
    nombres = {p.id: p for p in productos}
    candidatos = []
    for pid, v in ventas.items():
        u_act, u_ant = int(v.u_act), int(v.u_ant)
        if pid not in nombres or u_act < MIN_UNIDADES_GANADOR:
            continue
        if u_ant == 0:
            crecimiento = None  # nuevo en el ranking: no se inventa un porcentaje
        else:
            crecimiento = (u_act - u_ant) / u_ant * 100
            if crecimiento < CRECIMIENTO_GANADOR_PCT:
                continue
        candidatos.append((float(v.m_act), pid, v, crecimiento))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    total = sum(float(v.m_act) for v in ventas.values()) or 1
    res = []
    for monto, pid, v, crecimiento in candidatos[:MAX_GANADORES]:
        p = nombres[pid]
        variacion = "sin ventas en el tramo anterior" if crecimiento is None else f"▲ {_pct(crecimiento)}"
        res.append(
            _sugerencia(
                "ganador", "oportunidad", f"{p.nombre} está ganando",
                (f"Vendió {unidades(int(v.u_act))} en 30 días frente a {unidades(int(v.u_ant))} en los 30 anteriores"
                 if crecimiento is not None else f"Vendió {unidades(int(v.u_act))} en 30 días y no había vendido nada en los 30 anteriores")
                + f", y aporta el {_pct(monto / total * 100)} de lo vendido en el tramo.",
                [("Unidades 30 días", unidades(int(v.u_act))), ("Monto 30 días", _pesos(monto)), ("Variación", variacion)],
                "Asegura sus insumos y dale visibilidad: es lo que más está jalando.", "producto", pid,
            )
        )
    return res


def _insumos_quietos(insumos, consumo, ver_costos, ahora):
    """Insumos con existencia que casi no se gastan: capital quieto y riesgo
    de vencimiento."""
    res = []
    for i in insumos:
        existencia = float(i.existencia)
        if existencia <= max(0.0, float(i.minimo)) or (ahora - i.created_at).days < DIAS_INSUMO_NUEVO:
            continue
        c = consumo.get(i.id)
        gastado = float(c.c_rot) if c else 0.0
        if gastado / existencia >= ROTACION_MINIMA:
            continue
        datos = [("Gastado en 60 días", _cantidad(gastado, i.unidad)), ("Existencia", _cantidad(existencia, i.unidad))]
        if ver_costos:
            datos.append(("Capital quieto (a costo)", _pesos(Decimal(i.existencia) * Decimal(i.costo_unitario))))
        ultima = f"la última salida fue el {_fecha(c.ultima)}" if c and c.ultima else "no ha salido nunca por ventas"
        res.append(
            _sugerencia(
                "rotacion", "advertencia" if gastado == 0 else "informativo", f"{i.nombre} casi no se gasta",
                f"Se gastaron {_cantidad(gastado, i.unidad)} en {ROTACION_DIAS} días y quedan {_cantidad(existencia, i.unidad)} ({ultima}).",
                datos,
                "Úsalo en el plato del día o en una promoción, revisa su vencimiento y pausa sus compras.", "insumo", i.id,
            )
        )
    res.sort(key=lambda s: 0 if s["nivel"] == "advertencia" else 1)
    return res


def _ingrediente_mas_caro(p) -> str | None:
    """"Queso (48 % del costo)": el insumo que más pesa en la receta."""
    if p.tipo != "plato" or not p.receta:
        return None
    lineas = [(recetas.costo_linea(l), l) for l in p.receta]
    total = sum((c for c, _ in lineas), Decimal(0))
    if total <= 0:
        return None
    costo, linea = max(lineas, key=lambda x: x[0])
    return f"{linea.insumo.nombre} ({_pct(float(costo / total * 100))} del costo)"


def _precios(productos, ventas, config):
    """Platos cuyo costo por receta se come demasiado del precio."""
    res, sin_receta = [], 0
    for p in productos:
        costeo = recetas.costeo(p, config)
        if costeo["costo"] is None or costeo["porcentaje_costo"] is None:
            sin_receta += 1
            continue
        pct = float(costeo["porcentaje_costo"])
        if pct < COSTO_ALTO_PCT:
            continue
        neto = costeo["precio_neto"]
        # Si la carta incluye el impuesto, el precio sugerido también lo incluye.
        factor = Decimal(p.precio) / neto if neto else Decimal(1)
        sugerido = Decimal(costeo["costo"]) / Decimal(COSTO_OBJETIVO_PCT / 100) * factor
        v = ventas.get(p.id)
        demanda = f" Vendió {unidades(int(v.u_act))} en 30 días: el ajuste pesa en caja." if v and int(v.u_act) else ""
        caro = _ingrediente_mas_caro(p)
        if pct >= 100:
            nivel, titulo = "critico", f"{p.nombre} se vende por debajo de su costo"
        else:
            nivel, titulo = "oportunidad", f"{p.nombre} tiene un costo del {_pct(pct)}"
        res.append(
            _sugerencia(
                "precio", nivel, titulo,
                f"Su receta cuesta {_pesos(costeo['costo'])} y se vende a {_pesos(p.precio)} ({_pesos(neto)} sin impuesto): "
                f"el costo es el {_pct(pct)} del precio, por encima del {_pct(COSTO_ALTO_PCT)}."
                + (f" Lo que más pesa es {caro}." if caro else "") + demanda,
                [("Costo por receta", _pesos(costeo["costo"])), ("Precio", _pesos(p.precio)), ("% de costo", _pct(pct)),
                 (f"Precio para un costo del {_pct(COSTO_OBJETIVO_PCT)}", _pesos(sugerido))],
                f"Evalúa subir el precio hacia {_pesos(sugerido)}, ajustar la porción o negociar el insumo.", "producto", p.id,
            )
        )
    res.sort(key=lambda s: 0 if s["nivel"] == "critico" else 1)
    return res, sin_receta


def _proveedores(db, tenant_id, insumos, por_insumo, consumo):
    comparables = {iid: list(provs.values()) for iid, provs in por_insumo.items() if len(provs) >= 2 and iid in insumos}
    if not comparables:
        return [], 0
    ids = {f["proveedor_id"] for filas in comparables.values() for f in filas}
    provs = {p.id: p for p in db.query(Proveedor).filter(Proveedor.tenant_id == tenant_id, Proveedor.id.in_(ids)).all()}
    res = []
    for iid, filas in comparables.items():
        costo = lambda f: f["monto"] / f["cantidad"] if f["cantidad"] else Decimal(0)  # noqa: E731
        mejor = min(filas, key=costo)
        ultima = max(filas, key=lambda f: f["ultima"])  # a quién se le compró de último
        c_mejor, c_ultima = costo(mejor), costo(ultima)
        if ultima["proveedor_id"] == mejor["proveedor_id"] or c_ultima <= 0:
            continue
        ahorro = float((c_ultima - c_mejor) / c_ultima * 100)
        if ahorro < AHORRO_MINIMO_PCT:
            continue
        i = insumos[iid]
        c = consumo.get(iid)
        mensual = Decimal(str(float(c.c_act))) if c else Decimal(0)
        impacto = (
            [("Ahorro en un mes de consumo", f"{_pesos((c_ultima - c_mejor) * mensual)} ({legible(mensual, i.unidad)})")]
            if mensual else []
        )
        n_mejor, n_ultima = provs[mejor["proveedor_id"]].nombre, provs[ultima["proveedor_id"]].nombre
        res.append(
            _sugerencia(
                "proveedor", "oportunidad", f"{i.nombre}: {n_mejor} te sale {_pct(ahorro)} más barato",
                f"En {COSTOS_DIAS} días le compraste a {n_ultima} a {_pesos(c_ultima)} por {i.unidad} en promedio "
                f"({plural(int(ultima['compras']), 'compra', 'compras')}, la última el {_fecha(ultima['ultima'])}) y a {n_mejor} a "
                f"{_pesos(c_mejor)} por {i.unidad} ({plural(int(mejor['compras']), 'compra', 'compras')}).",
                [(n_mejor, f"{_pesos(c_mejor)} / {i.unidad}"), (n_ultima, f"{_pesos(c_ultima)} / {i.unidad}"), ("Diferencia", f"▼ {_pct(ahorro)}")]
                + impacto,
                f"Cotiza la próxima compra con {n_mejor}.", "proveedor", mejor["proveedor_id"], clave=iid,
            )
        )
    return res, len(comparables)


def _patrones(db, tenant_id, ahora):
    inicio = ahora - timedelta(weeks=SEMANAS_PATRON)
    local = Venta.fecha + DESFASE_NEGOCIO
    base = db.query(Venta).filter(Venta.tenant_id == tenant_id, Venta.estado == "completada", Venta.fecha >= inicio, Venta.fecha <= ahora)
    n_ventas, semanas = base.with_entities(func.count(Venta.id), func.count(func.distinct(func.date_trunc("week", local)))).one()
    if n_ventas < MIN_VENTAS_PATRON or semanas < MIN_SEMANAS_PATRON:
        return [], (
            f"Para detectar patrones hacen falta al menos {MIN_VENTAS_PATRON} ventas repartidas en "
            f"{MIN_SEMANAS_PATRON} semanas distintas (de las últimas {SEMANAS_PATRON}); hay "
            f"{plural(int(n_ventas), 'venta', 'ventas')} en {plural(int(semanas), 'semana', 'semanas')}."
        )
    res = []
    por_dia = dict(base.with_entities(func.extract("dow", local), func.sum(Venta.total)).group_by(func.extract("dow", local)).all())
    total = float(sum(por_dia.values())) or 1
    mejor = max(por_dia, key=lambda d: por_dia[d])
    peor = min(range(7), key=lambda d: float(por_dia.get(d, 0)))
    parte = float(por_dia[mejor]) / total * 100
    if parte >= 100 / 7 * 1.3:  # al menos 30 % por encima de un reparto parejo
        res.append(
            _sugerencia(
                "patron_dia", "informativo", f"Los {DIAS_PLURAL[int(mejor)]} son tu día fuerte",
                f"En las últimas {SEMANAS_PATRON} semanas los {DIAS_PLURAL[int(mejor)]} concentran el {_pct(parte)} de lo "
                f"vendido (un reparto parejo sería {_pct(100 / 7)}); el día más flojo es el {DIAS_SEMANA[peor]}.",
                [(d.capitalize(), _pesos(por_dia.get(i, 0))) for i, d in enumerate(DIAS_SEMANA)],
                f"Prepara más y refuerza el personal antes de cada {DIAS_SEMANA[int(mejor)]}; prueba una promoción el {DIAS_SEMANA[peor]}.",
                clave="dia",
            )
        )
    hora = func.extract("hour", local)
    por_hora = dict(base.with_entities(hora, func.count(Venta.id)).group_by(hora).all())
    bloques = {h: sum(int(por_hora.get(x, 0)) for x in range(h, h + 3)) for h in range(0, 22)}
    inicio_bloque = max(bloques, key=lambda h: bloques[h])
    parte_h = bloques[inicio_bloque] / int(n_ventas) * 100
    if parte_h >= 40:
        res.append(
            _sugerencia(
                "patron_hora", "informativo", f"La franja de {inicio_bloque}:00 a {inicio_bloque + 3}:00 es la de más ventas",
                f"El {_pct(parte_h)} de las ventas de las últimas {SEMANAS_PATRON} semanas se registró en esas tres horas "
                "(hora de Colombia).",
                [("Ventas en la franja", str(bloques[inicio_bloque])), ("Ventas totales", str(int(n_ventas)))],
                "Ten la preparación y los turnos listos antes de esa franja.", clave="hora",
            )
        )
    return res, (None if res else "No hay un día ni una franja que se destaque: las ventas están repartidas de forma pareja.")


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
def calcular(db: Session, tenant_id: uuid.UUID, ahora: datetime, ver_costos: bool) -> dict:
    ventas_90, dias_90 = _base(db, tenant_id, ahora)
    suficiente = ventas_90 >= MIN_VENTAS_BASE and dias_90 >= MIN_DIAS_BASE
    base = {
        "ventas": ventas_90,
        "dias_con_venta": dias_90,
        "dias": HISTORIA_DIAS,
        "suficiente": suficiente,
        "mensaje": None if suficiente else (
            f"Con {plural(ventas_90, 'venta completada', 'ventas completadas')} en {plural(dias_90, 'día', 'días')} "
            f"de los últimos {HISTORIA_DIAS}, todavía no hay base para estimar ritmos ni tendencias. Hacen falta al "
            f"menos {MIN_VENTAS_BASE} ventas en {MIN_DIAS_BASE} días distintos. Las sugerencias que no dependen de "
            "la historia de ventas (costo de los platos y proveedores) sí se muestran."
        ),
    }

    productos = (
        db.query(Producto)
        .options(*opciones_carga_producto())
        .filter(Producto.tenant_id == tenant_id, Producto.activo.is_(True))
        .order_by(Producto.nombre)
        .all()
    )
    insumos_lista = db.query(Insumo).filter(Insumo.tenant_id == tenant_id, Insumo.activo.is_(True)).order_by(Insumo.nombre).all()
    insumos = {i.id: i for i in insumos_lista}
    ventas = _ventas_por_producto(db, tenant_id, ahora)
    consumo = _consumo_por_insumo(db, tenant_id, ahora)
    insuficiente = "Sin base suficiente de ventas (ver arriba)."

    if suficiente:
        quiebres, reponer, sin_ritmo = _insumos_a_comprar(insumos_lista, consumo, ahora)
        alertas = quiebres + _caidas(productos, ventas)
        ganadores = _ganadores(productos, ventas)
        patrones, nota_patrones = _patrones(db, tenant_id, ahora)
        rotacion = _insumos_quietos(insumos_lista, consumo, ver_costos, ahora)
        nota_reponer = None if reponer else (
            f"Ningún insumo se acabaría en los próximos {DIAS_REPONER} días al ritmo actual."
            + (f" {plural(sin_ritmo, 'insumo no tiene', 'insumos no tienen')} consumo suficiente en 30 días para estimar su ritmo." if sin_ritmo else "")
        )
        secciones = [
            _seccion("alertas", "Alertas inteligentes", "Insumos que se acabarían pronto y caídas de venta.", alertas,
                     None if alertas else "Ningún insumo se acaba pronto y no hay caídas notables de venta."),
            _seccion("reponer", "Lista de compras sugerida", f"Insumos que alcanzan para menos de {DIAS_REPONER} días al consumo de los últimos 30.", reponer, nota_reponer),
            _seccion("ganadores", "Platos ganadores", f"Los que más venden y crecen al menos {_pct(CRECIMIENTO_GANADOR_PCT)}.", ganadores,
                     None if ganadores else "Ningún plato crece de forma notable frente a los 30 días anteriores."),
            _seccion("patrones", "Patrones de venta", f"Días y horas fuertes en las últimas {SEMANAS_PATRON} semanas.", patrones, nota_patrones),
            _seccion("rotacion", "Insumos quietos", f"Existencias que casi no se gastan (menos de un cuarto en {ROTACION_DIAS} días).", rotacion,
                     None if rotacion else "Todos los insumos con más de 30 días se gastan a un ritmo razonable."),
        ]
    else:
        secciones = [
            _seccion(clave, titulo, desc, sin_datos=insuficiente)
            for clave, titulo, desc in (
                ("alertas", "Alertas inteligentes", "Insumos que se acabarían pronto y caídas de venta."),
                ("reponer", "Lista de compras sugerida", "Según el consumo de los insumos."),
                ("ganadores", "Platos ganadores", "Los que más venden y crecen."),
                ("patrones", "Patrones de venta", "Días y horas fuertes."),
                ("rotacion", "Insumos quietos", "Existencias que casi no se gastan."),
            )
        ]

    sin_permiso = "Tu rol no ve costos ni márgenes (requiere el permiso de ver costos), así que esta sección no se muestra."
    if ver_costos:
        config = configuracion_de(db.get(Tenant, tenant_id))
        precios, sin_receta = _precios(productos, ventas, config)
        proveedores, comparables = _proveedores(db, tenant_id, insumos, _compras_por_insumo(db, tenant_id, ahora, insumos), consumo)
        if precios:
            nota_precios = None
        elif len(productos) > sin_receta:
            nota_precios = f"Todos los platos con receta cuestan menos del {_pct(COSTO_ALTO_PCT)} de su precio." + (
                f" {plural(sin_receta, 'plato no tiene', 'platos no tienen')} receta completa para costearlo." if sin_receta else ""
            )
        else:
            nota_precios = "Ningún plato tiene receta todavía: arma las recetas para conocer su costo."
        nota_prov = None if proveedores else (
            f"Ningún insumo se ha comprado a más de un proveedor en {COSTOS_DIAS} días: no hay con qué comparar."
            if not comparables else "Ya le compras cada insumo al proveedor más barato que tienes registrado."
        )
        secciones.append(_seccion("precios", "Platos con costo alto", f"Platos cuyo costo por receta pasa del {_pct(COSTO_ALTO_PCT)} del precio.", precios, nota_precios, True))
        secciones.append(_seccion("proveedores", "Proveedores con mejores condiciones", f"Precio promedio por insumo y proveedor en {COSTOS_DIAS} días.", proveedores, nota_prov, True))
    else:
        secciones.append(_seccion("precios", "Platos con costo alto", "Según el costo de cada receta.", sin_datos=sin_permiso, requiere_costos=True))
        secciones.append(_seccion("proveedores", "Proveedores con mejores condiciones", "Precio por insumo y proveedor.", sin_datos=sin_permiso, requiere_costos=True))

    return {
        "generado_en": ahora.isoformat(),
        "motor": "Reglas estadísticas locales",
        "privacidad": PRIVACIDAD,
        "base": base,
        "secciones": secciones,
    }
