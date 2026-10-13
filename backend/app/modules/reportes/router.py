"""
REPORTES (fase 8, 2026-10-12): cuánto entró, cuánto costó y cuánto gané, por
día, semana, mes, año o un periodo personalizado, con el detalle que explica
las cifras (platos y su margen, horas, días, tipos de orden, meseros, medios
de pago, categorías, insumos y mermas, gastos). Todo exportable a CSV (por
sección) y a PDF.

Las cifras de COSTO (costo, utilidades, margen, consumo valorizado) solo las
ve quien tiene `costos.ver`; el resto de un reporte no las trae.
"""
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.core.exportar import campo, respuesta_csv
from app.core.pdf import formatear_moneda, generar_reporte_pdf
from app.core.permisos import tiene_permiso, usuario_con_permiso
from app.db.models import Tenant
from app.db.session import get_db
from app.modules.dashboard.periodos import PERIODOS, ventana_de_periodo
from app.modules.reportes import consultas as q
from app.modules.seguridad.models import Usuario

router = APIRouter(prefix="/reportes", tags=["Reportes"])

MAX_DIAS = 400
CAMPOS_DE_COSTO = {"costo", "utilidad_bruta", "utilidad_real", "margen_bruto_pct", "costo_pct", "margen", "costo_consumo", "costo_merma"}


def _tramo(periodo: str | None, desde: date | None, hasta: date | None) -> tuple[datetime, datetime, str]:
    """[desde, hasta) en UTC naive desde días de Colombia (inclusive) o un
    periodo con nombre (hoy, semana, mes, año)."""
    if desde or hasta:
        if not (desde and hasta):
            raise ConflictError("Para un periodo personalizado indica el día inicial y el final.")
        if hasta < desde:
            raise ConflictError("El día final no puede ser anterior al inicial.")
        if (hasta - desde).days > MAX_DIAS:
            raise ConflictError(f"El periodo personalizado puede ser de hasta {MAX_DIAS} días.")
        inicio = datetime.combine(desde, time()) - q.DESFASE
        return inicio, datetime.combine(hasta + timedelta(days=1), time()) - q.DESFASE, f"Del {desde:%d/%m/%Y} al {hasta:%d/%m/%Y}"
    v = ventana_de_periodo(periodo or "mes")
    nombres = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes", "anio": "Este año"}
    return v.desde, v.hasta, nombres[periodo or "mes"]


def _sin_costos(datos, ver_costos: bool):
    if ver_costos:
        return datos
    if isinstance(datos, list):
        return [_sin_costos(x, False) for x in datos]
    if isinstance(datos, dict):
        return {k: (None if k in CAMPOS_DE_COSTO else _sin_costos(v, False)) for k, v in datos.items()}
    return datos


def _parametros(
    periodo: str | None = Query(default=None, pattern="^(" + "|".join(PERIODOS) + ")$"),
    desde: date | None = Query(default=None, description="Día de Colombia, inclusive"),
    hasta: date | None = Query(default=None, description="Día de Colombia, inclusive"),
):
    return _tramo(periodo, desde, hasta)


SECCIONES = {
    "platos": q.platos,
    "horas": q.por_hora,
    "dias": q.por_dia_semana,
    "tipos": q.por_tipo,
    "meseros": q.por_mesero,
    "medios": q.por_medio,
    "categorias": q.por_categoria,
    "insumos": q.insumos,
    "gastos": q.gastos,
}


@router.get("")
def reporte(tramo=Depends(_parametros), db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("reportes", "ver"))):
    desde, hasta, nombre = tramo
    tenant_id = usuario.tenant_id
    datos = {
        "periodo": nombre, "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "resumen": q.resumen(db, tenant_id, desde, hasta),
        **{clave: funcion(db, tenant_id, desde, hasta) for clave, funcion in SECCIONES.items()},
    }
    return _sin_costos(datos, tiene_permiso(usuario, "costos", "ver"))


COLUMNAS_CSV = {
    "platos": [("Plato", campo("nombre")), ("Categoría", campo("categoria")), ("Unidades", campo("unidades")), ("Vendido", campo("vendido")),
               ("Ingresos sin impuesto", campo("ingresos")), ("Costo", campo("costo")), ("Margen", campo("margen")), ("% costo", campo("costo_pct"))],
    "horas": [("Hora", campo("hora")), ("Cobros", campo("cobros")), ("Vendido", campo("total"))],
    "dias": [("Día", campo("dia")), ("Órdenes", campo("ordenes")), ("Vendido", campo("total"))],
    "tipos": [("Tipo de orden", campo("nombre")), ("Órdenes", campo("ordenes")), ("Vendido", campo("total")), ("Ticket promedio", campo("ticket"))],
    "meseros": [("Mesero", campo("nombre")), ("Órdenes", campo("ordenes")), ("Vendido", campo("total")), ("Ticket promedio", campo("ticket"))],
    "medios": [("Medio de pago", campo("nombre")), ("Recibido", campo("total"))],
    "categorias": [("Categoría", campo("nombre")), ("Vendido", campo("total"))],
    "insumos": [("Insumo", campo("nombre")), ("Unidad", campo("unidad")), ("Consumo", campo("consumo")), ("Costo del consumo", campo("costo_consumo")),
                ("Merma", campo("merma")), ("Costo de la merma", campo("costo_merma")), ("% merma", campo("merma_pct"))],
    "gastos": [("Categoría", campo("nombre")), ("Registros", campo("registros")), ("Total", campo("total"))],
}


