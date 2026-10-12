"""
AJUSTES DEL RESTAURANTE (fase 1, 2026-10-12): datos del negocio, logo,
configuración operativa, zonas, mesas, jornada y branding.
"""
import io
import re
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from app.core.branding import NOMBRE_PRODUCTO
from app.db.models import Tenant
from app.modules.ajustes.schemas import ConfiguracionRestaurante, configuracion_de
from app.modules.ajustes.services import fecha_jornada, limites_jornada

API = "/api/v1"
FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "src"


@pytest.fixture()
def s(client, tenant_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory(nombre_empresa="Donde Tavo")
    return client, auth_headers_factory(usuario_factory(tenant)), tenant


def _imagen(formato="PNG", tamano=(1200, 500), modo="RGB") -> bytes:
    buffer = io.BytesIO()
    Image.new(modo, tamano, "white").save(buffer, formato)
    return buffer.getvalue()


# ---------------------------------------------------------------- branding
def test_el_nombre_del_producto_es_el_mismo_en_backend_y_frontend():
    branding = (FRONTEND / "config" / "branding.jsx").read_text(encoding="utf-8")
    assert re.search(r'nombre:\s*"([^"]+)"', branding).group(1) == NOMBRE_PRODUCTO


# ---------------------------------------------------------------- negocio
def test_los_datos_del_negocio_se_guardan_y_salen_en_la_sesion(s):
    client, h, _ = s
    r = client.put(f"{API}/ajustes/negocio", headers=h, json={
        "nombre_empresa": "Donde Tavo", "nit": "900123456-8", "direccion": "  Cra 45  # 26-85 ",
        "ciudad": "Bogotá", "telefono": "300 123 4567", "correo": "Tavo@Ejemplo.co",
    })
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["nit"] == "900123456-8" and datos["telefono"] == "3001234567"
    assert datos["direccion"] == "Cra 45 # 26-85" and datos["correo"] == "tavo@ejemplo.co"
    me = client.get(f"{API}/seguridad/me", headers=h).json()["tenant"]
    assert me["nit"] == "900123456-8" and me["ciudad"] == "Bogotá"
    # La sesión trae la configuración con sus valores por defecto.
    assert me["configuracion"]["tipos_orden"] == ["local", "llevar", "domicilio"]
    assert me["configuracion"]["impuesto_consumo"] == {"aplica": True, "tasa": "8.00", "incluido_en_precio": True}


@pytest.mark.parametrize("campo,valor,mensaje", [
    ("nit", "900123456-7", "debería ser 8"),
    ("telefono", "12345", "celular de 10 dígitos"),
    ("ciudad", "Bogotá 2", "Solo letras"),
    ("nombre_empresa", " Tavo", "sin espacios al inicio"),
])
def test_los_datos_del_negocio_invalidos_dicen_la_causa_bajo_el_campo(s, campo, valor, mensaje):
    client, h, _ = s
    cuerpo = {"nombre_empresa": "Donde Tavo", campo: valor}
    r = client.put(f"{API}/ajustes/negocio", headers=h, json=cuerpo)
    assert r.status_code == 422
    errores = {e["campo"]: e["mensaje"] for e in r.json()["errores"]}
    assert mensaje in errores[campo]


def test_dos_restaurantes_no_comparten_nit(s, tenant_factory, usuario_factory, auth_headers_factory):
    client, h, _ = s
    assert client.put(f"{API}/ajustes/negocio", headers=h, json={"nombre_empresa": "Donde Tavo", "nit": "900123456-8"}).status_code == 200
    otro = auth_headers_factory(usuario_factory(tenant_factory()))
    r = client.put(f"{API}/ajustes/negocio", headers=otro, json={"nombre_empresa": "Otro Sitio", "nit": "900123456-8"})
    assert r.status_code == 409 and "900123456-8" in r.json()["detail"]


# ---------------------------------------------------------------- logo
def test_el_logo_se_comprime_a_webp_y_reemplaza_al_anterior(s, db_session):
    client, h, tenant = s
    r = client.put(f"{API}/ajustes/negocio/logo", headers={**h, "Content-Type": "image/png"}, content=_imagen())
    assert r.status_code == 200, r.text
    primero = r.json()["logo_id"]
    imagen = client.get(f"{API}/imagenes/{primero}")
    assert imagen.status_code == 200 and imagen.headers["content-type"] == "image/webp"
    assert "immutable" in imagen.headers["cache-control"]
    with Image.open(io.BytesIO(imagen.content)) as abierta:
        assert abierta.format == "WEBP" and abierta.size == (600, 250)

    segundo = client.put(f"{API}/ajustes/negocio/logo", headers={**h, "Content-Type": "image/jpeg"}, content=_imagen("JPEG")).json()["logo_id"]
    assert segundo != primero
    assert client.get(f"{API}/imagenes/{primero}").status_code == 404  # el viejo se borró

    r = client.delete(f"{API}/ajustes/negocio/logo", headers=h)
    assert r.status_code == 200 and r.json()["logo_id"] is None
    assert client.get(f"{API}/imagenes/{segundo}").status_code == 404


@pytest.mark.parametrize("tipo,contenido,estado,mensaje", [
    ("application/pdf", b"%PDF-1.4", 422, "solo se aceptan imágenes JPG, PNG o WebP"),
    ("image/png", b"esto no es una imagen", 422, "no es una imagen que se pueda abrir"),
    ("image/jpeg", None, 422, "su contenido es PNG"),
    ("image/png", b"", 422, "No llegó ninguna imagen"),
])
def test_imagenes_invalidas_se_rechazan_con_la_causa(s, tipo, contenido, estado, mensaje):
    client, h, _ = s
    cuerpo = _imagen("PNG") if contenido is None else contenido
    r = client.put(f"{API}/ajustes/negocio/logo", headers={**h, "Content-Type": tipo}, content=cuerpo)
    assert r.status_code == estado and mensaje in r.json()["detail"], r.text


def test_una_imagen_de_mas_de_5_mb_se_rechaza(s):
    client, h, _ = s
    r = client.put(f"{API}/ajustes/negocio/logo", headers={**h, "Content-Type": "image/png"}, content=b"0" * (5 * 1024 * 1024 + 1))
    assert r.status_code == 413 and "máximo es 5 MB" in r.json()["detail"]


def test_la_foto_de_un_plato_sale_cuadrada():
    from app.modules.imagenes.services import procesar

    webp, ancho, alto = procesar(_imagen("JPEG", (2000, 1000)), "image/jpeg", "plato")
    assert (ancho, alto) == (640, 640)
    with Image.open(io.BytesIO(webp)) as abierta:
        assert abierta.size == (640, 640)


# ---------------------------------------------------------------- configuración
def test_la_configuracion_se_guarda_validada(s):
    client, h, _ = s
    actual = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    actual.update({
        "tipos_orden": ["local", "llevar"],
        "medios_pago": ["efectivo", "nequi"],
        "propina_sugerida": "8",
        "alerta_cocina_minutos": 20,
        "jornada": {"inicio": "07:00", "fin": "16:00"},
        "impresoras": [
            {"nombre": "Cocina", "uso": "comanda", "ancho_mm": 80, "conexion": "ip", "direccion": "192.168.1.50:9100"},
            {"nombre": "Caja", "uso": "factura", "ancho_mm": 58, "conexion": "navegador", "direccion": "no aplica"},
        ],
    })
    r = client.put(f"{API}/ajustes/restaurante", headers=h, json=actual)
    assert r.status_code == 200, r.text
    guardada = client.get(f"{API}/ajustes/restaurante", headers=h).json()
    assert guardada["tipos_orden"] == ["local", "llevar"] and guardada["alerta_cocina_minutos"] == 20
    assert guardada["impresoras"][0]["direccion"] == "192.168.1.50:9100"
    assert guardada["impresoras"][1]["direccion"] is None  # sin red, sin IP
    assert all(i["id"] for i in guardada["impresoras"])


@pytest.mark.parametrize("cambio,campo,mensaje", [
    ({"tipos_orden": []}, "tipos_orden", "at least 1"),
    ({"medios_pago": ["efectivo", "efectivo"]}, "medios_pago", "repetidos"),
    ({"propina_sugerida": "35"}, "propina_sugerida", "30 %"),
    ({"alerta_cocina_minutos": 0}, "alerta_cocina_minutos", "entre 1 y 180"),
    ({"jornada": {"inicio": "25:00", "fin": "16:00"}}, "jornada.inicio", "formato 24 h"),
    ({"impresoras": [{"nombre": "Cocina", "conexion": "ip"}]}, "impresoras.0.direccion", "dirección IP"),
])
def test_configuracion_invalida_dice_la_causa(s, cambio, campo, mensaje):
    client, h, _ = s
    r = client.put(f"{API}/ajustes/restaurante", headers=h, json=cambio)
    assert r.status_code == 422
    errores = {e["campo"]: e["mensaje"] for e in r.json()["errores"]}
    assert campo in errores and mensaje in errores[campo], errores


def test_una_configuracion_guardada_vieja_o_rota_no_tumba_la_lectura():
    tenant = Tenant(nombre_empresa="X", configuracion={"propina_sugerida": "abc", "alerta_cocina_minutos": 25, "campo_viejo": 1})
    config = configuracion_de(tenant)
    assert config.alerta_cocina_minutos == 25  # lo válido se conserva
    assert config.propina_sugerida == ConfiguracionRestaurante().propina_sugerida  # lo roto vuelve al defecto


# ---------------------------------------------------------------- jornada
def test_la_jornada_empieza_a_su_hora_en_colombia():
    config = ConfiguracionRestaurante(jornada={"inicio": "06:00", "fin": "22:00"})
    # 10:00 UTC = 05:00 de Bogotá del 13 → todavía es la jornada del 12.
    assert fecha_jornada(config, datetime(2026, 10, 13, 10, 0)).isoformat() == "2026-10-12"
    # 11:00 UTC = 06:00 de Bogotá → arranca la del 13.
    assert fecha_jornada(config, datetime(2026, 10, 13, 11, 0)).isoformat() == "2026-10-13"
    inicio, fin = limites_jornada(config, datetime(2026, 10, 13).date())
    assert inicio == datetime(2026, 10, 13, 11, 0) and fin == datetime(2026, 10, 14, 11, 0)


# ---------------------------------------------------------------- zonas y mesas
def test_mesas_por_zona_con_nombres_normalizados_y_unicos(s):
    client, h, _ = s
    salon = client.post(f"{API}/ajustes/zonas", headers=h, json={"nombre": "Salón", "orden": 1}).json()
    r = client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": " b2 ", "zona_id": salon["id"], "puestos": 4})
    assert r.status_code == 201 and r.json()["nombre"] == "B2" and r.json()["zona_nombre"] == "Salón"
    r = client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": "B2"})
    assert r.status_code == 409 and "B2" in r.json()["detail"]
    for nombre in ("B10", "A1"):
        client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": nombre})
    nombres = [m["nombre"] for m in client.get(f"{API}/ajustes/mesas", headers=h).json()["items"]]
    assert nombres == ["A1", "B2", "B10"]  # orden natural: B2 antes que B10
    filtradas = client.get(f"{API}/ajustes/mesas?zona_id={salon['id']}", headers=h).json()
    assert [m["nombre"] for m in filtradas["items"]] == ["B2"]
    assert client.get(f"{API}/ajustes/zonas/{salon['id']}", headers=h).json()["mesas_count"] == 1


def test_una_zona_con_mesas_no_se_elimina(s):
    client, h, _ = s
    zona = client.post(f"{API}/ajustes/zonas", headers=h, json={"nombre": "Terraza"}).json()
    mesa = client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": "T1", "zona_id": zona["id"]}).json()
    r = client.delete(f"{API}/ajustes/zonas/{zona['id']}", headers=h)
    assert r.status_code == 409 and "tiene 1 mesa asociada" in r.json()["detail"]
    # Sin zona, la mesa queda suelta y la zona se puede borrar.
    assert client.put(f"{API}/ajustes/mesas/{mesa['id']}", headers=h, json={"zona_id": None}).json()["zona_id"] is None
    assert client.delete(f"{API}/ajustes/zonas/{zona['id']}", headers=h).status_code == 204


def test_desactivar_una_mesa_la_saca_del_filtro_de_activas(s):
    client, h, _ = s
    mesa = client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": "4"}).json()
    assert client.patch(f"{API}/ajustes/mesas/{mesa['id']}/estado", headers=h, json={"activo": False}).json()["activo"] is False
    assert client.get(f"{API}/ajustes/mesas?activo=true", headers=h).json()["total"] == 0


@pytest.mark.parametrize("nombre", ["B#2", "", "X" * 21])
def test_nombre_de_mesa_invalido(s, nombre):
    client, h, _ = s
    r = client.post(f"{API}/ajustes/mesas", headers=h, json={"nombre": nombre})
    assert r.status_code == 422


def test_un_rol_sin_ajustes_no_ve_la_configuracion_pero_si_la_recibe_en_su_sesion(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    mesero = auth_headers_factory(usuario_factory(tenant, rol=rol_factory(tenant, nombre="Mesero", permisos={"mesas": ["ver"]})))
    assert client.get(f"{API}/ajustes/restaurante", headers=mesero).status_code == 403
    me = client.get(f"{API}/seguridad/me", headers=mesero).json()
    assert me["tenant"]["configuracion"]["medios_pago"]
