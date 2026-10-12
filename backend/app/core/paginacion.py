"""
Paginación y búsqueda compartidas por todos los listados del backend.

Todos los endpoints de listado reciben los mismos parámetros (`q`, `pagina`,
`por_pagina`) y devuelven el mismo sobre `{items, total, pagina, por_pagina,
paginas}`, así el frontend usa un único componente de tabla para todo.
"""
from typing import Generic, Literal, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Query as OrmQuery

T = TypeVar("T")


class ParametrosPagina:
    def __init__(
        self,
        q: str | None = Query(default=None, max_length=100, description="Texto a buscar"),
        pagina: int = Query(default=1, ge=1),
        por_pagina: int = Query(default=10, ge=1, le=100),
        formato: Literal["json", "csv"] = Query(
            default="json", description="csv: TODAS las filas que cumplen la búsqueda y los filtros, como archivo"
        ),
    ):
        self.q = q.strip() if q else None
        self.pagina = pagina
        self.por_pagina = por_pagina
        self.formato = formato


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    pagina: int
    por_pagina: int
    paginas: int


def paginar(query: OrmQuery, params: ParametrosPagina, columnas_busqueda=(), orden=None) -> dict:
    """Aplica búsqueda ILIKE sobre `columnas_busqueda`, ordena y pagina."""
    if params.q and columnas_busqueda:
        patron = f"%{params.q}%"
        query = query.filter(or_(*[col.ilike(patron) for col in columnas_busqueda]))
    total = query.order_by(None).count()
    if orden is not None:
        query = query.order_by(*orden) if isinstance(orden, (list, tuple)) else query.order_by(orden)
    if getattr(params, "formato", "json") == "csv":
        # Exportación (app/core/exportar.py): la misma consulta, sin recortar.
        from app.core.exportar import MAX_FILAS_EXPORTAR, ExportacionDemasiadoGrande

        if total > MAX_FILAS_EXPORTAR:
            raise ExportacionDemasiadoGrande(
                f"La exportación tendría {total:,} filas y el máximo es {MAX_FILAS_EXPORTAR:,}. ".replace(",", ".")
                + "Usa la búsqueda o los filtros para acotarla."
            )
        return {"items": query.all(), "total": total, "pagina": 1, "por_pagina": total, "paginas": 1}
    items = query.offset((params.pagina - 1) * params.por_pagina).limit(params.por_pagina).all()
    paginas = max(1, -(-total // params.por_pagina))
    return {
        "items": items,
        "total": total,
        "pagina": params.pagina,
        "por_pagina": params.por_pagina,
        "paginas": paginas,
    }
