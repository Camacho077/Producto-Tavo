"""
Mensajes de error en español, con la CAUSA CONCRETA.

Regla del producto: ningún endpoint devuelve un error genérico del estilo
"No se pudo completar la operación". El `detail` que viaja al frontend es la
frase que ve el usuario en la alerta roja, así que siempre nombra el registro
involucrado y explica por qué no se pudo hacer lo que se pidió:

    "No se puede eliminar la categoría Celulares: tiene 3 productos asociados."

Aquí viven los constructores de esas frases para que todos los módulos las
armen igual (mismo orden, misma puntuación, mismos plurales) y para que
cambiar la redacción sea un solo sitio.
"""


def plural(cantidad: int, singular: str, plural_: str | None = None) -> str:
    """"1 producto" / "3 productos" — el plural por defecto agrega "s"."""
    return f"{cantidad} {singular if cantidad == 1 else (plural_ or singular + 's')}"


def unidades(cantidad: int) -> str:
    return plural(cantidad, "unidad", "unidades")


def ya_existe(entidad: str, campo: str, valor: str) -> str:
    """entidad="una categoría", campo="nombre" → "Ya existe una categoría con el nombre Celulares"."""
    return f"Ya existe {entidad} con el {campo} {valor}."


def no_se_puede_eliminar(entidad: str, nombre: str, cantidad: int, dependencia: str, dependencia_plural: str, alternativa: str) -> str:
    """"No se puede eliminar la categoría Celulares: tiene 3 productos asociados. …"."""
    return (
        f"No se puede eliminar {entidad} {nombre}: tiene {plural(cantidad, dependencia, dependencia_plural)} "
        f"asociad{'o' if dependencia.endswith('o') else 'a'}{'' if cantidad == 1 else 's'}. {alternativa}"
    )


def estado_no_permite(accion: str, entidad: str, codigo: str, estado_actual: str, permitidos: tuple[str, ...]) -> str:
    """"No se puede confirmar la compra COM-000003: está en estado anulada y
    solo se puede confirmar una compra pendiente."."""
    lista = " o ".join(permitidos)
    return (
        f"No se puede {accion} {entidad} {codigo}: está en estado {estado_actual} "
        f"y solo se puede {accion} {entidad} en estado {lista}."
    )


def no_existe(entidad: str) -> str:
    """"La compra indicada no existe o pertenece a otra empresa."."""
    return f"{entidad} no existe o pertenece a otra empresa."
