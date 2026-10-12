"""
Datos de demostración (Fase 7, 2026-09-30): la demo NUNCA debe mostrar el
dashboard en ceros, la corra quien la corra y el día que sea.

Antes el seed era idempotente pero quedaba congelado en el día en que se
cargó: a los dos días "Hoy" mostraba ceros y "6 meses" salía plano. Ahora
`cargar_demo` re-ancla cada documento a sus "días atrás" contados desde hoy.
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.modules.compras.models import Compra
from app.modules.inventario.models import MovimientoInsumo
from app.modules.ventas.models import Venta

RUTA_SEED = Path(__file__).resolve().parents[2] / "automatizaciones" / "deploy" / "seed_demo.py"


@pytest.fixture(scope="module")
def seed():
    spec = importlib.util.spec_from_file_location("seed_demo", RUTA_SEED)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _ahora():
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def empresa_demo(client, db_session, tenant_factory, usuario_factory, auth_headers_factory, seed):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    seed.cargar_demo(db_session, tenant.id, _ahora())
    return tenant, auth_headers_factory(admin)


def _vendido(client, headers, periodo):
    resp = client.get(f"/api/v1/dashboard/panel?periodo={periodo}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _serie(client, headers, rango):
    resp = client.get(f"/api/v1/dashboard/serie?rango={rango}", headers=headers)
    assert resp.status_code == 200, resp.text
    return [p["actual"] for p in resp.json()["puntos"]]


def test_la_demo_deja_ventas_hoy_esta_semana_y_en_los_ultimos_6_meses(client, empresa_demo):
    _, headers = empresa_demo
    assert sum(_serie(client, headers, "1d")) > 0, "Hoy no puede quedar en cero"
    assert sum(1 for v in _serie(client, headers, "1s") if v > 0) >= 3, "la semana necesita varios días con ventas"
    meses = _serie(client, headers, "6m")
    assert sum(1 for v in meses if v > 0) >= 5, f"6 meses debe tener historia, no una línea plana: {meses}"
    assert _vendido(client, headers, "hoy")["mas_vendidos"], "Hoy debe tener más vendidos"
    assert len(_vendido(client, headers, "anio")["mas_vendidos"]) >= 4


def test_es_idempotente(client, db_session, empresa_demo, seed):
    tenant, _ = empresa_demo
    antes = (db_session.query(Compra).filter_by(tenant_id=tenant.id).count(), db_session.query(Venta).filter_by(tenant_id=tenant.id).count())
    r = seed.cargar_demo(db_session, tenant.id, _ahora())
    assert (r["compras"], r["ventas"]) == (0, 0)
    despues = (db_session.query(Compra).filter_by(tenant_id=tenant.id).count(), db_session.query(Venta).filter_by(tenant_id=tenant.id).count())
    assert antes == despues


def test_una_demo_vieja_vuelve_a_hoy_al_correr_el_seed(client, db_session, empresa_demo, seed):
    """El caso real: la demo se cargó hace 10 días y el dashboard está en ceros."""
    tenant, headers = empresa_demo
    hace_10 = timedelta(days=10)
    for modelo in (Compra, Venta):
        for doc in db_session.query(modelo).filter_by(tenant_id=tenant.id):
            doc.fecha -= hace_10
    for mov in db_session.query(MovimientoInsumo).filter_by(tenant_id=tenant.id):
        mov.created_at -= hace_10
    db_session.commit()
    assert sum(_serie(client, headers, "1d")) == 0, "precondición: la demo envejecida deja Hoy en cero"

    seed.cargar_demo(db_session, tenant.id, _ahora())

    assert sum(_serie(client, headers, "1d")) > 0
    assert sum(1 for v in _serie(client, headers, "6m") if v > 0) >= 5


def test_el_historial_de_inventario_queda_en_orden_de_fechas(db_session, empresa_demo):
    """Las compras y ventas se crean en orden cronológico: recorriendo los
    movimientos por fecha, la existencia de cada insumo cuadra paso a paso
    y nunca queda en negativo."""
    tenant, _ = empresa_demo
    movimientos = (
        db_session.query(MovimientoInsumo)
        .filter_by(tenant_id=tenant.id)
        .order_by(MovimientoInsumo.created_at, MovimientoInsumo.id)
        .all()
    )
    assert movimientos
    existencia = {}
    for m in movimientos:
        existencia[m.insumo_id] = existencia.get(m.insumo_id, 0) + m.cantidad
        assert existencia[m.insumo_id] >= 0
        assert existencia[m.insumo_id] == m.existencia_resultante, f"{m.documento_codigo}: orden de fechas roto"


def test_la_demo_deja_recetas_costeadas_y_avisos_de_insumos(client, empresa_demo):
    _, headers = empresa_demo
    platos = client.get("/api/v1/catalogo/productos?por_pagina=100", headers=headers).json()["items"]
    assert len(platos) == 10
    assert all(p["costo"] is not None and p["margen"] is not None for p in platos), "todo plato de la demo lleva receta"
    combo = next(p for p in platos if p["tipo"] == "combo")
    assert float(combo["costo"]) == pytest.approx(sum(float(c["costo"]) * c["cantidad"] for c in combo["componentes"]))
    claves = {a["clave"] for a in client.get("/api/v1/dashboard/avisos", headers=headers).json()["avisos"]}
    assert "stock_bajo" in claves
