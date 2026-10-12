"""
Panel del dashboard con los datos REALES del tenant.

Dos endpoints independientes, porque en la pantalla son dos controles
distintos: /dashboard/panel (píldoras Hoy/Mes/Año, las cifras) y
/dashboard/serie (píldoras 1D/1S/1M/6M/1A, la gráfica). Mover uno no debe
obligar a volver a pedir el otro, y ninguno debe filtrar datos de otra empresa.
"""
from datetime import datetime, timedelta

import pytest

from tests.nombres import letras

from app.modules.dashboard import router as router_dashboard
from app.modules.dashboard.periodos import (
    PERIODOS,
    RANGOS_GRAFICA,
    ahora_utc,
    avanzar_meses,
    proyectar,
    rango_de_grafica,
    variacion,
    ventana_de_periodo,
)
from tests.conftest import comprar as comprar_insumos, crear_insumo, crear_plato

URL_PANEL = "/api/v1/dashboard/panel"
URL_SERIE = "/api/v1/dashboard/serie"


@pytest.fixture()
def sesion(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    return client, auth_headers_factory(admin)


def crear_categoria(client, headers, nombre):
    resp = client.post("/api/v1/catalogo/categorias", headers=headers, json={"nombre": nombre})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def crear_producto(client, headers, nombre, sku, precio="1000", categoria_id=None, grupo=None):
    """Plato cuya receta gasta una unidad del insumo "Insumo de <nombre>"."""
    insumo = crear_insumo(client, headers, f"Insumo de {nombre}", grupo=grupo)
    extra = {"categoria_id": categoria_id} if categoria_id else {}
    return crear_plato(client, headers, nombre, precio, receta=[(insumo["id"], "1", "unidad")], sku=sku, **extra)


def comprar(client, headers, producto_id, cantidad, precio="500", fecha=None):
    """Compra confirmada del insumo del plato: la única vía por la que entra existencia."""
    plato = client.get(f"/api/v1/catalogo/productos/{producto_id}", headers=headers).json()
    return comprar_insumos(
        client, headers, [(plato["receta"][0]["insumo_id"], cantidad, "unidad", precio)],
        fecha=(fecha or ahora_utc()).isoformat(timespec="seconds"),
    )


def vender(client, headers, producto_id, cantidad, precio="1000", fecha=None, cliente="Cliente Uno"):
    venta = client.post(
        "/api/v1/ventas/ventas",
        headers=headers,
        json={
            "cliente_nombre": cliente,
            "fecha": (fecha or ahora_utc()).isoformat(timespec="seconds"),
            "items": [{"producto_id": producto_id, "cantidad": cantidad, "precio_unitario": precio}],
        },
    ).json()
    resp = client.post(f"/api/v1/ventas/ventas/{venta['id']}/confirmar", headers=headers)
    assert resp.status_code == 200, resp.json()
    return resp.json()


# =====================================================================
# Aritmética de ventanas (sin base de datos)
# =====================================================================
# Los relojes de estas pruebas van en UTC naive (lo que da ahora_utc()). La
# medianoche de Bogotá (UTC-5) son las 05:00 UTC: por eso los límites
# esperados caen a las 5.
def test_el_periodo_se_compara_contra_el_mismo_numero_de_dias():
    """Comparar 25 días de septiembre contra los 31 de agosto inventaría una
    caída. El tramo anterior tiene que medir lo mismo que el actual."""
    v = ventana_de_periodo("mes", datetime(2026, 9, 25, 14, 30))  # 09:30 en Bogotá
    assert v.desde == datetime(2026, 9, 1, 5)
    assert v.hasta == datetime(2026, 9, 26, 5)
    assert v.desde_anterior == datetime(2026, 8, 1, 5)
    assert v.hasta_anterior == datetime(2026, 8, 26, 5)
    assert (v.hasta - v.desde) == (v.hasta_anterior - v.desde_anterior)


def test_hoy_se_compara_contra_ayer():
    v = ventana_de_periodo("hoy", datetime(2026, 9, 25, 23, 59))  # 18:59 en Bogotá
    assert v.desde == datetime(2026, 9, 25, 5)
    assert v.hasta == datetime(2026, 9, 26, 5)
    assert v.desde_anterior == datetime(2026, 9, 24, 5)
    assert v.hasta_anterior == datetime(2026, 9, 25, 5)


def test_anio_se_compara_contra_el_mismo_tramo_del_anio_pasado():
    v = ventana_de_periodo("anio", datetime(2026, 9, 25, 8, 0))
    assert v.desde == datetime(2026, 1, 1, 5)
    assert v.desde_anterior == datetime(2025, 1, 1, 5)
    assert (v.hasta - v.desde) == (v.hasta_anterior - v.desde_anterior)


# --- Día calendario de Colombia (decisión del 2026-09-30) ---------------
# 2026-09-30 21:00 en Bogotá = 2026-10-01 02:00 UTC. Para UTC ya es 1 de
# octubre; para el negocio sigue siendo 30 de septiembre.
NOCHE_BOGOTA_UTC = datetime(2026, 10, 1, 2, 0)


def test_hoy_es_el_dia_de_bogota_aunque_utc_ya_vaya_en_el_siguiente():
    v = ventana_de_periodo("hoy", NOCHE_BOGOTA_UTC)
    assert v.desde == datetime(2026, 9, 30, 5)      # 00:00 del 30 en Bogotá
    assert v.hasta == datetime(2026, 10, 1, 5)      # 00:00 del 1 en Bogotá
    venta_10_am_bogota = datetime(2026, 9, 30, 15)  # 10:00 en Bogotá
    assert v.desde <= venta_10_am_bogota < v.hasta
    assert v.desde_anterior == datetime(2026, 9, 29, 5)
    assert v.hasta_anterior == v.desde


@pytest.mark.parametrize("periodo", PERIODOS)
@pytest.mark.parametrize(
    "ahora",
    [NOCHE_BOGOTA_UTC, datetime(2026, 3, 1, 4, 59), datetime(2026, 1, 1, 4, 0)],
)
def test_el_tramo_anterior_mide_lo_mismo_en_hora_de_bogota(periodo, ahora):
    v = ventana_de_periodo(periodo, ahora)
    assert (v.hasta - v.desde) == (v.hasta_anterior - v.desde_anterior)
    assert v.desde <= ahora < v.hasta


def test_mes_en_la_noche_del_ultimo_dia_sigue_siendo_el_mes_de_bogota():
    """A las 21:00 del 30 de septiembre UTC ya está en octubre: el mes tiene
    que seguir siendo septiembre completo, contra los 30 primeros días de
    agosto."""
    v = ventana_de_periodo("mes", NOCHE_BOGOTA_UTC)
    assert v.desde == datetime(2026, 9, 1, 5)
    assert v.hasta == datetime(2026, 10, 1, 5)
    assert v.desde_anterior == datetime(2026, 8, 1, 5)
    assert v.hasta_anterior == datetime(2026, 8, 31, 5)


def test_la_primera_hora_utc_del_mes_o_del_anio_aun_es_la_anterior_en_bogota():
    # 1 de marzo 04:59 UTC = 28 de febrero 23:59 en Bogotá.
    v = ventana_de_periodo("mes", datetime(2026, 3, 1, 4, 59))
    assert v.desde == datetime(2026, 2, 1, 5)
    assert v.hasta == datetime(2026, 3, 1, 5)
    # 1 de enero 04:00 UTC = 31 de diciembre 23:00 en Bogotá.
    v = ventana_de_periodo("anio", datetime(2026, 1, 1, 4, 0))
    assert v.desde == datetime(2025, 1, 1, 5)
    assert v.hasta == datetime(2026, 1, 1, 5)


@pytest.mark.parametrize(
    "clave,primero,ultimo,siguiente",
    [
        # 24 horas de Bogotá: de las 22:00 del 29 a la hora 21:00 del 30.
        ("1d", datetime(2026, 9, 30, 3), datetime(2026, 10, 1, 2), datetime(2026, 10, 1, 3)),
        ("1s", datetime(2026, 9, 24, 5), datetime(2026, 9, 30, 5), datetime(2026, 10, 1, 5)),
        ("1m", datetime(2026, 9, 1, 5), datetime(2026, 9, 30, 5), datetime(2026, 10, 1, 5)),
        ("6m", datetime(2026, 4, 1, 5), datetime(2026, 9, 1, 5), datetime(2026, 10, 1, 5)),
        ("1a", datetime(2025, 10, 1, 5), datetime(2026, 9, 1, 5), datetime(2026, 10, 1, 5)),
    ],
)
def test_los_buckets_de_la_grafica_son_los_de_bogota(clave, primero, ultimo, siguiente):
    """El último bucket es el 30 de septiembre / septiembre (de Bogotá), no el
    1 de octubre que diría UTC; la proyección cae en el bucket siguiente."""
    r = rango_de_grafica(clave, NOCHE_BOGOTA_UTC)
    assert r.inicios()[0] == primero
    assert r.inicios()[-1] == ultimo
    assert r.siguiente_inicio() == siguiente == r.hasta
    assert r.inicios_anteriores()[-1] < r.desde


@pytest.mark.parametrize(
    "clave,unidad,puntos",
    [("1d", "hora", 24), ("1s", "day", 7), ("1m", "day", 30), ("6m", "month", 6), ("1a", "month", 12)],
)
def test_cada_rango_de_grafica_tiene_su_forma(clave, unidad, puntos):
    r = rango_de_grafica(clave, datetime(2026, 9, 25, 14, 30))
    assert (r.unidad, r.puntos) == (unidad, puntos)
    assert len(r.inicios()) == puntos
    assert len(r.inicios_anteriores()) == puntos
    # El tramo anterior mide exactamente lo mismo y termina donde empieza el actual.
    assert r.inicios_anteriores()[-1] < r.desde
    assert r.siguiente_inicio() == r.hasta


def test_avanzar_meses_no_se_sale_del_mes():
    assert avanzar_meses(datetime(2026, 3, 31), -1) == datetime(2026, 2, 28)
    assert avanzar_meses(datetime(2026, 1, 31), 1) == datetime(2026, 2, 28)


def test_la_proyeccion_sigue_la_tendencia_y_nunca_es_negativa():
    assert proyectar([100, 200, 300, 400]) == pytest.approx(500)
    # Tendencia a la baja fuerte: el siguiente punto daría negativo, se corta en 0.
    assert proyectar([300, 150, 10]) == 0.0
    # Sin datos no hay proyección; con uno o dos puntos, el promedio.
    assert proyectar([]) == 0.0
    assert proyectar([80, 120]) == pytest.approx(100)


def test_sin_periodo_anterior_no_hay_variacion_inventada():
    assert variacion(500, 0) is None
    assert variacion(150, 100) == 50.0
    assert variacion(50, 100) == -50.0


# =====================================================================
# /dashboard/panel
# =====================================================================
def test_panel_sin_token(client):
    assert client.get(URL_PANEL).status_code == 401


def test_panel_rechaza_un_periodo_inventado(sesion):
    client, headers = sesion
    assert client.get(f"{URL_PANEL}?periodo=semana", headers=headers).status_code == 422


@pytest.mark.parametrize("periodo", PERIODOS)
def test_panel_responde_en_vacio_sin_romperse(sesion, periodo):
    """Un tenant recién creado no tiene nada: el panel debe devolver ceros y
    listas vacías, no un 500 ni valores nulos que la pantalla no sepa pintar."""
    client, headers = sesion
    body = client.get(f"{URL_PANEL}?periodo={periodo}", headers=headers).json()

    assert body["periodo"] == periodo
    assert body["totales"]["ventas"] == 0
    assert body["totales"]["ventas_variacion"] is None
    assert body["mas_vendidos"] == []
    assert body["inventario"]["categorias"] == []
    assert body["proyeccion"]["ventas"] == 0
    assert len(body["proyeccion"]["historial"]) == 6


def test_panel_suma_solo_lo_del_periodo_y_calcula_la_variacion(sesion):
    client, headers = sesion
    ahora = ahora_utc()
    ayer = ahora - timedelta(days=1)

    producto = crear_producto(client, headers, "Silla ejecutiva", "SKU-SILLA", precio="1000")
    comprar(client, headers, producto["id"], 100, fecha=ahora)

    vender(client, headers, producto["id"], 4, precio="1000", fecha=ayer)   # 4.000 ayer
    vender(client, headers, producto["id"], 6, precio="1000", fecha=ahora)  # 6.000 hoy

    body = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()
    t = body["totales"]

    assert t["ventas"] == 6000.0
    assert t["ventas_anterior"] == 4000.0
    assert t["ventas_variacion"] == 50.0
    assert t["numero_ventas"] == 1
    assert t["productos_vendidos"] == 6
    assert t["numero_clientes"] == 1


def test_panel_cuenta_clientes_distintos_sin_importar_mayusculas(sesion):
    client, headers = sesion
    producto = crear_producto(client, headers, "Lampara Onix", "SKU-LAMP")
    comprar(client, headers, producto["id"], 50)

    vender(client, headers, producto["id"], 1, cliente="Maria Perez")
    vender(client, headers, producto["id"], 1, cliente="maria perez")
    vender(client, headers, producto["id"], 1, cliente="Juan Gomez")

    body = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()
    assert body["totales"]["numero_clientes"] == 2


def test_mas_vendidos_trae_categoria_monto_y_variacion(sesion):
    client, headers = sesion
    ahora = ahora_utc()
    ayer = ahora - timedelta(days=1)

    mobiliario = crear_categoria(client, headers, "Mobiliario")
    producto = crear_producto(client, headers, "Silla Roble", "SKU-ROBLE", categoria_id=mobiliario["id"])
    comprar(client, headers, producto["id"], 100)

    vender(client, headers, producto["id"], 2, precio="1000", fecha=ayer)   # 2.000 ayer
    vender(client, headers, producto["id"], 3, precio="1000", fecha=ahora)  # 3.000 hoy

    body = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()
    top = body["mas_vendidos"]

    assert len(top) == 1
    assert top[0]["nombre"] == "Silla Roble"
    assert top[0]["categoria"] == "Mobiliario"
    assert top[0]["unidades"] == 3
    assert top[0]["monto"] == 3000.0
    assert top[0]["variacion"] == 50.0


def test_mas_vendidos_excluye_lo_que_solo_se_vendio_en_el_periodo_anterior(sesion):
    """Un producto sin ventas en el tramo actual no puede aparecer como
    'más vendido' del tramo actual, aunque vendiera mucho antes."""
    client, headers = sesion
    ayer = ahora_utc() - timedelta(days=1)

    viejo = crear_producto(client, headers, "Producto Viejo", "SKU-VIEJO")
    nuevo = crear_producto(client, headers, "Producto Nuevo", "SKU-NUEVO")
    comprar(client, headers, viejo["id"], 50)
    comprar(client, headers, nuevo["id"], 50)

    vender(client, headers, viejo["id"], 20, fecha=ayer)
    vender(client, headers, nuevo["id"], 1)

    body = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()
    nombres = [p["nombre"] for p in body["mas_vendidos"]]
    assert nombres == ["Producto Nuevo"]


def test_mas_vendidos_se_limita_a_los_que_caben_en_la_pantalla(sesion):
    client, headers = sesion
    for i in range(6):
        producto = crear_producto(client, headers, f"Producto {letras(i)}", f"SKU-TOPE-{i}")
        comprar(client, headers, producto["id"], 50)
        vender(client, headers, producto["id"], i + 1)

    body = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()
    assert len(body["mas_vendidos"]) == 4
    # Ordenados de más a menos unidades.
    unidades = [p["unidades"] for p in body["mas_vendidos"]]
    assert unidades == sorted(unidades, reverse=True)


def test_inventario_arma_la_rejilla_por_grupo_de_insumo(sesion):
    """El inventario es de insumos, valorado a COSTO, agrupado por su grupo;
    "vendido" es el costo de lo que salió por ventas en el periodo."""
    client, headers = sesion
    olla = crear_producto(client, headers, "Sopa", "SKU-SOPA", precio="1000", grupo="Cocina")
    toalla = crear_producto(client, headers, "Postre", "SKU-POSTRE", precio="100", grupo="Bodega")
    comprar(client, headers, olla["id"], 10, precio="500")   # 10 x 500 = 5.000 a costo
    comprar(client, headers, toalla["id"], 20, precio="500")  # 20 x 500 = 10.000 a costo
    vender(client, headers, olla["id"], 2, precio="1000")    # salen 2 x 500 = 1.000 a costo

    inv = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()["inventario"]
    assert inv["insumos_activos"] == 2
    assert inv["valor_inventario"] == 8 * 500 + 20 * 500

    por_nombre = {c["nombre"]: c for c in inv["categorias"]}
    assert list(por_nombre) == ["Bodega", "Cocina"]  # ordenados por valor
    assert por_nombre["Cocina"]["valor"] == 4000.0
    assert por_nombre["Cocina"]["unidades"] == 1  # un insumo en el grupo
    assert por_nombre["Cocina"]["vendido"] == 1000.0
    assert por_nombre["Bodega"]["vendido"] == 0.0
    assert por_nombre["Bodega"]["variacion"] is None  # sin base anterior


def test_panel_aislado_por_tenant(client, tenant_factory, usuario_factory, auth_headers_factory):
    """La regla de oro del multi-tenant: las cifras de una empresa no pueden
    aparecer en el panel de otra."""
    tenant_a = tenant_factory(nombre_empresa="Empresa A")
    tenant_b = tenant_factory(nombre_empresa="Empresa B")
    headers_a = auth_headers_factory(usuario_factory(tenant_a))
    headers_b = auth_headers_factory(usuario_factory(tenant_b))

    producto = crear_producto(client, headers_a, "Solo de A", "SKU-A")
    comprar(client, headers_a, producto["id"], 10)
    vender(client, headers_a, producto["id"], 5, precio="1000")

    body_a = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers_a).json()
    body_b = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers_b).json()

    assert body_a["totales"]["ventas"] == 5000.0
    assert body_b["totales"]["ventas"] == 0
    assert body_b["mas_vendidos"] == []
    assert body_b["inventario"]["valor_inventario"] == 0


