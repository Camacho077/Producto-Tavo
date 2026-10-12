"""
UNIDADES DE MEDIDA DE LOS INSUMOS (2026-10-12).

Cada insumo lleva su existencia en UNA unidad (la suya). Las compras y las
recetas pueden escribirse en otra unidad de la misma familia: se compra el
queso por kilo y la receta gasta gramos. Aquí se convierte, y en ningún otro
lado.

Familias: masa (kg, g), volumen (L, ml) y conteo (unidad). Entre familias no
hay conversión posible (un "kilo de huevos" no se sabe cuántos huevos son):
se rechaza con la causa.
"""
from decimal import ROUND_HALF_UP, Decimal

UNIDADES: dict[str, tuple[str, Decimal]] = {
    # unidad: (familia, cuántas unidades base vale)
    "kg": ("masa", Decimal("1000")),
    "g": ("masa", Decimal("1")),
    "L": ("volumen", Decimal("1000")),
    "ml": ("volumen", Decimal("1")),
    "unidad": ("conteo", Decimal("1")),
}
NOMBRES = {"kg": "kilogramos", "g": "gramos", "L": "litros", "ml": "mililitros", "unidad": "unidades"}
FAMILIAS = {"masa": "de peso (kg, g)", "volumen": "de volumen (L, ml)", "conteo": "por unidad"}

TRES_DECIMALES = Decimal("0.001")


def familia(unidad: str) -> str:
    return UNIDADES[unidad][0]


def compatibles(a: str, b: str) -> bool:
    return familia(a) == familia(b)


def unidades_de_familia(unidad: str) -> list[str]:
    """Las unidades en que se puede escribir una cantidad de este insumo."""
    fam = familia(unidad)
    return [u for u, (f, _) in UNIDADES.items() if f == fam]


def convertir(cantidad: Decimal, de: str, a: str) -> Decimal:
    """`cantidad` en `de` expresada en `a`. Lanza ValueError entre familias."""
    if not compatibles(de, a):
        raise ValueError(
            f"No se puede convertir {de} a {a}: el insumo se mide {FAMILIAS[familia(a)]} "
            f"y la cantidad está {FAMILIAS[familia(de)]}."
        )
    return Decimal(cantidad) * UNIDADES[de][1] / UNIDADES[a][1]


def redondear(cantidad: Decimal) -> Decimal:
    return Decimal(cantidad).quantize(TRES_DECIMALES, rounding=ROUND_HALF_UP)


def legible(cantidad: Decimal, unidad: str) -> str:
    """"200 g", "1,5 kg", "3 unidades" — para los mensajes al usuario. Si la
    cantidad es pequeña en kg o L, se dice en g o ml (es como habla la gente)."""
    cantidad = Decimal(cantidad)
    if unidad in ("kg", "L") and 0 < abs(cantidad) < 1:
        menor = "g" if unidad == "kg" else "ml"
        return legible(convertir(cantidad, unidad, menor), menor)
    texto = f"{redondear(cantidad).normalize():f}".replace(".", ",")
    if unidad == "unidad":
        return f"{texto} {'unidad' if cantidad == 1 else 'unidades'}"
    return f"{texto} {unidad}"
