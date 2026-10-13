"""
EL PLAN CONTRATADO SE APLICA EN EL BACKEND (2026-10-01).

Antes el plan solo escondía módulos del sidebar: una empresa en Básico podía
llamar a /compras o a la IA directamente por la API. Ahora `exigir_permiso`
comprueba el plan (o el add-on en `Tenant.modulos_activos`) ANTES que el rol,
y responde 403 con la causa. Ni un administrador usa lo que su empresa no
contrató.
"""
import re
from pathlib import Path

import pytest

from app.core.catalogo_permisos import CATALOGO, GRUPO_DE_MODULO, PLAN_MINIMO_DE_GRUPO

MODULES_JS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "config" / "modules.js"


@pytest.fixture
def admin_con_plan(tenant_factory, usuario_factory, auth_headers_factory):
    def _crear(plan, modulos_activos=None):
        tenant = tenant_factory(plan=plan, modulos_activos=modulos_activos or [])
        return auth_headers_factory(usuario_factory(tenant))  # administrador

    return _crear


def test_plan_basico_bloquea_inventario_e_ia_con_la_causa(client, admin_con_plan):
    h = admin_con_plan("basico")
    for ruta, grupo in (
        ("/api/v1/compras/compras", "el Inventario"),
        ("/api/v1/inventario/insumos", "el Inventario"),
        ("/api/v1/compras/proveedores", "el Inventario"),
        ("/api/v1/ia/sugerencias", "las Sugerencias IA"),
    ):
        r = client.get(ruta, headers=h)
        assert r.status_code == 403, ruta
        assert f"El plan Básico de tu empresa no incluye {grupo}" in r.json()["detail"], ruta


def test_plan_basico_si_usa_carta_caja_dashboard_y_seguridad(client, admin_con_plan):
    """Un restaurante no opera sin carta, órdenes y caja: van desde Básico."""
    h = admin_con_plan("basico")
    assert client.get("/api/v1/catalogo/productos", headers=h).status_code == 200
    assert client.get("/api/v1/caja/ventas", headers=h).status_code == 200
    assert client.get("/api/v1/dashboard/panel?periodo=mes", headers=h).status_code == 200
    assert client.get("/api/v1/seguridad/usuarios", headers=h).status_code == 200
    assert client.get("/api/v1/seguridad/roles", headers=h).status_code == 200


def test_plan_estandar_usa_inventario_pero_no_la_ia(client, admin_con_plan):
    h = admin_con_plan("estandar")
    assert client.get("/api/v1/inventario/insumos", headers=h).status_code == 200
    assert client.get("/api/v1/caja/ventas", headers=h).status_code == 200
    r = client.get("/api/v1/ia/sugerencias", headers=h)
    assert r.status_code == 403
    assert "desde el plan Pro + IA o como módulo adicional" in r.json()["detail"]


def test_la_ia_como_add_on_funciona_en_un_plan_menor(client, admin_con_plan):
    h = admin_con_plan("estandar", modulos_activos=["ia"])
    assert client.get("/api/v1/ia/sugerencias", headers=h).status_code == 200


def test_cada_modulo_del_catalogo_tiene_grupo_y_plan():
    assert set(GRUPO_DE_MODULO) == set(CATALOGO)
    assert set(GRUPO_DE_MODULO.values()) <= set(PLAN_MINIMO_DE_GRUPO)


def test_el_plan_de_cada_grupo_coincide_con_el_sidebar():
    """frontend/src/config/modules.js decide qué se VE; el backend decide qué
    se PUEDE usar. Si no coinciden, el sidebar ofrecería algo que da 403 (o
    escondería algo pagado)."""
    js = MODULES_JS.read_text(encoding="utf-8")
    # Bloques de primer nivel: key: "x", … plan: "y" (los hijos no llevan plan).
    pares = dict(re.findall(r'key:\s*"(\w+)",\s*label:[^\n]*\n(?:[^\n]*\n){1,3}?\s*plan:\s*"(\w+)"', js))
    assert pares == PLAN_MINIMO_DE_GRUPO