# =====================================================================
# /dashboard/serie
# =====================================================================
def test_serie_sin_token(client):
    assert client.get(URL_SERIE).status_code == 401


def test_serie_rechaza_un_rango_inventado(sesion):
    client, headers = sesion
    assert client.get(f"{URL_SERIE}?rango=3s", headers=headers).status_code == 422


@pytest.mark.parametrize("rango", RANGOS_GRAFICA)
def test_serie_devuelve_la_forma_del_rango_aunque_no_haya_datos(sesion, rango):
    """La gráfica necesita SIEMPRE el mismo número de puntos: si faltaran, la
    pantalla tendría que inventar el eje."""
    client, headers = sesion
    esperados = rango_de_grafica(rango).puntos

    body = client.get(f"{URL_SERIE}?rango={rango}", headers=headers).json()

    assert body["rango"] == rango
    assert len(body["puntos"]) == esperados
    assert all(p["actual"] == 0 and p["anterior"] == 0 for p in body["puntos"])
    assert body["proyeccion"]["valor"] == 0
    # Cada punto dice a qué instante corresponde, en ISO: la etiqueta legible
    # la arma el frontend.
    assert all("inicio" in p and "inicio_anterior" in p for p in body["puntos"])


def test_serie_diaria_pone_la_venta_en_su_dia_y_la_anterior_en_el_tramo_previo(sesion):
    client, headers = sesion
    ahora = ahora_utc()

    producto = crear_producto(client, headers, "Producto Serie", "SKU-SERIE")
    comprar(client, headers, producto["id"], 100)
    vender(client, headers, producto["id"], 3, precio="1000", fecha=ahora)                      # hoy
    vender(client, headers, producto["id"], 2, precio="1000", fecha=ahora - timedelta(days=7))  # tramo anterior

    body = client.get(f"{URL_SERIE}?rango=1s", headers=headers).json()
    puntos = body["puntos"]

    assert len(puntos) == 7
    assert puntos[-1]["actual"] == 3000.0     # último día del tramo actual
    assert puntos[-1]["anterior"] == 2000.0   # mismo día del tramo anterior
    assert sum(p["actual"] for p in puntos) == 3000.0
    assert sum(p["anterior"] for p in puntos) == 2000.0


