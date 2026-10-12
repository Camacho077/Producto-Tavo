"""
SUGERENCIAS DE NEGOCIO (módulo IA, add-on de pago) — 2026-10-01.

Todo se calcula AQUÍ, dentro del sistema, con estadística sobre los datos
reales del tenant (ventas completadas, compras confirmadas, stock y precios).
No se llama a ningún modelo ni servicio externo: no sale ningún dato del
sistema (ver docs/ia/README.md). Tampoco se usa ningún dato personal de
clientes: solo cantidades, montos, fechas y productos.

Reglas de oro:
- Cada sugerencia dice POR QUÉ se generó (`por_que`) y con QUÉ datos
  (`datos`: pares etiqueta/valor con las cifras usadas).
- Si no hay datos suficientes, se dice (`sin_datos` de la sección), nunca se
  inventa una cifra. Cada regla tiene su propio umbral mínimo.
- Costos y márgenes solo para quien puede verlos (`compras.ver`, la misma
  regla que el costo del producto): a los demás la sección les explica por
  qué no la ven.
- Una sola pasada de consultas agregadas: cuesta lo mismo con 10 ventas que
  con 10.000.

Secciones:
    alertas       quiebres de stock previsibles, caídas de venta
    reponer       productos a reponer y cuánto
    ganadores     productos que más crecen
    patrones      días de la semana y franjas horarias fuertes
    rotacion      productos con baja rotación (capital quieto)
    precios       oportunidades de precio según margen        (costos)
    proveedores   proveedor con mejores condiciones por producto (costos)
"""
import math
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.mensajes import plural, unidades
from app.modules.compras.models import Compra, CompraItem, Producto, Proveedor
from app.modules.dashboard.periodos import DESFASE_NEGOCIO
from app.modules.ventas.models import Venta, VentaItem

# ---------------------------------------------------------------------------
# Umbrales con nombre: cambiarlos es un solo sitio y los tests se apoyan aquí.
# ---------------------------------------------------------------------------
VENTANA_DIAS = 30  # ritmo de venta actual
HISTORIA_DIAS = 90  # base mínima para hablar de "el negocio"
COSTOS_DIAS = 180  # compras que cuentan para costo promedio y proveedores
MIN_VENTAS_BASE = 5  # ventas completadas en 90 días para cualquier análisis
MIN_DIAS_BASE = 3  # días distintos con ventas en 90 días

MIN_UNIDADES_RITMO = 3  # unidades en 30 días para estimar un ritmo
MIN_DIAS_RITMO = 2  # días distintos con venta del producto en 30 días
DIAS_QUIEBRE = 7  # cobertura por debajo de esto: quiebre previsible
DIAS_REPONER = 21  # cobertura por debajo de esto: conviene reponer
DIAS_A_CUBRIR = 30  # la reposición sugerida cubre este horizonte

MIN_UNIDADES_CAIDA = 5  # unidades del tramo anterior para medir una caída
CAIDA_PRODUCTO_PCT = 40.0
CAIDA_TOTAL_PCT = 20.0
CRECIMIENTO_GANADOR_PCT = 20.0
MIN_UNIDADES_GANADOR = 5
MAX_GANADORES = 5

DIAS_PRODUCTO_NUEVO = 30  # un producto más nuevo no puede tener "baja rotación"
ROTACION_DIAS = 60
ROTACION_MINIMA = 0.25  # vender menos de 1/4 del stock en 60 días es lento

MARGEN_OBJETIVO = 0.25
MARGEN_BAJO = 0.15
AHORRO_MINIMO_PCT = 5.0

MIN_VENTAS_PATRON = 10
MIN_SEMANAS_PATRON = 4
SEMANAS_PATRON = 8

DIAS_SEMANA = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"]  # dow de Postgres
DIAS_PLURAL = ["domingos", "lunes", "martes", "miércoles", "jueves", "viernes", "sábados"]