@router.get("/csv")
def exportar_csv(
    seccion: str = Query(pattern="^(" + "|".join(SECCIONES) + ")$"),
    tramo=Depends(_parametros),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_con_permiso("reportes", "ver")),
):
    desde, hasta, _ = tramo
    ver = tiene_permiso(usuario, "costos", "ver")
    filas = _sin_costos(SECCIONES[seccion](db, usuario.tenant_id, desde, hasta), ver)
    columnas = [c for c in COLUMNAS_CSV[seccion] if ver or c[0] not in ("Costo", "Margen", "% costo", "Costo del consumo", "Costo de la merma")]
    return respuesta_csv(f"reporte-{seccion}", columnas, filas)


def _pesos(valor) -> str:
    return "—" if valor is None else formatear_moneda(valor)


@router.get("/pdf")
def exportar_pdf(tramo=Depends(_parametros), db: Session = Depends(get_db), usuario: Usuario = Depends(usuario_con_permiso("reportes", "ver"))):
    desde, hasta, nombre = tramo
    tid = usuario.tenant_id
    ver = tiene_permiso(usuario, "costos", "ver")
    r = q.resumen(db, tid, desde, hasta)
    resumen = [("Vendido (con impuesto)", _pesos(r["total"])), ("Ingresos (sin impuesto)", _pesos(r["ingresos"])),
               ("Impuesto al consumo", _pesos(r["impuesto"])), ("Propinas (no son ingreso)", _pesos(r["propinas"]))]
    if ver:
        resumen += [("Costo de lo vendido", _pesos(r["costo"])), ("Utilidad bruta", _pesos(r["utilidad_bruta"])),
                    ("Gastos", _pesos(r["gastos"])), ("Utilidad real", _pesos(r["utilidad_real"]))]
    resumen += [("Órdenes", str(r["ordenes"])), ("Ticket promedio", _pesos(r["ticket_promedio"]))]
    platos = q.platos(db, tid, desde, hasta)
    secciones = [
        ("Platos", ["Plato", "Unidades", "Vendido"] + (["Costo", "Margen", "% costo"] if ver else []),
         [[p["nombre"], p["unidades"], _pesos(p["vendido"])] + ([_pesos(p["costo"]), _pesos(p["margen"]), f"{p['costo_pct']} %" if p["costo_pct"] is not None else "—"] if ver else []) for p in platos]),
        ("Por tipo de orden", ["Tipo", "Órdenes", "Vendido", "Ticket"], [[t["nombre"], t["ordenes"], _pesos(t["total"]), _pesos(t["ticket"])] for t in q.por_tipo(db, tid, desde, hasta)]),
        ("Por mesero", ["Mesero", "Órdenes", "Vendido", "Ticket"], [[m["nombre"], m["ordenes"], _pesos(m["total"]), _pesos(m["ticket"])] for m in q.por_mesero(db, tid, desde, hasta)]),
        ("Por medio de pago", ["Medio", "Recibido"], [[m["nombre"], _pesos(m["total"])] for m in q.por_medio(db, tid, desde, hasta)]),
        ("Horas de más venta", ["Hora", "Cobros", "Vendido"], [[f"{h['hora']:02d}:00", h["cobros"], _pesos(h["total"])] for h in q.por_hora(db, tid, desde, hasta) if h["cobros"]]),
        ("Gastos", ["Categoría", "Registros", "Total"], [[g["nombre"], g["registros"], _pesos(g["total"])] for g in q.gastos(db, tid, desde, hasta)]),
    ]
    if ver:
        secciones.append(("Insumos: consumo y mermas", ["Insumo", "Consumo", "Costo", "Merma", "Costo merma"],
                          [[i["nombre"], f"{i['consumo']:g} {i['unidad']}", _pesos(i["costo_consumo"]), f"{i['merma']:g} {i['unidad']}", _pesos(i["costo_merma"])]
                           for i in q.insumos(db, tid, desde, hasta)]))
    tenant = db.get(Tenant, tid)
    contenido = generar_reporte_pdf(titulo="Reporte", empresa=tenant.nombre_empresa, subtitulo=nombre, resumen=resumen, secciones=secciones)
    return Response(content=contenido, media_type="application/pdf", headers={"Content-Disposition": 'inline; filename="reporte.pdf"'})