def test_serie_mensual_agrupa_por_mes(sesion):
    client, headers = sesion
    ahora = ahora_utc()

    producto = crear_producto(client, headers, "Producto Mes", "SKU-MES")
    comprar(client, headers, producto["id"], 100)
    vender(client, headers, producto["id"], 1, precio="1000", fecha=ahora)
    vender(client, headers, producto["id"], 1, precio="1000", fecha=ahora)

    body = client.get(f"{URL_SERIE}?rango=6m", headers=headers).json()
    assert body["unidad"] == "month"
    assert len(body["puntos"]) == 6
    assert body["puntos"][-1]["actual"] == 2000.0


def test_serie_proyecta_un_bucket_hacia_adelante(sesion):
    """La proyección es un punto MÁS, fuera de la serie, con su propio
    instante: así la pantalla puede dibujarla punteada y distinguible."""
    client, headers = sesion
    body = client.get(f"{URL_SERIE}?rango=1m", headers=headers).json()

    ultimo = body["puntos"][-1]["inicio"]
    assert body["proyeccion"]["inicio"] > ultimo


# =====================================================================
# Día calendario de Bogotá, de punta a punta (reloj fijo)
# =====================================================================
# Un año en el pasado, para que la validación "fecha no futura" del registro
# de ventas no dependa de la hora en que corre la suite.
# 2025-09-30 21:00 en Bogotá = 2025-10-01 02:00 UTC.
RELOJ_NOCHE = datetime(2025, 10, 1, 2, 0)


