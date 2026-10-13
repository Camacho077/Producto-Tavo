import uuid
"""
MÓDULO IA — sugerencias calculadas con los datos reales del tenant
(app/modules/ia/analisis.py). Restaurante (2026-10-12): el inventario es de
INSUMOS (consumo por receta) y el costo de cada plato sale de su receta. Cada
regla se prueba con datos creados por la API real y se comprueba que la
sugerencia dice POR QUÉ y con QUÉ cifras; sin datos, que lo diga.
"""
from datetime import timedelta

import pytest

from app.core.tiempo import ahora_utc
from app.core.validaciones import digito_verificacion_nit
from app.modules.ia import analisis
from app.modules.catalogo.models import Producto
from app.modules.inventario.models import Insumo
from tests.conftest import vender as vender_orden

URL = "/api/v1/ia/sugerencias"
API = "/api/v1"


# La sesión de la base de la prueba en curso: `vender` la usa para llevar la
# venta a su fecha.
_DB = {}


@pytest.fixture(autouse=True)
def _sesion_db(db_session):
    _DB["db"] = db_session


@pytest.fixture()
def sesion(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    return client, auth_headers_factory(admin), tenant


def nit(base: str) -> str:
    return f"{base}-{digito_verificacion_nit(base)}"


def proveedor(client, h, razon, base_nit):
    r = client.post(f"{API}/compras/proveedores", headers=h, json={
        "tipo_persona": "juridica", "nit": nit(base_nit), "razon_social": razon, "representante_nombre": "Ana Prueba",
    })
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def plato(client, h, nombre, precio="1000", minimo="0", unidad="unidad"):
    """Plato que gasta UNA unidad de su insumo del mismo nombre. Devuelve
    (id del plato, id del insumo)."""
    insumo = client.post(f"{API}/inventario/insumos", headers=h, json={"nombre": nombre, "unidad": unidad, "minimo": minimo}).json()
    p = client.post(f"{API}/catalogo/productos", headers=h, json={
        "nombre": f"Plato de {nombre}", "precio": precio, "receta": [{"insumo_id": insumo["id"], "cantidad": "1", "unidad": unidad}],
    })
    assert p.status_code == 201, p.json()
    return p.json()["id"], insumo["id"]


def comprar(client, h, prov, insumo_id, cantidad, costo, fecha, unidad="unidad"):
    r = client.post(f"{API}/compras/compras", headers=h, json={
        "proveedor_id": prov, "fecha": fecha.isoformat(timespec="seconds"), "confirmar": True,
        "items": [{"insumo_id": insumo_id, "cantidad": str(cantidad), "unidad": unidad, "precio_unitario": str(costo)}],
    })
    assert r.status_code == 201, r.json()


def vender(client, h, pid, cantidad, fecha):
    vender_orden(client, h, [(pid, cantidad)], fecha=fecha, db=_DB["db"])


def seccion(cuerpo, clave):
    return next(s for s in cuerpo["secciones"] if s["clave"] == clave)


def base_de_ventas(client, h, ahora, prov):
    """Historia mínima para que haya base (5 ventas en 5 días) sin disparar
    otras reglas: un plato de relleno con mucha existencia."""
    relleno, insumo = plato(client, h, "Relleno")
    comprar(client, h, prov, insumo, 10_000, 100, ahora - timedelta(days=200))
    for d in range(1, 6):
        vender(client, h, relleno, 1, ahora - timedelta(days=d * 3))
    return relleno


# =====================================================================
# Sin datos: se dice, no se inventa
# =====================================================================
def test_sin_ventas_lo_dice_en_vez_de_inventar(sesion):
    client, h, _ = sesion
    cuerpo = client.get(URL, headers=h).json()
    assert cuerpo["base"]["suficiente"] is False
    assert "todavía no hay base para estimar ritmos" in cuerpo["base"]["mensaje"]
    for clave in ("alertas", "reponer", "ganadores", "patrones", "rotacion"):
        s = seccion(cuerpo, clave)
        assert s["sugerencias"] == [] and s["sin_datos"]
    assert "Ningún plato tiene receta todavía" in seccion(cuerpo, "precios")["sin_datos"]
    assert "no hay con qué comparar" in seccion(cuerpo, "proveedores")["sin_datos"]
    assert "No se envía ningún dato a servicios externos" in cuerpo["privacidad"]


# =====================================================================
# Insumos: se acabarían pronto y lista de compras
# =====================================================================
def test_quiebre_previsible_y_lista_de_compras_con_su_porque(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    rapido, leche = plato(client, h, "Leche")
    lento, arroz = plato(client, h, "Arroz")
    comprar(client, h, prov, leche, 45, 500, ahora - timedelta(days=200))
    comprar(client, h, prov, arroz, 40, 500, ahora - timedelta(days=200))
    for d in range(10):  # 40 y 30 unidades en 10 días distintos
        vender(client, h, rapido, 4, ahora - timedelta(days=d * 2 + 1))
        vender(client, h, lento, 3, ahora - timedelta(days=d * 2 + 1))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    quiebre = next(s for s in seccion(cuerpo, "alertas")["sugerencias"] if s["tipo"] == "quiebre")
    assert quiebre["nivel"] == "critico"
    assert quiebre["titulo"].startswith("Leche se acabaría hacia el")
    assert "1,333 unidades por día" in quiebre["por_que"]  # 40 / 30 días
    assert {"etiqueta": "Existencia", "valor": "5 unidades"} in quiebre["datos"]
    assert quiebre["enlace"] == {"recurso": "insumo", "id": leche}

    reponer = {s["titulo"]: s for s in seccion(cuerpo, "reponer")["sugerencias"]}
    assert reponer["Comprar Leche"]["nivel"] == "critico"
    assert reponer["Comprar Leche"]["accion"] == "Comprar 35 unidades."  # 40/30 × 30 − 5
    assert reponer["Comprar Arroz"]["nivel"] == "advertencia"  # 10 a 1 por día: 10 días
    assert "Arroz se acabaría" not in str(seccion(cuerpo, "alertas"))


def test_bajo_el_minimo_sin_ritmo_sugiere_el_doble_del_minimo(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    _, queso = plato(client, h, "Queso", minimo="2", unidad="kg")
    comprar(client, h, prov, queso, "500", 28, ahora - timedelta(days=200), unidad="g")
    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    s = next(x for x in seccion(cuerpo, "reponer")["sugerencias"] if x["titulo"] == "Comprar Queso")
    assert "Quedan 500 g y su mínimo es 2 kg" in s["por_que"]
    assert s["accion"] == "Comprar al menos 3,5 kg."


def test_un_insumo_sin_consumo_suficiente_no_recibe_un_ritmo_inventado(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    raro, linterna = plato(client, h, "Linterna")
    comprar(client, h, prov, linterna, 3, 500, ahora - timedelta(days=200))
    vender(client, h, raro, 2, ahora - timedelta(days=1))  # 2 en 1 solo día: no es ritmo

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    assert "Linterna" not in str(seccion(cuerpo, "alertas")) + str(seccion(cuerpo, "reponer"))


# =====================================================================
# Ventas: caídas y ganadores
# =====================================================================
def test_caida_y_ganador_por_plato(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    cae, i_cae = plato(client, h, "Galletas")
    sube, i_sube = plato(client, h, "Cafe")
    comprar(client, h, prov, i_cae, 500, 500, ahora - timedelta(days=200))
    comprar(client, h, prov, i_sube, 500, 500, ahora - timedelta(days=200))
    vender(client, h, cae, 20, ahora - timedelta(days=45))
    vender(client, h, cae, 5, ahora - timedelta(days=5))
    vender(client, h, sube, 5, ahora - timedelta(days=45))
    vender(client, h, sube, 15, ahora - timedelta(days=5))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    caida = next(s for s in seccion(cuerpo, "alertas")["sugerencias"] if s["tipo"] == "caida_producto")
    assert caida["titulo"] == "Plato de Galletas vende 75 % menos"
    assert "Pasó de 20 unidades a 5 unidades" in caida["por_que"]
    ganador = seccion(cuerpo, "ganadores")["sugerencias"][0]
    assert ganador["titulo"] == "Plato de Cafe está ganando"
    assert {"etiqueta": "Variación", "valor": "▲ 200 %"} in ganador["datos"]


# =====================================================================
# Insumos quietos
# =====================================================================
def test_insumo_quieto_con_capital_inmovilizado(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    pid, harina = plato(client, h, "Harina", precio="20000")
    comprar(client, h, prov, harina, 100, 8000, ahora - timedelta(days=90))
    vender(client, h, pid, 2, ahora - timedelta(days=20))
    db_session.query(Insumo).filter(Insumo.id == harina).update({"created_at": ahora - timedelta(days=90)})
    db_session.flush()

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    s = next(x for x in seccion(cuerpo, "rotacion")["sugerencias"] if x["titulo"] == "Harina casi no se gasta")
    assert "Se gastaron 2 unidades en 60 días y quedan 98 unidades" in s["por_que"]
    assert {"etiqueta": "Capital quieto (a costo)", "valor": "$784.000"} in s["datos"]

    sin_costos = analisis.calcular(db_session, tenant.id, ahora, ver_costos=False)
    s2 = next(x for x in seccion(sin_costos, "rotacion")["sugerencias"] if x["titulo"] == "Harina casi no se gasta")
    assert all(d["etiqueta"] != "Capital quieto (a costo)" for d in s2["datos"])
    assert "784.000" not in str(sin_costos)


def test_un_insumo_nuevo_no_esta_quieto(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    _, termo = plato(client, h, "Termo")
    comprar(client, h, prov, termo, 50, 500, ahora - timedelta(days=1))
    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    assert "Termo" not in str(seccion(cuerpo, "rotacion"))


# =====================================================================
# Costo por receta y proveedores (solo con costos.ver)
# =====================================================================
def test_plato_con_costo_alto_y_precio_sugerido(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    _, aceite = plato(client, h, "Aceite", precio="10000")
    comprar(client, h, prov, aceite, 10, 9000, ahora - timedelta(days=10))
    _, azucar = plato(client, h, "Azucar", precio="1000")
    comprar(client, h, prov, azucar, 10, 1200, ahora - timedelta(days=10))
    _, sano = plato(client, h, "Sano", precio="10000")
    comprar(client, h, prov, sano, 10, 2000, ahora - timedelta(days=10))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    precios = {s["titulo"]: s for s in seccion(cuerpo, "precios")["sugerencias"]}
    assert precios["Plato de Azucar se vende por debajo de su costo"]["nivel"] == "critico"
    s = precios["Plato de Aceite tiene un costo del 97 %"]  # 9.000 sobre 9.259 sin impuesto
    assert "Lo que más pesa es Aceite (100 % del costo)" in s["por_que"]
    assert {"etiqueta": "Precio para un costo del 35 %", "valor": "$27.771"} in s["datos"]  # 9.000 / 0,35 × 1,08
    assert "Plato de Sano" not in str(seccion(cuerpo, "precios"))
    # Sin base de ventas igual se calcula: no depende de la historia.
    assert cuerpo["base"]["suficiente"] is False


def test_proveedor_mas_barato_comparando_por_unidad_del_insumo(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    barato = proveedor(client, h, "Mayorista Central", "900123456")
    caro = proveedor(client, h, "Tienda del Barrio", "800197268")
    _, harina = plato(client, h, "Harina", precio="5000", unidad="kg")
    comprar(client, h, barato, harina, 10, 2000, ahora - timedelta(days=40), unidad="kg")
    comprar(client, h, caro, harina, 10000, "2.5", ahora - timedelta(days=5), unidad="g")  # = $2.500 el kg

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    s = seccion(cuerpo, "proveedores")["sugerencias"][0]
    assert s["titulo"] == "Harina: Mayorista Central te sale 20 % más barato"
    assert "le compraste a Tienda del Barrio a $2.500 por kg en promedio" in s["por_que"]
    assert s["enlace"] == {"recurso": "proveedor", "id": barato}


def test_quien_no_ve_costos_no_recibe_costos_ni_proveedores(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h_admin = auth_headers_factory(usuario_factory(tenant))
    prov = proveedor(client, h_admin, "Distribuidora Andina", "900123456")
    _, aceite = plato(client, h_admin, "Aceite", precio="10000")
    comprar(client, h_admin, prov, aceite, 10, 9000, ahora_utc() - timedelta(days=10))
    analista = rol_factory(tenant, nombre="Analista", permisos={"ia": ["ver"], "productos": ["ver"]})
    h = auth_headers_factory(usuario_factory(tenant, rol=analista))

    r = client.get(URL, headers=h)
    assert r.status_code == 200
    cuerpo = r.json()
    for clave in ("precios", "proveedores"):
        s = seccion(cuerpo, clave)
        assert s["sugerencias"] == []
        assert "Tu rol no ve costos ni márgenes" in s["sin_datos"]
    assert "9.000" not in r.text


# =====================================================================
# Patrones de venta (día de la semana y franja horaria, hora de Colombia)
# =====================================================================
def test_patron_de_dia_y_franja(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    pid, pan = plato(client, h, "Pan")
    comprar(client, h, prov, pan, 1000, 300, ahora - timedelta(days=200))
    local = ahora - timedelta(hours=5)
    sabado = (local - timedelta(days=(local.weekday() - 5) % 7 or 7)).replace(hour=15, minute=0, second=0, microsecond=0)
    for semana in range(6):
        dia = sabado - timedelta(weeks=semana) + timedelta(hours=5)  # 15:00 de Bogotá en UTC
        vender(client, h, pid, 5, dia)
        vender(client, h, pid, 5, dia + timedelta(hours=1))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    patrones = {s["tipo"]: s for s in seccion(cuerpo, "patrones")["sugerencias"]}
    assert patrones["patron_dia"]["titulo"] == "Los sábados son tu día fuerte"
    assert "concentran el 100 %" in patrones["patron_dia"]["por_que"]
    assert patrones["patron_hora"]["titulo"].startswith("La hora pico es a las 1")  # 15 o 16:00


def test_pocas_semanas_no_alcanzan_para_un_patron(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    s = seccion(cuerpo, "patrones")
    assert s["sugerencias"] == []
    assert "hacen falta al menos 10 ventas" in s["sin_datos"]


# =====================================================================
# Aislamiento entre empresas
# =====================================================================
def test_nunca_mezcla_datos_de_otra_empresa(client, tenant_factory, usuario_factory, auth_headers_factory):
    a, b = tenant_factory(), tenant_factory()
    h_a, h_b = auth_headers_factory(usuario_factory(a)), auth_headers_factory(usuario_factory(b))
    ahora = ahora_utc()
    prov = proveedor(client, h_a, "Distribuidora Andina", "900123456")
    pid, secreto = plato(client, h_a, "Secreto", precio="10000")
    comprar(client, h_a, prov, secreto, 10, 9500, ahora - timedelta(days=10))
    for d in range(6):
        vender(client, h_a, pid, 1, ahora - timedelta(days=d + 1))

    r = client.get(URL, headers=h_b)
    assert r.status_code == 200
    assert "Secreto" not in r.text and "Distribuidora Andina" not in r.text
    assert r.json()["base"]["ventas"] == 0


# =====================================================================
# Reglas del restaurante (2026-10-12): carta, alzas, mermas, caja, temporadas
# =====================================================================
def test_plato_que_casi_no_se_vende(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    relleno = base_de_ventas(client, h, ahora, prov)
    raro, insumo = plato(client, h, "Postre raro", precio="4000")
    comprar(client, h, prov, insumo, 50, 500, ahora - timedelta(days=200))
    vender(client, h, raro, 1, ahora - timedelta(days=50))
    db_session.query(Producto).filter(Producto.id.in_([raro, relleno])).update({"created_at": ahora - timedelta(days=90)}, synchronize_session=False)
    db_session.commit()
    s = seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=True), "carta")
    titulos = [x["titulo"] for x in s["sugerencias"]]
    assert "Plato de Postre raro casi no se vende" in titulos
    raro_s = next(x for x in s["sugerencias"] if x["titulo"] == "Plato de Postre raro casi no se vende")
    assert "Vendió 0 unidades en 30 días" in raro_s["por_que"] and "última venta" in raro_s["por_que"]


def test_alza_de_un_insumo_y_platos_que_perdieron_margen(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Carnes del Llano", "900765432")
    carne = client.post(f"{API}/inventario/insumos", headers=h, json={"nombre": "Carne", "unidad": "kg"}).json()["id"]
    p = client.post(f"{API}/catalogo/productos", headers=h, json={"nombre": "Hamburguesa", "precio": "13500",
                    "receta": [{"insumo_id": carne, "cantidad": "150", "unidad": "g"}]}).json()
    comprar(client, h, prov, carne, 10, 22000, ahora - timedelta(days=80), unidad="kg")
    comprar(client, h, prov, carne, 10, 28600, ahora - timedelta(days=10), unidad="kg")
    s = seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=True), "alzas")
    alza = s["sugerencias"][0]
    assert alza["titulo"] == "Carne subió 30 % y bajó el margen de 1 plato"
    assert "Hamburguesa (" in alza["por_que"] and alza["enlace"]["recurso"] == "insumo"
    assert p["id"]
    sin_costos = seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=False), "alzas")
    assert sin_costos["sugerencias"] == [] and sin_costos["requiere_costos"]


def test_mermas_fuera_de_lo_normal(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Fruver", "900222333")
    base_de_ventas(client, h, ahora, prov)
    lechuga = client.post(f"{API}/inventario/insumos", headers=h, json={"nombre": "Lechuga", "unidad": "unidad"}).json()["id"]
    comprar(client, h, prov, lechuga, 100, 2500, ahora - timedelta(days=89))
    from app.modules.inventario import schemas as si, services as inv
    from app.modules.seguridad.models import Usuario

    usuario = db_session.query(Usuario).filter(Usuario.tenant_id == tenant.id).first()
    lechuga = uuid.UUID(lechuga)
    inv.registrar_merma(db_session, usuario, lechuga, si.MermaCreate(cantidad=1, unidad="unidad", motivo="vencido"), ahora=ahora - timedelta(days=60))
    for d in range(1, 7):
        inv.registrar_merma(db_session, usuario, lechuga, si.MermaCreate(cantidad=2, unidad="unidad", motivo="danado"), ahora=ahora - timedelta(days=d))
    a = next(x for x in seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=True), "alertas")["sugerencias"] if x["tipo"] == "merma")
    assert a["titulo"] == "Mermas fuera de lo normal: Lechuga"
    assert "6 mermas por 12 unidades" in a["por_que"]
    assert {"etiqueta": "Valor perdido", "valor": "$30.000"} in a["datos"]


def test_diferencias_de_caja_repetidas_en_el_turno_de_una_persona(sesion, db_session, usuario_factory):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    from app.modules.caja import schemas as sc, services as cj

    carla = usuario_factory(tenant, nombre_completo="Carla Ruiz")
    jorge = usuario_factory(tenant, nombre_completo="Jorge Mesa")
    if cj.caja_abierta(db_session, tenant.id):
        abierta = cj.caja_abierta(db_session, tenant.id)
        cj.cerrar(db_session, jorge, sc.CerrarCaja(contado=cj.cuadre(db_session, abierta)["esperado"]))
    for d, quien, faltante in ((9, carla, 2000), (7, jorge, 0), (5, carla, 5000), (3, carla, 3500)):
        cj.abrir(db_session, quien, 100000, ahora=ahora - timedelta(days=d, hours=10))
        cj.cerrar(db_session, quien, sc.CerrarCaja(contado={"efectivo": 100000 - faltante}, motivo_diferencia="Faltó" if faltante else None), ahora=ahora - timedelta(days=d))
    a = next(x for x in seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=True), "alertas")["sugerencias"] if x["tipo"] == "diferencias_caja")
    assert a["titulo"] == "Diferencias de caja repetidas en el turno de Carla Ruiz"
    assert "3 fueron de su turno, por $10.500" in a["por_que"]


def test_semana_fuerte_y_semana_floja(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    pid, insumo = plato(client, h, "Menú", precio="10000")
    comprar(client, h, prov, insumo, 2000, 100, ahora - timedelta(days=200))
    local = ahora - timedelta(hours=5)
    lunes_actual = (local - timedelta(days=local.weekday())).replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(hours=5)
    for semanas in range(1, 11):
        n = 30 if semanas == 5 else 4 if semanas == 1 else 10
        vender(client, h, pid, n, lunes_actual - timedelta(weeks=semanas) + timedelta(days=1))
    tipos = {x["tipo"]: x for x in seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=True), "patrones")["sugerencias"]}
    assert tipos["semana_fuerte"]["titulo"].endswith("vendiste 200 % más de lo normal")
    assert tipos["semana_floja"]["titulo"] == "La semana pasada vendiste 60 % menos que una semana normal"


def test_se_vende_mucho_pero_deja_poco_margen(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    pid, insumo = plato(client, h, "Almuerzo", precio="10800")
    comprar(client, h, prov, insumo, 200, 6000, ahora - timedelta(days=60))
    for d in range(1, 8):
        vender(client, h, pid, 5, ahora - timedelta(days=d))
    s = next(x for x in seccion(analisis.calcular(db_session, tenant.id, ahora, ver_costos=True), "precios")["sugerencias"])
    assert s["titulo"] == "Plato de Almuerzo se vende mucho pero deja poco margen (60 % de costo)" and s["nivel"] == "advertencia"
