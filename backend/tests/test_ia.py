"""
MÓDULO IA — sugerencias calculadas con los datos reales del tenant
(app/modules/ia/analisis.py). Cada regla se prueba con datos creados por la
API real (el stock sale de compras y ventas, nunca a mano) y se comprueba
que la sugerencia dice POR QUÉ y con QUÉ cifras; sin datos, que lo diga.
"""
from datetime import timedelta

import pytest

from app.core.tiempo import ahora_utc
from app.core.validaciones import digito_verificacion_nit
from app.modules.compras.models import Producto
from app.modules.ia import analisis

URL = "/api/v1/ia/sugerencias"


@pytest.fixture()
def sesion(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant, nombre_completo="Ana Admin")
    return client, auth_headers_factory(admin), tenant


def nit(base: str) -> str:
    return f"{base}-{digito_verificacion_nit(base)}"


def proveedor(client, h, razon, base_nit):
    r = client.post("/api/v1/compras/proveedores", headers=h, json={
        "tipo_persona": "juridica", "nit": nit(base_nit), "razon_social": razon, "representante_nombre": "Ana Prueba",
    })
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def producto(client, h, nombre, sku, precio="1000", stock_minimo=0):
    r = client.post("/api/v1/compras/productos", headers=h, json={"nombre": nombre, "sku": sku, "precio": precio, "stock_minimo": stock_minimo})
    assert r.status_code == 201, r.json()
    return r.json()["id"]


def comprar(client, h, prov, pid, cantidad, costo, fecha):
    r = client.post("/api/v1/compras/compras", headers=h, json={
        "proveedor_id": prov, "fecha": fecha.isoformat(timespec="seconds"), "confirmar": True,
        "items": [{"producto_id": pid, "cantidad": cantidad, "precio_unitario": str(costo)}],
    })
    assert r.status_code == 201, r.json()


def vender(client, h, pid, cantidad, fecha, precio="1000"):
    r = client.post("/api/v1/ventas/ventas", headers=h, json={
        "cliente_nombre": "Carlos Cliente", "fecha": fecha.isoformat(timespec="seconds"), "confirmar": True,
        "items": [{"producto_id": pid, "cantidad": cantidad, "precio_unitario": precio}],
    })
    assert r.status_code == 201, r.json()


def seccion(cuerpo, clave):
    return next(s for s in cuerpo["secciones"] if s["clave"] == clave)


def tipos(cuerpo, clave):
    return [s["tipo"] for s in seccion(cuerpo, clave)["sugerencias"]]


def base_de_ventas(client, h, ahora, prov):
    """Historia mínima para que haya base (5 ventas en 5 días) sin disparar
    otras reglas: un producto de relleno con mucho stock."""
    relleno = producto(client, h, "Relleno", "REL-1")
    comprar(client, h, prov, relleno, 10_000, 100, ahora - timedelta(days=200))
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
    assert "Ningún producto tiene costo conocido" in seccion(cuerpo, "precios")["sin_datos"]
    assert "no hay con qué comparar" in seccion(cuerpo, "proveedores")["sin_datos"]
    assert "No se envía ningún dato a servicios externos" in cuerpo["privacidad"]