PRIVACIDAD = (
    "Calculado dentro del sistema con estadística sobre tus ventas, compras y "
    "stock. No se envía ningún dato a servicios externos ni se usan datos "
    "personales de tus clientes."
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


def _por_dia(ritmo: float) -> str:
    """1 → "1 unidad por día"; 1.33 → "1,3 unidades por día"."""
    texto = _num(ritmo)
    return f"{texto} {'unidad' if texto == '1' else 'unidades'} por día"


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


def _costos(db, tenant_id, ahora):
    """Costo promedio por producto y por (producto, proveedor) en 180 días."""
    inicio = ahora - timedelta(days=COSTOS_DIAS)
    filas = (
        db.query(
            CompraItem.producto_id,
            Compra.proveedor_id,
            func.sum(CompraItem.cantidad).label("unidades"),
            func.sum(CompraItem.cantidad * CompraItem.precio_unitario).label("monto"),
            func.count(func.distinct(Compra.id)).label("compras"),
            func.max(Compra.fecha).label("ultima"),
        )
        .join(Compra, Compra.id == CompraItem.compra_id)
        .filter(Compra.tenant_id == tenant_id, CompraItem.tenant_id == tenant_id, Compra.estado == "confirmada", Compra.fecha >= inicio)
        .group_by(CompraItem.producto_id, Compra.proveedor_id)
        .all()
    )
    por_producto: dict = defaultdict(lambda: {"unidades": 0, "monto": Decimal(0), "compras": 0})
    por_proveedor: dict = defaultdict(list)
    for f in filas:
        p = por_producto[f.producto_id]
        p["unidades"] += int(f.unidades)
        p["monto"] += Decimal(f.monto)
        p["compras"] += int(f.compras)
        por_proveedor[f.producto_id].append(f)
    return por_producto, por_proveedor


def _ritmo(v) -> float | None:
    """Unidades por día en los últimos 30, o None si no hay base suficiente."""
    if v is None or int(v.u_act) < MIN_UNIDADES_RITMO or int(v.dias_act) < MIN_DIAS_RITMO:
        return None
    return int(v.u_act) / VENTANA_DIAS


# ---------------------------------------------------------------------------
# Reglas
# ---------------------------------------------------------------------------
def _stock(productos, ventas, ahora):
    """Quiebres previsibles (alerta) y reposición sugerida."""
    alertas, reponer = [], []
    sin_ritmo = 0
    for p in productos:
        v = ventas.get(p.id)
        ritmo = _ritmo(v)
        if ritmo is None:
            if p.stock <= p.stock_minimo and p.stock_minimo > 0:
                # Sin historia de venta, la única base es el mínimo configurado.
                faltan = p.stock_minimo - p.stock + 1
                reponer.append(
                    _sugerencia(
                        "reponer", "advertencia", f"Reponer {p.nombre}",
                        f"Tiene {unidades(p.stock)} y su mínimo configurado es {p.stock_minimo}. "
                        "No hay ventas suficientes en 30 días para estimar un ritmo, así que la cantidad "
                        "sugerida solo devuelve el stock por encima del mínimo.",
                        [("Stock actual", unidades(p.stock)), ("Mínimo configurado", unidades(p.stock_minimo)),
                         ("Vendidas en 30 días", unidades(int(v.u_act) if v else 0))],
                        f"Comprar al menos {unidades(faltan)}.", "producto", p.id,
                    )
                )
            elif p.stock > 0 or v is not None:
                sin_ritmo += 1
            continue
        cobertura = p.stock / ritmo if ritmo else math.inf
        datos = [
            ("Vendidas en 30 días", f"{unidades(int(v.u_act))} en {plural(int(v.dias_act), 'día', 'días')}"),
            ("Ritmo", _por_dia(ritmo)),
            ("Stock actual", unidades(p.stock)),
            ("Cobertura", "agotado" if p.stock <= 0 else f"{_num(cobertura, 0)} días"),
        ]
        sugerida = max(0, math.ceil(ritmo * DIAS_A_CUBRIR + p.stock_minimo - p.stock))
        if cobertura < DIAS_QUIEBRE:
            fin = ahora + timedelta(days=cobertura)
            titulo = (
                f"{p.nombre} ya está agotado y se sigue pidiendo"
                if p.stock <= 0
                else f"{p.nombre} se agotaría hacia el {_fecha(fin)}"
            )
            alertas.append(
                _sugerencia(
                    "quiebre", "critico", titulo,
                    f"Al ritmo de los últimos 30 días ({_por_dia(ritmo)}) el stock de "
                    f"{unidades(p.stock)} alcanza para unos {_num(cobertura, 0)} días, menos que los {DIAS_QUIEBRE} "
                    "que da margen para reponer.",
                    datos, f"Reponer {unidades(sugerida)} para cubrir {DIAS_A_CUBRIR} días.", "producto", p.id,
                )
            )
        if cobertura < DIAS_REPONER or p.stock <= p.stock_minimo:
            motivo = (
                f"está en {unidades(p.stock)}, en o por debajo de su mínimo ({p.stock_minimo})"
                if p.stock <= p.stock_minimo
                else f"alcanza para unos {_num(cobertura, 0)} días, menos de {DIAS_REPONER}"
            )
            reponer.append(
                _sugerencia(
                    "reponer", "critico" if cobertura < DIAS_QUIEBRE else "advertencia", f"Reponer {p.nombre}",
                    f"Vende {_por_dia(ritmo)} y su stock {motivo}. La cantidad sugerida cubre "
                    f"{DIAS_A_CUBRIR} días de venta más el mínimo configurado.",
                    datos + [("Sugerido", unidades(sugerida))],
                    f"Comprar {unidades(sugerida)}.", "producto", p.id,
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
                    "Revisa qué productos explican la caída (abajo) y si hubo falta de stock.", "ventas", clave="total",
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
            agotado = " Además está agotado: parte de la caída puede ser falta de stock." if p.stock <= 0 else ""
            alertas.append(
                _sugerencia(
                    "caida_producto", "advertencia", f"{p.nombre} vende {_pct(abs(cambio))} menos",
                    f"Pasó de {unidades(u_ant)} a {unidades(u_act)} entre los dos últimos tramos de {VENTANA_DIAS} días.{agotado}",
                    [("30 días anteriores", unidades(u_ant)), ("Últimos 30 días", unidades(u_act)), ("Cambio", f"▼ {_pct(abs(cambio))}")],
                    "Revisa precio, exhibición y stock de este producto.", "producto", pid,
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
                "Asegura su stock y dale visibilidad: es lo que más está jalando.", "producto", pid,
            )
        )
    return res


def _rotacion(productos, ventas, costos, ver_costos, ahora):
    res = []
    for p in productos:
        if p.stock <= max(0, p.stock_minimo) or (ahora - p.created_at).days < DIAS_PRODUCTO_NUEVO:
            continue
        v = ventas.get(p.id)
        vendidas = int(v.u_rot) if v else 0
        rotacion = vendidas / p.stock
        if rotacion >= ROTACION_MINIMA:
            continue
        costo = _costo_unitario(p, costos)
        if ver_costos and costo is not None:
            capital = ("Capital inmovilizado (a costo)", _pesos(costo * p.stock))
        else:
            capital = ("Valor a precio de venta", _pesos(p.precio * p.stock))
        ultima = f"la última fue el {_fecha(v.ultima)}" if v and v.ultima else "nunca se ha vendido"
        dias_salida = f"unos {_num(p.stock / (vendidas / ROTACION_DIAS), 0)} días" if vendidas else "sin fecha: no se está vendiendo"
        res.append(
            _sugerencia(
                "rotacion", "advertencia" if vendidas == 0 else "informativo", f"{p.nombre} rota lento",
                f"Vendió {unidades(vendidas)} en {ROTACION_DIAS} días y tiene {unidades(p.stock)} en stock ({ultima}). "
                f"A ese ritmo el stock tardaría {dias_salida} en salir.",
                [("Vendidas en 60 días", unidades(vendidas)), ("Stock", unidades(p.stock)), capital],
                "Considera una promoción, un combo con un producto ganador o pausar sus compras.", "producto", p.id,
            )
        )
    res.sort(key=lambda s: 0 if s["nivel"] == "advertencia" else 1)
    return res


def _costo_unitario(p, costos) -> Decimal | None:
    c = costos.get(p.id)
    if c and c["unidades"]:
        return c["monto"] / c["unidades"]
    return Decimal(p.precio_compra) if p.precio_compra is not None else None


def _precios(productos, ventas, costos):
    res, sin_costo = [], 0
    for p in productos:
        costo = _costo_unitario(p, costos)
        if costo is None or costo <= 0:
            sin_costo += 1
            continue
        precio = Decimal(p.precio)
        margen = float((precio - costo) / precio) if precio > 0 else -1.0
        if margen >= MARGEN_BAJO:
            continue
        c = costos.get(p.id)
        origen = (f"promedio de {plural(c['compras'], 'compra', 'compras')} en {COSTOS_DIAS} días"
                  if c and c["unidades"] else "costo registrado en el producto")
        sugerido = costo / Decimal(1 - MARGEN_OBJETIVO)
        v = ventas.get(p.id)
        demanda = f" Vendió {unidades(int(v.u_act))} en 30 días: el ajuste pesa en caja." if v and int(v.u_act) else ""
        if margen < 0:
            nivel, titulo = "critico", f"{p.nombre} se vende por debajo del costo"
        else:
            nivel, titulo = "oportunidad", f"{p.nombre} deja poco margen"
        res.append(
            _sugerencia(
                "precio", nivel, titulo,
                f"Cuesta {_pesos(costo)} ({origen}) y se vende a {_pesos(precio)}: margen de {_pct(margen * 100)}, "
                f"por debajo del {_pct(MARGEN_BAJO * 100)}.{demanda}",
                [("Costo", _pesos(costo)), ("Precio actual", _pesos(precio)), ("Margen", _pct(margen * 100)),
                 (f"Precio para {_pct(MARGEN_OBJETIVO * 100)} de margen", _pesos(sugerido))],
                f"Evalúa subir el precio hacia {_pesos(sugerido)} o negociar el costo.", "producto", p.id,
            )
        )
    res.sort(key=lambda s: 0 if s["nivel"] == "critico" else 1)
    return res, sin_costo


def _proveedores(db, tenant_id, productos, por_proveedor, ventas):
    nombres = {p.id: p for p in productos}
    comparables = {pid: filas for pid, filas in por_proveedor.items() if len(filas) >= 2 and pid in nombres}
    if not comparables:
        return [], 0
    ids = {f.proveedor_id for filas in comparables.values() for f in filas}
    provs = {p.id: p for p in db.query(Proveedor).filter(Proveedor.tenant_id == tenant_id, Proveedor.id.in_(ids)).all()}
    res = []
    for pid, filas in comparables.items():
        costo = lambda f: Decimal(f.monto) / int(f.unidades)  # noqa: E731
        mejor = min(filas, key=costo)
        ultima = max(filas, key=lambda f: f.ultima)  # a quién se le compró de último
        if ultima.proveedor_id == mejor.proveedor_id:
            continue
        c_mejor, c_ultima = costo(mejor), costo(ultima)
        ahorro = float((c_ultima - c_mejor) / c_ultima * 100)
        if ahorro < AHORRO_MINIMO_PCT:
            continue
        p = nombres[pid]
        v = ventas.get(pid)
        mensual = int(v.u_act) if v else 0
        impacto = (
            [("Ahorro en un mes de venta", f"{_pesos((c_ultima - c_mejor) * mensual)} ({unidades(mensual)})")]
            if mensual else []
        )
        n_mejor, n_ultima = provs[mejor.proveedor_id].nombre, provs[ultima.proveedor_id].nombre
        res.append(
            _sugerencia(
                "proveedor", "oportunidad", f"{p.nombre}: {n_mejor} te sale {_pct(ahorro)} más barato",
                f"En {COSTOS_DIAS} días le compraste a {n_ultima} a {_pesos(c_ultima)} en promedio "
                f"({plural(int(ultima.compras), 'compra', 'compras')}, la última el {_fecha(ultima.ultima)}) y a {n_mejor} a "
                f"{_pesos(c_mejor)} ({plural(int(mejor.compras), 'compra', 'compras')}).",
                [(n_mejor, f"{_pesos(c_mejor)} / ud"), (n_ultima, f"{_pesos(c_ultima)} / ud"), ("Diferencia", f"▼ {_pct(ahorro)}")] + impacto,
                f"Cotiza la próxima compra con {n_mejor}.", "proveedor", mejor.proveedor_id, clave=pid,
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
                f"Refuerza stock y personal antes de cada {DIAS_SEMANA[int(mejor)]}; prueba una promoción el {DIAS_SEMANA[peor]}.",
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
                "Programa reposición y turnos para llegar completos a esa franja.", clave="hora",
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
            "la historia de ventas (márgenes y proveedores) sí se muestran."
        ),
    }

    productos = db.query(Producto).filter(Producto.tenant_id == tenant_id, Producto.activo.is_(True)).order_by(Producto.nombre).all()
    ventas = _ventas_por_producto(db, tenant_id, ahora)
    costos, por_proveedor = _costos(db, tenant_id, ahora)
    insuficiente = "Sin base suficiente de ventas (ver arriba)."

    if suficiente:
        quiebres, reponer, sin_ritmo = _stock(productos, ventas, ahora)
        alertas = quiebres + _caidas(productos, ventas)
        ganadores = _ganadores(productos, ventas)
        patrones, nota_patrones = _patrones(db, tenant_id, ahora)
        rotacion = _rotacion(productos, ventas, costos, ver_costos, ahora)
        nota_reponer = None if reponer else (
            "Ningún producto necesita reposición en los próximos " f"{DIAS_REPONER} días al ritmo actual."
            + (f" {plural(sin_ritmo, 'producto no tiene', 'productos no tienen')} ventas suficientes en 30 días para estimar su ritmo." if sin_ritmo else "")
        )
        secciones = [
            _seccion("alertas", "Alertas inteligentes", "Quiebres de stock previsibles y caídas de venta.", alertas,
                     None if alertas else "Sin quiebres previsibles ni caídas notables: el ritmo de venta y el stock van parejos."),
            _seccion("reponer", "Productos a reponer", f"Cobertura menor a {DIAS_REPONER} días al ritmo de los últimos 30.", reponer, nota_reponer),
            _seccion("ganadores", "Productos ganadores", f"Los que más venden y crecen al menos {_pct(CRECIMIENTO_GANADOR_PCT)}.", ganadores,
                     None if ganadores else "Ningún producto crece de forma notable frente a los 30 días anteriores."),
            _seccion("patrones", "Patrones de venta", f"Días y horas fuertes en las últimas {SEMANAS_PATRON} semanas.", patrones, nota_patrones),
            _seccion("rotacion", "Baja rotación", f"Stock que se vende muy despacio (menos de un cuarto en {ROTACION_DIAS} días).", rotacion,
                     None if rotacion else "Todo el stock con más de 30 días rota a un ritmo razonable."),
        ]
    else:
        secciones = [
            _seccion(clave, titulo, desc, sin_datos=insuficiente)
            for clave, titulo, desc in (
                ("alertas", "Alertas inteligentes", "Quiebres de stock previsibles y caídas de venta."),
                ("reponer", "Productos a reponer", "Según el ritmo de venta."),
                ("ganadores", "Productos ganadores", "Los que más venden y crecen."),
                ("patrones", "Patrones de venta", "Días y horas fuertes."),
                ("rotacion", "Baja rotación", "Stock que se vende muy despacio."),
            )
        ]

    sin_permiso = "Tu rol no ve costos ni márgenes (requiere el permiso de ver compras), así que esta sección no se muestra."
    if ver_costos:
        precios, sin_costo = _precios(productos, ventas, costos)
        proveedores, comparables = _proveedores(db, tenant_id, productos, por_proveedor, ventas)
        nota_precios = None if precios else (
            f"Todos los productos con costo conocido dejan al menos {_pct(MARGEN_BAJO * 100)} de margen."
            + (f" {plural(sin_costo, 'producto no tiene', 'productos no tienen')} costo (ni compras en {COSTOS_DIAS} días ni costo registrado)." if sin_costo else "")
            if len(productos) > sin_costo else "Ningún producto tiene costo conocido todavía: registra compras para calcular márgenes."
        )
        nota_prov = None if proveedores else (
            f"Ningún producto se ha comprado a más de un proveedor en {COSTOS_DIAS} días: no hay con qué comparar."
            if not comparables else "Ya le compras cada producto al proveedor más barato que tienes registrado."
        )
        secciones.append(_seccion("precios", "Oportunidades de precio", f"Productos con margen menor a {_pct(MARGEN_BAJO * 100)}.", precios, nota_precios, True))
        secciones.append(_seccion("proveedores", "Proveedores con mejores condiciones", f"Costo promedio por proveedor en {COSTOS_DIAS} días.", proveedores, nota_prov, True))
    else:
        secciones.append(_seccion("precios", "Oportunidades de precio", "Según el margen de cada producto.", sin_datos=sin_permiso, requiere_costos=True))
        secciones.append(_seccion("proveedores", "Proveedores con mejores condiciones", "Costo por proveedor.", sin_datos=sin_permiso, requiere_costos=True))

    return {
        "generado_en": ahora.isoformat(),
        "motor": "Reglas estadísticas locales",
        "privacidad": PRIVACIDAD,
        "base": base,
        "secciones": secciones,
    }