@pytest.fixture()
def con_ventas_de_fin_de_mes(sesion, monkeypatch):
    monkeypatch.setattr(router_dashboard, "ahora_utc", lambda: RELOJ_NOCHE)
    client, headers = sesion
    producto = crear_producto(client, headers, "Mesa Nogal", "SKU-NOCHE")
    comprar(client, headers, producto["id"], 100, fecha=datetime(2025, 8, 1, 12))
    vender(client, headers, producto["id"], 3, fecha=datetime(2025, 9, 30, 15))  # 30 sep 10:00 Bogotá
    vender(client, headers, producto["id"], 2, fecha=datetime(2025, 9, 30, 4))   # 29 sep 23:00 Bogotá
    vender(client, headers, producto["id"], 7, fecha=datetime(2025, 9, 1, 3))    # 31 ago 22:00 Bogotá
    return client, headers


def test_a_las_9_pm_la_venta_de_la_manana_sigue_en_hoy(con_ventas_de_fin_de_mes):
    client, headers = con_ventas_de_fin_de_mes

    hoy = client.get(f"{URL_PANEL}?periodo=hoy", headers=headers).json()
    assert hoy["ventana"]["desde"] == "2025-09-30T05:00:00"
    assert hoy["totales"]["ventas"] == 3000.0           # la de las 10 a. m.
    assert hoy["totales"]["ventas_anterior"] == 2000.0  # la de las 11 p. m. de ayer


