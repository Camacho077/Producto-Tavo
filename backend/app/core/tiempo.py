"""
La hora "ahora" del backend, en UN solo lugar (2026-09-30).

`datetime.utcnow()` está deprecado desde Python 3.12 y se va a eliminar: solo
el `default=datetime.utcnow` de TimestampMixin producía más de 6.400 avisos
en cada corrida de la suite (uno por cada fila insertada).

`ahora_utc()` devuelve lo MISMO que devolvía `utcnow()` —la hora UTC sin
tzinfo— porque las columnas de fecha del negocio son DateTime naive y
mezclarlas con un datetime con zona revienta la comparación en SQL.
"""
from datetime import datetime, timezone


def ahora_utc() -> datetime:
    """Hora UTC actual, naive (sin tzinfo), para columnas DateTime naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
