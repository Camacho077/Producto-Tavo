"""
EXPORTAR LISTADOS A CSV (2026-10-01).

No hay rutas nuevas: cada listado acepta `?formato=csv` (ver
`ParametrosPagina` en paginacion.py). Así la exportación usa EXACTAMENTE la
misma consulta, los mismos filtros, la misma búsqueda y el MISMO permiso que
la tabla que el usuario está viendo, y también los mismos campos ocultos (el
costo sale vacío para quien no ve compras, porque se exporta lo ya
serializado para ese usuario). Lo protege tests/test_exportar.py.

Formato pensado para abrirse con doble clic en Excel en Colombia:
- separador `;` y coma decimal (la configuración regional es-CO);
- UTF-8 con BOM, para que Excel lea bien las tildes y la ñ;
- fechas en hora de Colombia (`AAAA-MM-DD HH:MM`), igual que en pantalla;
- celdas que empiezan por `=`, `+`, `@` o `-` (no numérico) se neutralizan
  con un apóstrofo: un nombre como `=HYPERLINK(...)` no se ejecuta como
  fórmula al abrir el archivo (inyección CSV, OWASP).
"""
import csv
import io
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable

from fastapi import Response

from app.core.errors import AppError
from app.core.validaciones import ZONA_NEGOCIO

MAX_FILAS_EXPORTAR = 50_000


class ExportacionDemasiadoGrande(AppError):
    status_code = 413
    detail = "La exportación es demasiado grande."


# (encabezado, función que recibe la fila serializada y devuelve el valor)
Columna = tuple[str, Callable[[dict], Any]]


def campo(nombre: str) -> Callable[[dict], Any]:
    return lambda fila: fila.get(nombre)


def _celda(valor: Any) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (Decimal, float)):
        return f"{Decimal(str(valor)):.2f}".replace(".", ",")
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, datetime):
        # Las columnas guardan UTC sin zona: se pasa a la hora de Colombia.
        local = valor + ZONA_NEGOCIO.utcoffset(None) if valor.tzinfo is None else valor.astimezone(ZONA_NEGOCIO)
        return local.strftime("%Y-%m-%d %H:%M")
    texto = str(valor)
    if texto[:1] in ("=", "+", "@", "\t", "\r") or (texto[:1] == "-" and not texto[1:2].isdigit()):
        return "'" + texto
    return texto


def respuesta_csv(nombre: str, columnas: list[Columna], filas: list[dict]) -> Response:
    buffer = io.StringIO()
    escritor = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    escritor.writerow([encabezado for encabezado, _ in columnas])
    for fila in filas:
        escritor.writerow([_celda(obtener(fila)) for _, obtener in columnas])
    contenido = "﻿" + buffer.getvalue()
    return Response(
        content=contenido.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nombre}.csv"'},
    )


def responder(pagina: dict, params, esquema, columnas: list[Columna], nombre: str):
    """Devuelve la página tal cual (JSON) o, con `?formato=csv`, el CSV de
    TODAS las filas que cumplen los filtros (paginar ya no recortó)."""
    if getattr(params, "formato", None) != "csv":
        return pagina
    # Sin esquema, las filas ya son diccionarios serializados.
    filas = pagina["items"] if esquema is None else [esquema.model_validate(item, from_attributes=True).model_dump() for item in pagina["items"]]
    return respuesta_csv(nombre, columnas, filas)


def humanizar(valor: str | None) -> str:
    """"en_proceso" → "en proceso" (los estados se exportan legibles)."""
    return (valor or "").replace("_", " ")


def resumen_items(fila: dict) -> str:
    """"Arroz × 10; Leche × 4" — una celda por documento, legible en Excel."""
    return "; ".join(f"{i.get('producto_nombre') or i.get('producto_sku') or 'Producto'} × {i['cantidad']}" for i in fila.get("items") or [])