def test_el_mes_del_panel_es_el_de_bogota_en_la_ultima_noche(con_ventas_de_fin_de_mes):
    """Para UTC ya es octubre; para el negocio el mes es septiembre, y la
    venta del 31 de agosto a las 10 p. m. es del mes anterior."""
    client, headers = con_ventas_de_fin_de_mes

    mes = client.get(f"{URL_PANEL}?periodo=mes", headers=headers).json()
    assert mes["ventana"]["desde"] == "2025-09-01T05:00:00"
    assert mes["ventana"]["hasta"] == "2025-10-01T05:00:00"
    assert mes["totales"]["ventas"] == 5000.0
    # Septiembre (30 días) se compara contra el 1-30 de agosto de Bogotá: la
    # venta del 31 de agosto queda fuera de ESE tramo, aunque es de agosto.
    assert mes["ventana"]["hasta_anterior"] == "2025-08-31T05:00:00"
    assert mes["totales"]["ventas_anterior"] == 0.0
    # La proyección también va por meses de Bogotá: septiembre es el mes en
    # curso (y el 30 es su último día, así que no se extrapola).
    assert mes["proyeccion"]["mes"] == "2025-10-01"
    assert [h["ventas"] for h in mes["proyeccion"]["historial"]][-2:] == [7000.0, 5000.0]


