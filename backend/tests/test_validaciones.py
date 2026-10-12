"""Reglas de validación de negocio (app/core/validaciones.py) aplicadas por
los endpoints. El frontend replica los mismos mensajes; si estos cambian,
cambia frontend/src/lib/validaciones.js."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core import validaciones as v

PROVEEDOR_JURIDICA = {
    "tipo_persona": "juridica",
    "nit": "890903938-8",
    "razon_social": "Bancolombia SA",
    "representante_nombre": "Juan Carlos Mora",
    "telefono": "3001234567",
    "email": "Compras@Ejemplo.COM",
}


def _headers(tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    return auth_headers_factory(usuario_factory(tenant))


def _errores(resp):
    return {e["campo"]: e["mensaje"] for e in resp.json()["errores"]}


# ---------- Unidad: NIT y documentos ----------
@pytest.mark.parametrize("base,dv", [("890903938", 8), ("890904996", 1), ("899999068", 1), ("800197268", 4)])
def test_digito_verificacion_nit_coincide_con_nits_publicos(base, dv):
    assert v.digito_verificacion_nit(base) == dv


def test_validar_nit_rechaza_digito_incorrecto():
    with pytest.raises(ValueError, match="debería ser 8"):
        v.validar_nit("890903938-1")
    assert v.validar_nit(" 890.903.938-8 ") == "890903938-8"


@pytest.mark.parametrize("tipo,numero,ok", [
    ("CC", "1020304050", True), ("CC", "12345", False), ("CE", "1234567", True), ("CE", "12345678", False),
    ("PA", "ab123456", True), ("PA", "ab-12", False), ("TI", "1000123456", True), ("TI", "123", False),
])
def test_validar_documento_por_tipo(tipo, numero, ok):
    if ok:
        assert v.validar_documento(tipo, numero) == numero.strip().upper()
    else:
        with pytest.raises(ValueError):
            v.validar_documento(tipo, numero)


@pytest.mark.parametrize("valor,esperado", [("300 123 4567", "3001234567"), ("(60) 1 2345678", "6012345678")])
def test_telefono_colombiano_valido(valor, esperado):
    assert v.telefono(valor) == esperado


@pytest.mark.parametrize("valor", ["2001234567", "30012345", "601234567"])
def test_telefono_colombiano_invalido(valor):
    with pytest.raises(ValueError, match="celular de 10 dígitos"):
        v.telefono(valor)


# ---------- Endpoints: los mensajes llegan en español, por campo ----------
def test_proveedor_juridica_valida_nit_y_limpia_campos_de_natural(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = _headers(tenant_factory, usuario_factory, auth_headers_factory)
    resp = client.post("/api/v1/compras/proveedores", headers=headers, json={**PROVEEDOR_JURIDICA, "nit": "890903938-5"})
    assert resp.status_code == 422
    assert resp.json()["errores"][0]["campo"] == "nit"
    assert "debería ser 8" in resp.json()["errores"][0]["mensaje"]

    # Campos de persona natural enviados "fantasma": el backend los descarta.
    resp = client.post(
        "/api/v1/compras/proveedores",
        headers=headers,
        json={**PROVEEDOR_JURIDICA, "nombres": "Fantasma", "tipo_documento": "CC", "numero_documento": "1234567"},
    )
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["nombre"] == "Bancolombia SA"
    assert body["nombres"] is None and body["numero_documento"] is None
    assert body["email"] == "compras@ejemplo.com"  # normalizado a minúsculas


def test_proveedor_natural_exige_documento_valido_y_deriva_nombre(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = _headers(tenant_factory, usuario_factory, auth_headers_factory)
    base = {"tipo_persona": "natural", "tipo_documento": "CC", "nombres": "María José", "apellidos": "Gómez Pérez"}

    resp = client.post("/api/v1/compras/proveedores", headers=headers, json={**base, "numero_documento": "123"})
    assert resp.status_code == 422
    assert "entre 6 y 10 dígitos" in resp.json()["errores"][0]["mensaje"]

    resp = client.post("/api/v1/compras/proveedores", headers=headers, json={**base, "numero_documento": "1020304050"})
    assert resp.status_code == 201, resp.json()
    assert resp.json()["nombre"] == "María José Gómez Pérez"
    assert resp.json()["nit"] is None


def test_plato_rechaza_negativos_decimales_y_nombre_con_espacios(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = _headers(tenant_factory, usuario_factory, auth_headers_factory)
    resp = client.post(
        "/api/v1/catalogo/productos",
        headers=headers,
        json={"nombre": " Pizza ", "sku": "PIZ 1", "precio": "12.345", "dias_semana": [7]},
    )
    assert resp.status_code == 422
    errores = _errores(resp)
    assert errores["nombre"] == v.MSG_NOMBRE_CARTA
    assert errores["sku"] == v.MSG_SKU
    assert errores["precio"] == v.MSG_PRECIO
    assert "0 (lunes) a 6 (domingo)" in errores["dias_semana"]


def test_insumo_rechaza_cantidades_negativas_y_costos_con_muchos_decimales(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = _headers(tenant_factory, usuario_factory, auth_headers_factory)
    resp = client.post(
        "/api/v1/inventario/insumos",
        headers=headers,
        json={"nombre": "Queso", "unidad": "libra", "minimo": "-1", "costo_unitario": "1.23456", "existencia_inicial": "0.0001"},
    )
    assert resp.status_code == 422
    errores = _errores(resp)
    assert set(errores) == {"unidad", "minimo", "costo_unitario", "existencia_inicial"}
    assert errores["costo_unitario"] == v.MSG_COSTO
    assert errores["minimo"] == v.MSG_CANTIDAD_DECIMAL_CERO


def test_usuario_nombre_solo_letras_y_email_normalizado(client, tenant_factory, usuario_factory, rol_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)
    headers = auth_headers_factory(admin)
    rol = rol_factory(tenant)

    resp = client.post(
        "/api/v1/seguridad/usuarios",
        headers=headers,
        json={"nombre_completo": "Ana 123", "email": "ana@empresa.com", "password": "clave-segura-123", "rol_id": str(rol.id)},
    )
    assert resp.status_code == 422
    assert _errores(resp)["nombre_completo"] == v.MSG_NOMBRE_PERSONA

    resp = client.post(
        "/api/v1/seguridad/usuarios",
        headers=headers,
        json={"nombre_completo": "Ana O'Neil Pérez", "email": "  Ana.Perez@Empresa.COM ", "password": "clave-segura-123", "rol_id": str(rol.id)},
    )
    assert resp.status_code == 201, resp.json()
    assert resp.json()["email"] == "ana.perez@empresa.com"


def test_compra_rechaza_fecha_futura_y_cantidad_fuera_de_rango(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = _headers(tenant_factory, usuario_factory, auth_headers_factory)
    insumo = client.post("/api/v1/inventario/insumos", headers=headers, json={"nombre": "Arroz", "unidad": "kg"}).json()
    proveedor = client.post("/api/v1/compras/proveedores", headers=headers, json=PROVEEDOR_JURIDICA).json()
    futura = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    resp = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor["id"],
            "fecha": futura,
            "items": [{"insumo_id": insumo["id"], "cantidad": "2000000", "unidad": "kg", "precio_unitario": "10"}],
        },
    )
    assert resp.status_code == 422
    errores = _errores(resp)
    assert errores["fecha"] == "La fecha no puede ser futura"
    assert errores["items.0.cantidad"] == v.MSG_CANTIDAD_DECIMAL


def test_pedido_rechaza_entrega_anterior_a_hoy_y_telefono_invalido(client, tenant_factory, usuario_factory, auth_headers_factory):
    headers = _headers(tenant_factory, usuario_factory, auth_headers_factory)
    producto = client.post("/api/v1/catalogo/productos", headers=headers, json={"nombre": "Almuerzo", "precio": "100"}).json()
    ayer = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    resp = client.post(
        "/api/v1/ventas/pedidos",
        headers=headers,
        json={
            "cliente_nombre": "Obras del Valle",
            "cliente_telefono": "2001234567",
            "fecha": datetime.now(timezone.utc).isoformat(),
            "fecha_entrega": ayer,
            "items": [{"producto_id": producto["id"], "cantidad": 1, "precio_unitario": "100"}],
        },
    )
    assert resp.status_code == 422
    errores = _errores(resp)
    assert errores["fecha_entrega"] == "La fecha de entrega no puede ser anterior a hoy"
    assert errores["cliente_telefono"] == v.MSG_TELEFONO


BOGOTA = timezone(timedelta(hours=-5))


def _reloj_fijo(monkeypatch, ahora: datetime):
    class Reloj(datetime):
        @classmethod
        def now(cls, tz=None):
            return ahora.astimezone(tz)

    monkeypatch.setattr(v, "datetime", Reloj)


def _como_llega(dia: int, hora: int) -> datetime:
    """Hora de Bogotá tal como la envía el frontend: toISOString(), en UTC."""
    return datetime(2026, 9, dia, hora, 0, tzinfo=BOGOTA).astimezone(timezone.utc)


@pytest.mark.parametrize(
    "ahora",
    [
        datetime(2026, 9, 28, 20, 30, tzinfo=BOGOTA),  # noche: en UTC ya es el 29
        datetime(2026, 9, 28, 8, 0, tzinfo=BOGOTA),  # mañana del mismo día
    ],
)
def test_entrega_compara_contra_hoy_en_colombia_no_en_utc(monkeypatch, ahora):
    """Mismos casos que validaciones.test.js del frontend: 'hoy' es el día de Bogotá."""
    _reloj_fijo(monkeypatch, ahora)
    # Hoy a primera hora: aceptada aunque en UTC (de noche) ya sea el 29.
    assert v.fecha_no_pasada(_como_llega(28, 0))
    assert v.fecha_no_pasada(_como_llega(29, 9))
    # Ayer en Colombia: rechazada aunque en UTC (02:00 del 28) ya sea hoy.
    with pytest.raises(ValueError, match="La fecha de entrega no puede ser anterior a hoy"):
        v.fecha_no_pasada(_como_llega(27, 21))
    with pytest.raises(ValueError, match="La fecha no puede ser futura"):
        v.fecha_no_futura(_como_llega(29, 9))
    assert v.fecha_no_futura(_como_llega(28, 7))


@pytest.mark.parametrize("valor", ["Taladro Percutor", "Ñandú D'Alba", "Cemento Gris Tipo Uno"])
def test_nombre_item_acepta_solo_letras(valor):
    assert v.nombre_item(valor) == valor


@pytest.mark.parametrize("valor", ["Taladro 650W", "Ferretería & Cía", "Aceros S.A.S", " Taladro", "Taladro-X"])
def test_nombre_item_rechaza_digitos_y_simbolos(valor):
    with pytest.raises(ValueError, match="Solo letras"):
        v.nombre_item(valor)


@pytest.mark.parametrize("valor,ok", [("0", True), ("100", True), ("12.5", True), ("-1", False), ("100.01", False), ("10.555", False)])
def test_porcentaje_entre_0_y_100_con_2_decimales(valor, ok):
    if ok:
        assert v.porcentaje(Decimal(valor)) == Decimal(valor).quantize(Decimal("0.01"))
    else:
        with pytest.raises(ValueError, match="porcentaje entre 0 y 100"):
            v.porcentaje(Decimal(valor))
