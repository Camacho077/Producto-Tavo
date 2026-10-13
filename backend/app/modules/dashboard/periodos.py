"""
Ventanas de tiempo del dashboard.

Dos ejes independientes, porque en la pantalla son dos controles distintos:

1. El PERIODO de las cifras (Hoy / Mes / Año). Es un tramo de calendario que
   termina hoy, comparado contra el MISMO número de días del periodo anterior
   — no contra el mes anterior completo. Comparar 12 días de septiembre contra
   30 de agosto daría una caída inventada.

2. El RANGO de la gráfica (1D / 1S / 1M / 6M / 1A). Define cuántos puntos
   tiene la serie y de qué tamaño es cada punto (hora, día o mes), más el
   tramo anterior del mismo tamaño para la comparativa punteada.

El calendario es el del NEGOCIO (Colombia, UTC-5), no el de UTC (decisión del
2026-09-30): con días UTC, "Hoy" iba en Bogotá de 19:00 a 19:00 y después de
las 7 p. m. las ventas de la mañana desaparecían de "Hoy". Así que los límites
(medianoche, día 1, 1 de enero, cada hora/día/mes de la gráfica) se calculan
en hora de Bogotá y se CONVIERTEN a UTC naive antes de llegar a SQL:
`Venta.fecha` y `Compra.fecha` son DateTime sin zona, en UTC, y mezclar un
datetime con tzinfo revienta la comparación. Todos los instantes que salen de
este módulo (y del API) siguen siendo UTC naive; solo cambia dónde caen.

El backend NO devuelve etiquetas legibles: devuelve el instante de inicio de
cada punto en ISO y el frontend lo formatea con Intl según la configuración
regional.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.tiempo import ahora_utc as _ahora_utc
from app.core.validaciones import ZONA_NEGOCIO

PERIODOS = ("hoy", "semana", "mes", "anio")
RANGOS_GRAFICA = ("1d", "1s", "1m", "6m", "1a")

# Cuántos puntos tiene cada rango y de qué tamaño es cada punto. Son los
# cinco botones de la maqueta; cambiar aquí cambia la gráfica entera.
FORMA_DE_RANGO = {
    "1d": ("hora", 24),
    "1s": ("day", 7),
    "1m": ("day", 30),
    "6m": ("month", 6),
    "1a": ("month", 12),
}

# Unidad tal como la entiende date_trunc de Postgres.
UNIDAD_SQL = {"hora": "hour", "day": "day", "month": "month"}


# `ahora_utc` vive en app/core/tiempo.py (la usan también los modelos); se
# re-exporta aquí porque el router y las pruebas del dashboard la importan
# de este módulo.
ahora_utc = _ahora_utc


# Desfase fijo del negocio frente a UTC (-5 h). Colombia no tiene horario de
# verano, así que sumar una constante es exacto todo el año.
DESFASE_NEGOCIO = ZONA_NEGOCIO.utcoffset(None)


def a_hora_negocio(momento_utc: datetime) -> datetime:
    """UTC naive -> hora de pared de Bogotá, también naive."""
    return momento_utc + DESFASE_NEGOCIO


def a_utc(momento_negocio: datetime) -> datetime:
    """Hora de pared de Bogotá (naive) -> UTC naive, lo que se compara en SQL."""
    return momento_negocio - DESFASE_NEGOCIO


def inicio_de_dia(momento: datetime) -> datetime:
    return momento.replace(hour=0, minute=0, second=0, microsecond=0)


def avanzar_meses(momento: datetime, n: int) -> datetime:
    """Suma (o resta, con n negativo) meses respetando el día del mes: el
    31 de marzo menos un mes es el 28/29 de febrero, no el 3 de marzo."""
    total = momento.month - 1 + n
    anio = momento.year + total // 12
    mes = total % 12 + 1
    dia = min(momento.day, monthrange(anio, mes)[1])
    return momento.replace(year=anio, month=mes, day=dia)


def inicio_de_bucket(momento: datetime, unidad: str) -> datetime:
    """El instante con el que date_trunc etiqueta el bucket que contiene a
    `momento`. Tiene que coincidir exactamente con la clave que devuelve
    Postgres, o la serie sale toda en cero."""
    if unidad == "hora":
        return momento.replace(minute=0, second=0, microsecond=0)
    if unidad == "day":
        return inicio_de_dia(momento)
    return inicio_de_dia(momento).replace(day=1)


def avanzar_bucket(momento: datetime, unidad: str, n: int) -> datetime:
    if unidad == "hora":
        return momento + timedelta(hours=n)
    if unidad == "day":
        return momento + timedelta(days=n)
    return avanzar_meses(momento, n)


@dataclass(frozen=True)
class Ventana:
    """Tramo actual y el tramo anterior del mismo largo. `hasta` es exclusivo."""

    periodo: str
    desde: datetime
    hasta: datetime
    desde_anterior: datetime
    hasta_anterior: datetime

    @property
    def dias(self) -> int:
        return max(1, (self.hasta - self.desde).days)


def ventana_de_periodo(periodo: str, ahora: datetime | None = None) -> Ventana:
    """
    `ahora` es UTC naive; "hoy" es el día calendario de Bogotá.

    - hoy:  desde las 00:00 de hoy hasta las 00:00 de mañana, contra ayer.
    - semana: desde el lunes hasta mañana, contra el mismo número de días de
            la semana anterior arrancando en su lunes (fase 8).
    - mes:  desde el día 1 del mes hasta mañana, contra el mismo número de
            días del mes anterior arrancando en su día 1.
    - anio: desde el 1 de enero hasta mañana, contra el mismo número de días
            del año anterior arrancando en su 1 de enero.
    """
    if periodo not in PERIODOS:
        raise ValueError(f"Periodo desconocido: {periodo}")
    hoy = inicio_de_dia(a_hora_negocio(ahora or ahora_utc()))
    manana = hoy + timedelta(days=1)

    if periodo == "hoy":
        desde, desde_anterior = hoy, hoy - timedelta(days=1)
    elif periodo == "semana":
        desde = hoy - timedelta(days=hoy.weekday())
        desde_anterior = desde - timedelta(days=7)
    elif periodo == "mes":
        desde = hoy.replace(day=1)
        desde_anterior = avanzar_meses(desde, -1)
    else:
        desde = hoy.replace(month=1, day=1)
        desde_anterior = desde.replace(year=desde.year - 1)

    # El tramo anterior mide lo mismo que el actual; el desfase es constante,
    # así que pasarlos a UTC no cambia ninguno de los dos largos.
    largo = manana - desde
    return Ventana(
        periodo,
        a_utc(desde),
        a_utc(manana),
        a_utc(desde_anterior),
        a_utc(desde_anterior + largo),
    )


@dataclass(frozen=True)
class RangoGrafica:
    """Serie de la gráfica: `puntos` buckets de tamaño `unidad`, terminando en
    el bucket que contiene a `ahora`, más el tramo anterior del mismo largo.

    Los buckets son horas/días/meses de BOGOTÁ; todos los instantes que expone
    (`desde`, `hasta`, `inicios()`...) están en UTC naive. La aritmética de
    meses se hace en hora de Bogotá, porque un mes de Bogotá empieza a las
    05:00 UTC del día 1."""

    clave: str
    unidad: str
    puntos: int
    desde: datetime
    hasta: datetime
    desde_anterior: datetime

    @property
    def unidad_sql(self) -> str:
        return UNIDAD_SQL[self.unidad]

    def _avanzar(self, inicio_utc: datetime, n: int) -> datetime:
        return a_utc(avanzar_bucket(a_hora_negocio(inicio_utc), self.unidad, n))

    def inicios(self) -> list[datetime]:
        return [self._avanzar(self.desde, i) for i in range(self.puntos)]

    def inicios_anteriores(self) -> list[datetime]:
        return [self._avanzar(self.desde_anterior, i) for i in range(self.puntos)]

    def siguiente_inicio(self) -> datetime:
        """El bucket que viene: dónde se dibuja la proyección."""
        return self._avanzar(self.desde, self.puntos)


def rango_de_grafica(clave: str, ahora: datetime | None = None) -> RangoGrafica:
    if clave not in FORMA_DE_RANGO:
        raise ValueError(f"Rango de gráfica desconocido: {clave}")
    unidad, puntos = FORMA_DE_RANGO[clave]
    ultimo = inicio_de_bucket(a_hora_negocio(ahora or ahora_utc()), unidad)
    desde = avanzar_bucket(ultimo, unidad, -(puntos - 1))
    hasta = avanzar_bucket(ultimo, unidad, 1)
    desde_anterior = avanzar_bucket(desde, unidad, -puntos)
    return RangoGrafica(clave, unidad, puntos, a_utc(desde), a_utc(hasta), a_utc(desde_anterior))


def proyectar(valores: list[float]) -> float:
    """
    Regresión lineal simple: devuelve el valor estimado del punto siguiente
    (x = n). Con menos de tres puntos no hay tendencia que valga, así que cae
    al promedio; si todos los x son iguales, también. Nunca negativa: un
    negocio no puede vender menos que nada.
    """
    n = len(valores)
    if n == 0:
        return 0.0
    if n < 3:
        return max(0.0, sum(valores) / n)
    xs = range(n)
    media_x = sum(xs) / n
    media_y = sum(valores) / n
    var_x = sum((x - media_x) ** 2 for x in xs)
    if var_x == 0:
        return max(0.0, media_y)
    pendiente = sum((x - media_x) * (y - media_y) for x, y in zip(xs, valores)) / var_x
    return max(0.0, media_y + pendiente * (n - media_x))


def variacion(actual: float, anterior: float) -> float | None:
    """Porcentaje de cambio, o None cuando no hay base con la que comparar:
    sin periodo anterior un porcentaje no significa nada y la pantalla debe
    poder no mostrar nada en vez de un '+100 %' inventado."""
    if not anterior:
        return None
    return round((actual - anterior) / anterior * 100, 1)