def test_la_serie_agrupa_por_hora_dia_y_mes_de_bogota(con_ventas_de_fin_de_mes):
    client, headers = con_ventas_de_fin_de_mes

    semana = client.get(f"{URL_SERIE}?rango=1s", headers=headers).json()
    por_dia = {p["inicio"]: p["actual"] for p in semana["puntos"]}
    assert semana["puntos"][-1]["inicio"] == "2025-09-30T05:00:00"
    assert por_dia["2025-09-30T05:00:00"] == 3000.0
    assert por_dia["2025-09-29T05:00:00"] == 2000.0
    assert semana["proyeccion"]["inicio"] == "2025-10-01T05:00:00"

    dia = client.get(f"{URL_SERIE}?rango=1d", headers=headers).json()
    por_hora = {p["inicio"]: p["actual"] for p in dia["puntos"]}
    assert por_hora["2025-09-30T15:00:00"] == 3000.0  # la hora 10-11 a. m. de Bogotá
    assert por_hora["2025-09-30T04:00:00"] == 2000.0  # la hora 11 p. m.-12 a. m. del 29

    seis = client.get(f"{URL_SERIE}?rango=6m", headers=headers).json()
    por_mes = {p["inicio"]: p["actual"] for p in seis["puntos"]}
    assert seis["puntos"][-1]["inicio"] == "2025-09-01T05:00:00"
    assert por_mes["2025-09-01T05:00:00"] == 5000.0
    assert por_mes["2025-08-01T05:00:00"] == 7000.0
    assert seis["proyeccion"]["inicio"] == "2025-10-01T05:00:00"


def test_serie_aislada_por_tenant(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant_a = tenant_factory()
    tenant_b = tenant_factory()
    headers_a = auth_headers_factory(usuario_factory(tenant_a))
    headers_b = auth_headers_factory(usuario_factory(tenant_b))

    producto = crear_producto(client, headers_a, "Solo de A", "SKU-SERIE-A")
    comprar(client, headers_a, producto["id"], 10)
    vender(client, headers_a, producto["id"], 5, precio="1000")

    body_b = client.get(f"{URL_SERIE}?rango=1s", headers=headers_b).json()
    assert all(p["actual"] == 0 for p in body_b["puntos"])
