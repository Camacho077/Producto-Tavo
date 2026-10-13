"""
Datos de demostración (2026-10-12): Donde Tavo con historia de 90 días y
Café Central como segunda empresa para probar el aislamiento.

La prueba corre EXACTAMENTE `cargar_demo` (con menos días para que tarde
poco) y comprueba lo que la demo promete: las cuentas de cada rol entran con
su contraseña, hoy hay órdenes en todos los estados y la caja está abierta,
el inventario y la utilidad cuadran, y una empresa no ve nada de la otra.
"""
import importlib.util
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from app.core.errors import ConflictError
from app.core.tiempo import ahora_utc
from app.modules.caja import services as caja
from app.modules.caja.models import CajaSesion, Venta, VentaItem
from app.modules.gastos.models import Gasto
from app.modules.inventario.models import Insumo, MovimientoInsumo
from app.modules.ordenes import services as ordenes
from app.modules.ordenes.models import Orden
from app.modules.reportes import consultas

RUTA_SEED = Path(__file__).resolve().parents[2] / "automatizaciones" / "deploy" / "seed_demo.py"
API = "/api/v1"
DIAS = 14


@pytest.fixture(scope="module")
def seed():
    spec = importlib.util.spec_from_file_location("seed_demo", RUTA_SEED)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _ahora(seed):
    """Ahora, o ayer por la tarde si la prueba corre de madrugada (antes de
    las 10 a. m. de Colombia aún no hay órdenes de hoy que mostrar)."""
    ahora = ahora_utc()
    local = ahora + seed.COLOMBIA
    if local.hour < 10:
        ayer = (local - timedelta(days=1)).date()
        return seed.utc(ayer, 17, 0)
    return ahora


def _login(client, correo, clave):
    return client.post(f"{API}/seguridad/login", json={"email": correo, "password": clave})