# =====================================================================
# Stock: quiebres previsibles y reposición
# =====================================================================
def test_quiebre_previsible_y_reposicion_con_su_porque(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    rapido = producto(client, h, "Leche", "LEC-1")
    lento = producto(client, h, "Arroz", "ARR-1")
    comprar(client, h, prov, rapido, 45, 500, ahora - timedelta(days=200))
    comprar(client, h, prov, lento, 40, 500, ahora - timedelta(days=200))
    for d in range(10):  # 40 y 30 unidades en 10 días distintos
        vender(client, h, rapido, 4, ahora - timedelta(days=d * 2 + 1))
        vender(client, h, lento, 3, ahora - timedelta(days=d * 2 + 1))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    quiebre = next(s for s in seccion(cuerpo, "alertas")["sugerencias"] if s["tipo"] == "quiebre")
    assert quiebre["nivel"] == "critico"
    assert quiebre["titulo"].startswith("Leche se agotaría hacia el")
    assert "1,3 unidades por día" in quiebre["por_que"]  # 40 uds / 30 días
    assert {"etiqueta": "Stock actual", "valor": "5 unidades"} in quiebre["datos"]
    assert quiebre["enlace"] == {"recurso": "producto", "id": rapido}

    reponer = {s["titulo"]: s for s in seccion(cuerpo, "reponer")["sugerencias"]}
    assert reponer["Reponer Leche"]["nivel"] == "critico"
    assert reponer["Reponer Leche"]["accion"] == "Comprar 35 unidades."  # ceil(40/30*30 - 5)
    assert reponer["Reponer Arroz"]["nivel"] == "advertencia"  # 10 uds a 1/día: 10 días
    assert "Arroz se agotaría" not in str(seccion(cuerpo, "alertas"))


def test_un_producto_sin_ventas_suficientes_no_recibe_un_ritmo_inventado(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    raro = producto(client, h, "Linterna", "LIN-1")
    comprar(client, h, prov, raro, 3, 500, ahora - timedelta(days=200))
    vender(client, h, raro, 2, ahora - timedelta(days=1))  # 2 uds en 1 día: no es ritmo

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    assert "Linterna" not in str(seccion(cuerpo, "alertas")) + str(seccion(cuerpo, "reponer"))


# =====================================================================
# Ventas: caídas y ganadores
# =====================================================================
def test_caida_y_ganador_por_producto(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    cae = producto(client, h, "Galletas", "GAL-1")
    sube = producto(client, h, "Cafe", "CAF-1")
    comprar(client, h, prov, cae, 500, 500, ahora - timedelta(days=200))
    comprar(client, h, prov, sube, 500, 500, ahora - timedelta(days=200))
    vender(client, h, cae, 20, ahora - timedelta(days=45))
    vender(client, h, cae, 5, ahora - timedelta(days=5))
    vender(client, h, sube, 5, ahora - timedelta(days=45))
    vender(client, h, sube, 15, ahora - timedelta(days=5))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    caida = next(s for s in seccion(cuerpo, "alertas")["sugerencias"] if s["tipo"] == "caida_producto")
    assert caida["titulo"] == "Galletas vende 75 % menos"
    assert "Pasó de 20 unidades a 5 unidades" in caida["por_que"]
    ganador = seccion(cuerpo, "ganadores")["sugerencias"][0]
    assert ganador["titulo"] == "Cafe está ganando"
    assert {"etiqueta": "Variación", "valor": "▲ 200 %"} in ganador["datos"]


# =====================================================================
# Baja rotación
# =====================================================================
def test_baja_rotacion_con_capital_inmovilizado(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    quieto = producto(client, h, "Paraguas", "PAR-1", precio="20000")
    comprar(client, h, prov, quieto, 100, 8000, ahora - timedelta(days=90))
    vender(client, h, quieto, 2, ahora - timedelta(days=20), precio="20000")
    db_session.query(Producto).filter(Producto.id == quieto).update({"created_at": ahora - timedelta(days=90)})
    db_session.flush()

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    s = next(x for x in seccion(cuerpo, "rotacion")["sugerencias"] if x["titulo"] == "Paraguas rota lento")
    assert "Vendió 2 unidades en 60 días y tiene 98 unidades en stock" in s["por_que"]
    assert {"etiqueta": "Capital inmovilizado (a costo)", "valor": "$784.000"} in s["datos"]

    sin_costos = analisis.calcular(db_session, tenant.id, ahora, ver_costos=False)
    s2 = next(x for x in seccion(sin_costos, "rotacion")["sugerencias"] if x["titulo"] == "Paraguas rota lento")
    assert {"etiqueta": "Valor a precio de venta", "valor": "$1.960.000"} in s2["datos"]
    assert "8.000" not in str(sin_costos)


def test_un_producto_nuevo_no_tiene_baja_rotacion(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    base_de_ventas(client, h, ahora, prov)
    nuevo = producto(client, h, "Termo", "TER-1")
    comprar(client, h, prov, nuevo, 50, 500, ahora - timedelta(days=1))
    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    assert "Termo" not in str(seccion(cuerpo, "rotacion"))


# =====================================================================
# Precios y proveedores (solo con permiso de ver costos)
# =====================================================================
def test_margen_bajo_y_precio_sugerido(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    prov = proveedor(client, h, "Distribuidora Andina", "900123456")
    caro = producto(client, h, "Aceite", "ACE-1", precio="10000")
    comprar(client, h, prov, caro, 10, 9000, ahora - timedelta(days=10))
    perdida = producto(client, h, "Azucar", "AZU-1", precio="1000")
    comprar(client, h, prov, perdida, 10, 1200, ahora - timedelta(days=10))

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    precios = {s["titulo"]: s for s in seccion(cuerpo, "precios")["sugerencias"]}
    assert precios["Azucar se vende por debajo del costo"]["nivel"] == "critico"
    aceite = precios["Aceite deja poco margen"]
    assert "margen de 10 %" in aceite["por_que"]
    assert {"etiqueta": "Precio para 25 % de margen", "valor": "$12.000"} in aceite["datos"]
    # Sin base de ventas igual se calcula: no depende de la historia.
    assert cuerpo["base"]["suficiente"] is False


def test_proveedor_con_mejores_condiciones(sesion, db_session):
    client, h, tenant = sesion
    ahora = ahora_utc()
    barato = proveedor(client, h, "Mayorista Central", "900123456")
    caro = proveedor(client, h, "Tienda del Barrio", "800197268")
    pid = producto(client, h, "Harina", "HAR-1", precio="5000")
    comprar(client, h, barato, pid, 10, 2000, ahora - timedelta(days=40))
    comprar(client, h, caro, pid, 10, 2500, ahora - timedelta(days=5))  # la última compra fue al caro

    cuerpo = analisis.calcular(db_session, tenant.id, ahora, ver_costos=True)
    s = seccion(cuerpo, "proveedores")["sugerencias"][0]
    assert s["titulo"] == "Harina: Mayorista Central te sale 20 % más barato"
    assert "le compraste a Tienda del Barrio a $2.500 en promedio" in s["por_que"]
    assert s["enlace"] == {"recurso": "proveedor", "id": barato}


def test_quien_no_ve_compras_no_recibe_costos_ni_proveedores(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h_admin = auth_headers_factory(usuario_factory(tenant))
    prov = proveedor(client, h_admin, "Distribuidora Andina", "900123456")
    pid = producto(client, h_admin, "Aceite", "ACE-1", precio="10000")
    comprar(client, h_admin, prov, pid, 10, 9000, ahora_utc() - timedelta(days=10))
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
    pid = producto(client, h, "Pan", "PAN-1")
    comprar(client, h, prov, pid, 1000, 300, ahora - timedelta(days=200))
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
    assert patrones["patron_hora"]["titulo"].startswith("La franja de 1")  # 13, 14 o 15:00
    assert "15" in patrones["patron_hora"]["titulo"] or "14" in patrones["patron_hora"]["titulo"] or "13" in patrones["patron_hora"]["titulo"]


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
    pid = producto(client, h_a, "Secreto", "SEC-1", precio="10000")
    comprar(client, h_a, prov, pid, 10, 9500, ahora - timedelta(days=10))
    for d in range(6):
        vender(client, h_a, pid, 1, ahora - timedelta(days=d + 1), precio="10000")

    r = client.get(URL, headers=h_b)
    assert r.status_code == 200
    assert "Secreto" not in r.text and "Distribuidora Andina" not in r.text
    assert r.json()["base"]["ventas"] == 0
