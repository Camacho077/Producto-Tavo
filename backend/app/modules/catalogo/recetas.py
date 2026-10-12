"""
COSTO Y CONSUMO POR RECETA (2026-10-12) — la pieza que responde "¿cuánto me
cuesta cada plato?".

- `costo_de_producto`: costo de UNA porción, calculado EN VIVO con el costo
  vigente de cada insumo. No se guarda: cuando una compra cambia el costo de
  un insumo, todos los platos que lo usan quedan recalculados solos.
- `consumo`: cuánto de cada insumo gasta un conjunto de líneas vendidas
  (plato × cantidad, con sus modificadores; un combo se abre en sus platos),
  ya convertido a la unidad de cada insumo. Lo usa quien descuenta inventario.
- Margen sobre el precio NETO: si la carta incluye el impuesto al consumo,
  ese 8 % no es ingreso del restaurante (se le paga a la DIAN).
"""
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from app.modules.ajustes.schemas import ConfiguracionRestaurante
from app.modules.catalogo.models import Modificador, Producto, RecetaItem
from app.modules.inventario.unidades import convertir

CENTAVOS = Decimal("0.01")
UNO = Decimal("1")
CIEN = Decimal("100")


def _a_pesos(valor: Decimal) -> Decimal:
    return Decimal(valor).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


def cantidad_por_porcion(linea: RecetaItem) -> Decimal:
    """Lo que sale de la bodega por porción, en la unidad del insumo,
    incluida la merma."""
    bruto = Decimal(linea.cantidad) * (UNO + Decimal(linea.merma_porcentaje or 0) / CIEN)
    return convertir(bruto, linea.unidad, linea.insumo.unidad)


def costo_linea(linea: RecetaItem) -> Decimal:
    return cantidad_por_porcion(linea) * Decimal(linea.insumo.costo_unitario)


def cantidad_de_modificador(mod: Modificador) -> Decimal:
    if not (mod.insumo_id and mod.cantidad and mod.unidad and mod.insumo):
        return Decimal("0")
    return convertir(Decimal(mod.cantidad), mod.unidad, mod.insumo.unidad)


def costo_modificador(mod: Modificador) -> Decimal | None:
    """Costo de un EXTRA (lo que agrega). Un «sin» no cuesta: ahorra."""
    if mod.tipo != "extra" or not mod.insumo_id:
        return None
    return _a_pesos(cantidad_de_modificador(mod) * Decimal(mod.insumo.costo_unitario))


def costo_de_producto(producto: Producto) -> Decimal | None:
    """Costo de UNA porción. None si no hay con qué calcularlo (un plato sin
    receta o un combo con algún plato sin receta): mejor "sin dato" que un
    costo cero que haría ver un margen del 100 %."""
    if producto.tipo == "combo":
        if not producto.componentes:
            return None
        total = Decimal("0")
        for comp in producto.componentes:
            costo = costo_de_producto(comp.producto)
            if costo is None:
                return None
            total += costo * comp.cantidad
        return _a_pesos(total)
    if not producto.receta:
        return None
    return _a_pesos(sum((costo_linea(l) for l in producto.receta), Decimal("0")))


def precio_neto(precio: Decimal, config: ConfiguracionRestaurante | None) -> Decimal:
    """Precio sin el impuesto al consumo (si la carta lo incluye)."""
    precio = Decimal(precio)
    if config and config.impuesto_consumo.aplica and config.impuesto_consumo.incluido_en_precio:
        return _a_pesos(precio / (UNO + Decimal(config.impuesto_consumo.tasa) / CIEN))
    return _a_pesos(precio)


def costeo(producto: Producto, config: ConfiguracionRestaurante | None) -> dict:
    """{costo, precio_neto, margen, porcentaje_costo} de una porción."""
    costo = costo_de_producto(producto)
    neto = precio_neto(producto.precio, config)
    if costo is None:
        return {"costo": None, "precio_neto": neto, "margen": None, "porcentaje_costo": None}
    return {
        "costo": costo,
        "precio_neto": neto,
        "margen": _a_pesos(neto - costo),
        "porcentaje_costo": _a_pesos(costo / neto * CIEN) if neto > 0 else None,
    }


# ---------------------------------------------------------------------------
# Consumo de insumos de lo vendido
# ---------------------------------------------------------------------------
@dataclass
class LineaVendida:
    producto: Producto
    cantidad: int
    modificadores: list[Modificador] = field(default_factory=list)


def _sumar_plato(acumulado: dict, plato: Producto, porciones: Decimal, modificadores: list[Modificador]) -> None:
    quitados = {m.insumo_id for m in modificadores if m.tipo == "sin" and m.insumo_id}
    for linea in plato.receta:
        if linea.insumo_id in quitados:
            continue
        acumulado[linea.insumo_id] += cantidad_por_porcion(linea) * porciones
    for mod in modificadores:
        if mod.tipo == "extra" and mod.insumo_id:
            acumulado[mod.insumo_id] += cantidad_de_modificador(mod) * porciones


def consumo(lineas: list[LineaVendida]) -> dict:
    """{insumo_id: cantidad en la unidad del insumo} que gastan las líneas."""
    acumulado: dict = defaultdict(lambda: Decimal("0"))
    for l in lineas:
        porciones = Decimal(l.cantidad)
        if l.producto.tipo == "combo":
            for comp in l.producto.componentes:
                _sumar_plato(acumulado, comp.producto, porciones * comp.cantidad, [])
        else:
            _sumar_plato(acumulado, l.producto, porciones, l.modificadores)
    return dict(acumulado)


def costo_unitario_vendido(producto: Producto, modificadores: list[Modificador]) -> Decimal | None:
    """Costo de UNA unidad tal como se vendió (con sus «sin» y sus «extra»).
    Se guarda en la línea de la venta: el margen de ese día no cambia aunque
    después suba el insumo."""
    base = costo_de_producto(producto)
    if base is None:
        return None
    if producto.tipo == "combo":
        return base
    quitados = {m.insumo_id for m in modificadores if m.tipo == "sin" and m.insumo_id}
    ahorro = sum((costo_linea(l) for l in producto.receta if l.insumo_id in quitados), Decimal("0"))
    extra = sum((cantidad_de_modificador(m) * Decimal(m.insumo.costo_unitario) for m in modificadores if m.tipo == "extra" and m.insumo_id), Decimal("0"))
    return _a_pesos(base - ahorro + extra)


def platos_que_usan(productos: list[Producto], insumo_ids: set) -> list[Producto]:
    """De estos productos, los que gastan alguno de esos insumos."""
    return [
        p for p in productos
        if any(l.insumo_id in insumo_ids for l in p.receta)
        or any(any(l.insumo_id in insumo_ids for l in c.producto.receta) for c in p.componentes)
    ]
