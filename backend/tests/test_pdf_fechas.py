"""Las fechas de los PDF van en hora de Colombia (2026-10-13): los instantes
se guardan en UTC sin zona y un cobro de las 6:41 p. m. salía a las 23:41."""
from datetime import datetime, timedelta, timezone

from app.core.pdf import formatear_fecha


def test_un_instante_utc_sin_zona_se_imprime_en_hora_de_colombia():
    assert formatear_fecha(datetime(2026, 10, 12, 23, 41)) == "12/10/2026 18:41"
    assert formatear_fecha(datetime(2026, 10, 13, 2, 15)) == "12/10/2026 21:15"


def test_con_zona_explicita_tambien():
    assert formatear_fecha(datetime(2026, 10, 12, 23, 41, tzinfo=timezone.utc)) == "12/10/2026 18:41"
    assert formatear_fecha(datetime(2026, 10, 12, 18, 41, tzinfo=timezone(timedelta(hours=-5)))) == "12/10/2026 18:41"


def test_sin_fecha():
    assert formatear_fecha(None) == "—"
