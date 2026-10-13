"""
REPORTES (fase 8, 2026-10-12): las cifras cuadran con las recetas, los
gastos y los cobros; el detalle por plato, hora, tipo, mesero, medio,
categoría e insumo; CSV y PDF; costos solo con costos.ver.
"""
from datetime import datetime, timedelta

import pytest

from app.core.tiempo import ahora_utc
from app.modules.dashboard.periodos import ventana_de_periodo
from tests.conftest import API_V1 as API, abrir_caja, comprar, crear_insumo, crear_plato, tomar_orden


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    h = auth_headers_factory(usuario_factory(tenant, nombre_completo="Marta Mesera"))
    cat = client.post(f"{API}/catalogo/categorias", headers=h, json={"nombre": "Almuerzos"}).json()
    pollo = crear_insumo(client, h, "Pollo", "kg")
    arroz = crear_insumo(client, h, "Arroz", "kg")
    comprar(client, h, [(pollo["id"], "10", "kg", "20000"), (arroz["id"], "10", "kg", "4000")])
    # Costo por porción: 150 g de pollo (3.000) + 100 g de arroz (400) = 3.400.
    plato = crear_plato(client, h, "Arroz con pollo", "10800", receta=[(pollo["id"], "150", "g"), (arroz["id"], "100", "g")], categoria_id=cat["id"])
    return client, h, plato, pollo


def _cobrar(client, h, orden, medio="efectivo"):
    abrir_caja(client, h)
    r = client.post(f"{API}/caja/cobros", headers=h, json={"orden_id": orden["id"], "pagos": [{"medio": medio, "monto": orden["total"]}]})
    assert r.status_code == 201, r.text
    return r.json()


def test_el_reporte_cuadra_ventas_costo_gastos_y_utilidad(s):
    client, h, plato, pollo = s
    _cobrar(client, h, tomar_orden(client, h, [(plato["id"], 3)]))
    _cobrar(client, h, tomar_orden(client, h, [(plato["id"], 2)], tipo="local", mesa_id=client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": "M1"}).json()["id"]), medio="nequi")
    client.post(f"{API}/inventario/insumos/{pollo['id']}/merma", headers=h, json={"cantidad": "500", "unidad": "g", "motivo": "vencido"})
    hoy = (ahora_utc() - timedelta(hours=5)).date().isoformat()
    client.post(f"{API}/gastos", headers=h, json={"fecha": hoy, "categoria": "arriendo", "descripcion": "Arriendo", "valor": "20000"})

    r = client.get(f"{API}/reportes", headers=h, params={"periodo": "hoy"})
    assert r.status_code == 200, r.text
    d = r.json()
    res = d["resumen"]
    # 5 × 10.800 = 54.000 con el 8 % incluido → 50.000 de ingresos; costo 5 × 3.400.
    assert (res["total"], res["ingresos"], res["impuesto"], res["costo"]) == (54000.0, 50000.0, 4000.0, 17000.0)
    assert (res["utilidad_bruta"], res["gastos"], res["utilidad_real"]) == (33000.0, 20000.0, 13000.0)
    assert res["ordenes"] == 2 and res["ticket_promedio"] == 27000.0

    plato_r = d["platos"][0]
    assert (plato_r["unidades"], plato_r["vendido"], plato_r["ingresos"], plato_r["costo"], plato_r["margen"]) == (5, 54000.0, 50000.0, 17000.0, 33000.0)
    assert plato_r["costo_pct"] == 34.0
    assert {t["clave"]: t["total"] for t in d["tipos"]} == {"llevar": 32400.0, "local": 21600.0}
    assert d["meseros"] == [{"clave": "Marta Mesera", "nombre": "Marta Mesera", "ordenes": 2, "total": 54000.0, "ticket": 27000.0}]
    assert {m["clave"]: m["total"] for m in d["medios"]} == {"efectivo": 32400.0, "nequi": 21600.0}
    assert d["categorias"][0]["nombre"] == "Almuerzos"
    assert sum(x["cobros"] for x in d["horas"]) == 2 and len(d["horas"]) == 24 and len(d["dias"]) == 7
    pollo_r = next(i for i in d["insumos"] if i["nombre"] == "Pollo")
    assert (pollo_r["consumo"], pollo_r["costo_consumo"], pollo_r["merma"], pollo_r["costo_merma"]) == (0.75, 15000.0, 0.5, 10000.0)
    assert d["gastos"] == [{"clave": "arriendo", "nombre": "Arriendo", "total": 20000.0, "registros": 1}]


def test_csv_por_seccion_y_pdf(s):
    client, h, plato, _ = s
    _cobrar(client, h, tomar_orden(client, h, [plato["id"]]))
    csv = client.get(f"{API}/reportes/csv", headers=h, params={"seccion": "platos", "periodo": "mes"})
    assert csv.status_code == 200 and "Arroz con pollo" in csv.content.decode("utf-8") and "Margen" in csv.text
    pdf = client.get(f"{API}/reportes/pdf", headers=h, params={"periodo": "mes"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"{API}/reportes/csv", headers=h, params={"seccion": "inventada"}).status_code == 422


def test_periodo_personalizado(s):
    client, h, _, _ = s
    hoy = (ahora_utc() - timedelta(hours=5)).date()
    ok = client.get(f"{API}/reportes", headers=h, params={"desde": (hoy - timedelta(days=10)).isoformat(), "hasta": hoy.isoformat()})
    assert ok.status_code == 200 and ok.json()["periodo"].startswith("Del ")
    solo_uno = client.get(f"{API}/reportes", headers=h, params={"desde": hoy.isoformat()})
    assert solo_uno.status_code == 409 and "día inicial y el final" in solo_uno.json()["detail"]
    al_reves = client.get(f"{API}/reportes", headers=h, params={"desde": hoy.isoformat(), "hasta": (hoy - timedelta(days=1)).isoformat()})
    assert al_reves.status_code == 409


def test_sin_costos_ver_no_hay_costo_margen_ni_utilidad(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory, s):
    tenant = tenant_factory()
    h = auth_headers_factory(usuario_factory(tenant, rol=rol_factory(tenant, nombre="Gerente", permisos={"reportes": ["ver"]})))
    d = client.get(f"{API}/reportes", headers=h, params={"periodo": "mes"}).json()
    assert d["resumen"]["costo"] is None and d["resumen"]["utilidad_real"] is None and d["resumen"]["total"] == 0.0
    csv = client.get(f"{API}/reportes/csv", headers=h, params={"seccion": "platos"})
    assert "Margen" not in csv.text and "Costo" not in csv.text


def test_no_mezcla_empresas(s, client, tenant_factory, usuario_factory, auth_headers_factory):
    client_, h, plato, _ = s
    _cobrar(client_, h, tomar_orden(client_, h, [plato["id"]]))
    ajena = auth_headers_factory(usuario_factory(tenant_factory()))
    d = client.get(f"{API}/reportes", headers=ajena, params={"periodo": "mes"}).json()
    assert d["resumen"]["total"] == 0.0 and d["platos"] == [] and "Arroz con pollo" not in str(d)


def test_la_semana_empieza_el_lunes_de_colombia():
    # Miércoles 14/10/2026 a las 10:00 de Bogotá (15:00 UTC).
    v = ventana_de_periodo("semana", datetime(2026, 10, 14, 15, 0))
    assert v.desde == datetime(2026, 10, 12, 5, 0)  # lunes 12 a las 00:00 de Bogotá
    assert v.desde_anterior == datetime(2026, 10, 5, 5, 0)
    assert v.hasta - v.desde == v.hasta_anterior - v.desde_anterior