def test_la_demo_completa(client, db_session, seed):
    ahora = _ahora(seed)
    hoy = (ahora + seed.COLOMBIA).date()
    r = seed.cargar_demo(db_session, ahora=ahora, dias=DIAS, escala=0.6)
    tavo, central = r["donde_tavo"]["tenant"], r["cafe_central"]["tenant"]
    assert tavo.nombre_empresa == "Donde Tavo" and central.nombre_empresa == "Café Central"
    assert not [k for k in r["donde_tavo"]["cuenta"] if k.endswith("rechazada") and not k.startswith("orden")]

    # Cuentas: cada rol entra con su contraseña exacta.
    for correo, clave in (("admin@dondetavo.demo", "Tavo2026*Admin"), ("caja@dondetavo.demo", "Tavo2026*Caja"),
                          ("mesero@dondetavo.demo", "Tavo2026*Mesero"), ("cocina@dondetavo.demo", "Tavo2026*Cocina"),
                          ("admin@cafecentral.demo", "Central2026*Admin")):
        resp = _login(client, correo, clave)
        assert resp.status_code == 200, (correo, resp.text)

    # Hoy: órdenes en todos los estados, mesas libres/ocupadas/por cobrar.
    de_hoy = db_session.query(Orden).filter(Orden.tenant_id == tavo.id, Orden.jornada == hoy).all()
    assert {"abierta", "cobrada", "anulada"} <= {o.estado for o in de_hoy}
    en_cocina = {ordenes.estado_cocina(o) for o in de_hoy}
    assert {"entrante", "en_preparacion", "lista"} <= en_cocina, en_cocina
    assert any(o.estado == "abierta" and o.comandas and all(c.estado == "entregada" for c in o.comandas) for o in de_hoy),         "falta una orden entregada sin cobrar"
    assert db_session.query(Venta).filter(Venta.tenant_id == tavo.id, Venta.estado == "completada").count() > 0
    assert {"libre", "ocupada", "por_cobrar"} <= {m["estado"] for m in ordenes.estado_mesas(db_session, tavo.id)}

    # Caja: abierta hoy y un cierre por cada día anterior con operación.
    abierta = caja.caja_abierta(db_session, tavo.id)
    assert abierta is not None and (abierta.abierta_en + seed.COLOMBIA).date() == hoy
    cierres = db_session.query(CajaSesion).filter(CajaSesion.tenant_id == tavo.id, CajaSesion.estado == "cerrada").all()
    dias_con_ordenes = {j for (j,) in db_session.query(Orden.jornada).filter(Orden.tenant_id == tavo.id, Orden.jornada < hoy).distinct()}
    assert {(c.abierta_en + seed.COLOMBIA).date() for c in cierres} >= dias_con_ordenes

    # Inventario: existencia = compras − consumo − mermas ± ajustes, insumo por insumo.
    suma = defaultdict(Decimal)
    for insumo_id, cantidad in db_session.query(MovimientoInsumo.insumo_id, MovimientoInsumo.cantidad).filter(MovimientoInsumo.tenant_id == tavo.id):
        suma[insumo_id] += Decimal(cantidad)
    insumos = db_session.query(Insumo).filter(Insumo.tenant_id == tavo.id).all()
    assert len(insumos) == 25
    for i in insumos:
        assert Decimal(i.existencia) == suma[i.id], i.nombre
    assert any(Decimal(i.existencia) == 0 for i in insumos), "un insumo debe estar agotado"
    assert sum(1 for i in insumos if Decimal(i.existencia) < Decimal(i.minimo)) >= 3

    # Utilidad real = ventas sin impuesto − costo por receta − gastos.
    desde, hasta = ahora - timedelta(days=DIAS + 2), ahora
    res = consultas.resumen(db_session, tavo.id, desde, hasta)
    ventas = db_session.query(Venta).filter(Venta.tenant_id == tavo.id, Venta.estado == "completada", Venta.fecha >= desde).all()
    ingresos = sum(Decimal(v.subtotal) for v in ventas)
    costo = sum(Decimal(it.cantidad) * Decimal(it.costo_unitario or 0)
                for it in db_session.query(VentaItem).filter(VentaItem.venta_id.in_([v.id for v in ventas])))
    primero, _ = consultas.dias_negocio(desde, hasta)
    gastos = sum(Decimal(g.valor) for g in db_session.query(Gasto).filter(Gasto.tenant_id == tavo.id, Gasto.fecha >= primero, Gasto.fecha <= hoy))
    assert gastos > 0 and costo > 0
    assert Decimal(str(res["utilidad_real"])) == (ingresos - costo - gastos).quantize(Decimal("0.01"))

    # Aislamiento: Café Central no ve nada de Donde Tavo.
    h = {"Authorization": f"Bearer {_login(client, 'admin@cafecentral.demo', 'Central2026*Admin').json()['access_token']}"}
    ids_tavo = {str(o.id) for o in de_hoy}
    jornada = db_session.query(Orden.jornada).filter(Orden.tenant_id == central.id).order_by(Orden.jornada.desc()).first()[0]
    lista = client.get(f"{API}/ordenes?vista=todas&jornada={jornada}&por_pagina=100", headers=h).json()["items"]
    assert lista and not ids_tavo & {o["id"] for o in lista}
    assert client.get(f"{API}/ordenes/{de_hoy[0].id}", headers=h).status_code == 404

    # Idempotente: otra corrida el mismo día no duplica nada.
    n = db_session.query(Orden).filter(Orden.tenant_id == tavo.id).count()
    otra = seed.cargar_demo(db_session, ahora=ahora, dias=DIAS, escala=0.6)
    assert otra["donde_tavo"]["al_dia"] and otra["cafe_central"]["al_dia"]
    assert db_session.query(Orden).filter(Orden.tenant_id == tavo.id).count() == n


def test_la_demo_nunca_se_carga_en_produccion(db_session, seed, monkeypatch):
    monkeypatch.setattr(seed.settings, "ENV", "production")
    with pytest.raises(ConflictError):
        seed.cargar_demo(db_session)
    assert seed.tenant_de(db_session, "admin@dondetavo.demo") is None


@pytest.mark.parametrize("n", [3, 10, 30])
def test_hoy_siempre_deja_ordenes_cobradas_aunque_sea_temprano(seed, n):
    """Corrida temprano (pocas órdenes de hoy): primero quedan las cobradas
    que necesita "Hoy" del dashboard y luego, por prioridad, las vivas."""
    import random

    ahora = ahora_utc()
    hoy = (ahora + seed.COLOMBIA).date()
    planes = [seed.OrdenPlan(t=ahora - timedelta(minutes=5 * (n - i)), tipo="local", origen="local", toma="mesero", items=[], mesa="S8")
              for i in range(n)]
    seed.marcar_estados_de_hoy(random.Random(1), planes, hoy, ahora)
    destinos = [p.destino for p in planes]
    assert destinos.count("cobrada") + destinos.count("anulada") >= min(n, seed.MIN_COBRADAS_HOY)
    if n >= 10:
        assert {"entrante", "en_preparacion", "lista", "entregada"} <= set(destinos), destinos
