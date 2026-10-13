"""
PERMISOS POR ROL Y AISLAMIENTO ENTRE EMPRESAS.

Lo que protege este archivo:

1. Estructura: TODA ruta de negocio exige un permiso, y es el permiso
   esperado. Una ruta nueva sin permiso (o con el permiso equivocado) rompe
   este test aunque nadie se acuerde de probarla.
2. Por cada ruta: un rol que tiene TODOS los permisos menos ese recibe 403
   con la causa concreta; con ese permiso, deja de ser 403.
3. Por cada ruta con un id: un usuario de OTRA empresa recibe 404 y nunca
   datos ajenos, y la empresa dueña no ve nada cambiado.
4. Reglas contra la escalada de privilegios y protección del Administrador.
5. Costos y márgenes solo para quien tiene `costos.ver`.
"""
import importlib
import uuid

import pytest

from app.core.catalogo_permisos import CATALOGO, ROLES_DE_EJEMPLO, frase_permiso, todos_los_permisos
from app.modules.seguridad.models import Rol

API = "/api/v1"

# (método, ruta) -> (módulo, acción). La fuente de verdad de este test.
ESPERADO = {
    ("GET", "/seguridad/permisos"): ("roles", "ver"),
    ("GET", "/seguridad/usuarios"): ("usuarios", "ver"),
    ("GET", "/seguridad/usuarios/{usuario_id}"): ("usuarios", "ver"),
    ("POST", "/seguridad/usuarios"): ("usuarios", "crear"),
    ("PUT", "/seguridad/usuarios/{usuario_id}"): ("usuarios", "editar"),
    ("PATCH", "/seguridad/usuarios/{usuario_id}/estado"): ("usuarios", "cambiar_estado"),
    ("DELETE", "/seguridad/usuarios/{usuario_id}"): ("usuarios", "eliminar"),
    ("GET", "/seguridad/roles"): ("roles", "ver"),
    ("GET", "/seguridad/roles/{rol_id}"): ("roles", "ver"),
    ("POST", "/seguridad/roles"): ("roles", "crear"),
    ("PUT", "/seguridad/roles/{rol_id}"): ("roles", "editar"),
    ("DELETE", "/seguridad/roles/{rol_id}"): ("roles", "eliminar"),
    ("GET", "/dashboard/panel"): ("dashboard", "ver"),
    ("GET", "/dashboard/serie"): ("dashboard", "ver"),
    ("GET", "/dashboard/avisos"): ("dashboard", "ver"),
    ("GET", "/ia/sugerencias"): ("ia", "ver"),
    ("GET", "/ia/status"): ("ia", "ver"),
    ("GET", "/ajustes/negocio"): ("ajustes", "ver"),
    ("PUT", "/ajustes/negocio"): ("ajustes", "editar"),
    ("PUT", "/ajustes/negocio/logo"): ("ajustes", "editar"),
    ("DELETE", "/ajustes/negocio/logo"): ("ajustes", "editar"),
    ("GET", "/ajustes/restaurante"): ("ajustes", "ver"),
    ("PUT", "/ajustes/restaurante"): ("ajustes", "editar"),
    ("GET", "/ajustes/zonas"): ("mesas", "ver"),
    ("GET", "/ajustes/zonas/{zona_id}"): ("mesas", "ver"),
    ("POST", "/ajustes/zonas"): ("mesas", "crear"),
    ("PUT", "/ajustes/zonas/{zona_id}"): ("mesas", "editar"),
    ("DELETE", "/ajustes/zonas/{zona_id}"): ("mesas", "eliminar"),
    ("GET", "/ajustes/mesas"): ("mesas", "ver"),
    ("GET", "/ajustes/mesas/{mesa_id}"): ("mesas", "ver"),
    ("POST", "/ajustes/mesas"): ("mesas", "crear"),
    ("PUT", "/ajustes/mesas/{mesa_id}"): ("mesas", "editar"),
    ("PATCH", "/ajustes/mesas/{mesa_id}/estado"): ("mesas", "cambiar_estado"),
    ("DELETE", "/ajustes/mesas/{mesa_id}"): ("mesas", "eliminar"),
    **{
        (metodo, ruta.format(r=recurso, id=f"{{{singular}_id}}")): (modulo, accion)
        for prefijo, recurso, singular, modulo in (
            ("catalogo", "categorias", "categoria", "categorias"),
            ("catalogo", "productos", "producto", "productos"),
            ("inventario", "insumos", "insumo", "insumos"),
            ("compras", "proveedores", "proveedor", "proveedores"),
        )
        for metodo, ruta, accion in (
            ("GET", "/" + prefijo + "/{r}", "ver"),
            ("GET", "/" + prefijo + "/{r}/{id}", "ver"),
            ("POST", "/" + prefijo + "/{r}", "crear"),
            ("PUT", "/" + prefijo + "/{r}/{id}", "editar"),
            ("PATCH", "/" + prefijo + "/{r}/{id}/estado", "cambiar_estado"),
            ("DELETE", "/" + prefijo + "/{r}/{id}", "eliminar"),
        )
    },
    ("PATCH", "/catalogo/productos/{producto_id}/agotado"): ("productos", "cambiar_estado"),
    ("PUT", "/catalogo/productos/{producto_id}/imagen"): ("productos", "editar"),
    ("DELETE", "/catalogo/productos/{producto_id}/imagen"): ("productos", "editar"),
    ("GET", "/inventario/insumos/{insumo_id}/movimientos"): ("insumos", "ver"),
    ("GET", "/inventario/grupos"): ("insumos", "ver"),
    ("GET", "/inventario/movimientos"): ("movimientos", "ver"),
    ("POST", "/inventario/insumos/{insumo_id}/merma"): ("movimientos", "crear"),
    ("GET", "/inventario/conteos"): ("movimientos", "ver"),
    ("GET", "/inventario/conteos/{conteo_id}"): ("movimientos", "ver"),
    ("POST", "/inventario/conteos"): ("movimientos", "crear"),
    ("GET", "/inventario/carga-inicial/plantilla"): ("insumos", "ver"),
    ("POST", "/inventario/carga-inicial/validar"): ("insumos", "crear"),
    ("POST", "/inventario/carga-inicial/aplicar"): ("insumos", "crear"),
    ("GET", "/compras/compras"): ("compras", "ver"),
    ("GET", "/compras/compras/{compra_id}"): ("compras", "ver"),
    ("GET", "/compras/compras/{compra_id}/pdf"): ("compras", "ver"),
    ("POST", "/compras/compras"): ("compras", "crear"),
    ("POST", "/compras/compras/{compra_id}/confirmar"): ("compras", "cambiar_estado"),
    ("POST", "/compras/compras/{compra_id}/cancelar"): ("compras", "cambiar_estado"),
    ("POST", "/compras/compras/{compra_id}/anular"): ("compras", "anular"),
    ("GET", "/caja/actual"): ("caja", "ver"),
    ("POST", "/caja/abrir"): ("caja", "cambiar_estado"),
    ("POST", "/caja/cerrar"): ("caja", "cambiar_estado"),
    ("GET", "/caja/cierres"): ("caja", "ver"),
    ("GET", "/caja/cierres/{caja_id}"): ("caja", "ver"),
    ("GET", "/caja/por-cobrar"): ("ventas", "crear"),
    ("POST", "/caja/cobros"): ("ventas", "crear"),
    ("GET", "/caja/ventas"): ("ventas", "ver"),
    ("GET", "/caja/ventas/{venta_id}"): ("ventas", "ver"),
    ("GET", "/caja/ventas/{venta_id}/pdf"): ("ventas", "ver"),
    ("POST", "/caja/ventas/{venta_id}/anular"): ("ventas", "anular"),
    ("GET", "/gastos"): ("gastos", "ver"),
    ("GET", "/gastos/{gasto_id}"): ("gastos", "ver"),
    ("POST", "/gastos"): ("gastos", "crear"),
    ("PUT", "/gastos/{gasto_id}"): ("gastos", "editar"),
    ("DELETE", "/gastos/{gasto_id}"): ("gastos", "eliminar"),
    ("GET", "/ordenes/carta"): ("ordenes", "crear"),
    ("GET", "/ordenes/mesas"): ("ordenes", "ver"),
    ("GET", "/ordenes/jornada"): ("ordenes", "ver"),
    ("GET", "/ordenes"): ("ordenes", "ver"),
    ("GET", "/ordenes/{orden_id}"): ("ordenes", "ver"),
    ("POST", "/ordenes"): ("ordenes", "crear"),
    ("POST", "/ordenes/{orden_id}/items"): ("ordenes", "editar"),
    ("PUT", "/ordenes/{orden_id}"): ("ordenes", "editar"),
    ("POST", "/ordenes/{orden_id}/items/{item_id}/anular"): ("ordenes", "editar"),
    ("POST", "/ordenes/{orden_id}/anular"): ("ordenes", "anular"),
    ("POST", "/ordenes/{orden_id}/entregar"): ("ordenes", "cambiar_estado"),
    ("POST", "/ordenes/agotados"): ("ordenes", "crear"),
    ("GET", "/reportes"): ("reportes", "ver"),
    ("GET", "/reportes/csv"): ("reportes", "ver"),
    ("GET", "/reportes/pdf"): ("reportes", "ver"),
    ("GET", "/cocina/comandas"): ("cocina", "ver"),
    ("POST", "/cocina/comandas/{comanda_id}/tomar"): ("cocina", "cambiar_estado"),
    ("POST", "/cocina/comandas/{comanda_id}/finalizar"): ("cocina", "cambiar_estado"),
}

# Rutas que NO exigen permiso, y por qué.
SIN_PERMISO = {
    ("POST", "/seguridad/login"),  # público: es la puerta de entrada
    ("POST", "/seguridad/registro"),  # público: alta de una empresa nueva
    ("GET", "/seguridad/me"),  # todo usuario activo puede saber quién es
    # Un <img> no manda el token; son fotos de la carta y logos, por UUID
    # aleatorio (app/modules/imagenes/router.py).
    ("GET", "/imagenes/{imagen_id}"),
}


def _rutas_de_negocio():
    for modulo in ("seguridad", "dashboard", "catalogo", "inventario", "compras", "caja", "gastos", "ordenes", "cocina", "reportes", "ia", "ajustes", "imagenes"):
        router = importlib.import_module(f"app.modules.{modulo}.router").router
        for ruta in router.routes:
            for metodo in ruta.methods - {"HEAD", "OPTIONS"}:
                yield metodo, ruta.path, ruta


def _permiso_de(dependant):
    for dep in dependant.dependencies:
        marca = getattr(dep.call, "__permiso__", None)
        if marca:
            return marca
        encontrada = _permiso_de(dep)
        if encontrada:
            return encontrada
    return None


# ---------------------------------------------------------------------------
# 1. Estructura: ninguna ruta de negocio sin su permiso
# ---------------------------------------------------------------------------
def test_toda_ruta_de_negocio_exige_el_permiso_esperado():
    encontradas = {}
    for metodo, path, ruta in _rutas_de_negocio():
        encontradas[(metodo, path)] = _permiso_de(ruta.dependant)

    sin_revisar = set(encontradas) - set(ESPERADO) - SIN_PERMISO
    assert not sin_revisar, f"rutas nuevas sin entrada en ESPERADO (¿qué permiso exigen?): {sorted(sin_revisar)}"
    faltan = set(ESPERADO) - set(encontradas)
    assert not faltan, f"ESPERADO nombra rutas que ya no existen: {sorted(faltan)}"

    errores = [
        f"{m} {p}: exige {encontradas[(m, p)]}, se esperaba {esperado}"
        for (m, p), esperado in ESPERADO.items()
        if encontradas[(m, p)] != esperado
    ]
    assert not errores, "\n".join(errores)
    for publica in SIN_PERMISO:
        assert encontradas[publica] is None


def test_el_catalogo_cubre_los_modulos_pedidos():
    for modulo in ("compras", "productos", "categorias", "insumos", "movimientos", "costos", "proveedores", "ventas", "caja", "gastos", "ordenes", "usuarios", "roles", "dashboard", "ajustes", "mesas"):
        assert modulo in CATALOGO
    # Cada par usado en ESPERADO existe en el catálogo.
    for modulo, accion in ESPERADO.values():
        assert accion in CATALOGO[modulo][2]


# ---------------------------------------------------------------------------
# 2. 403 sin el permiso exacto; con él, pasa la verificación
# ---------------------------------------------------------------------------
def _todos_menos(modulo, accion):
    permisos = todos_los_permisos()
    permisos[modulo] = [a for a in permisos[modulo] if a != accion]
    return permisos


def _url_con_ids(path):
    partes = [str(uuid.uuid4()) if p.startswith("{") else p for p in path.split("/")]
    return API + "/".join(partes)


@pytest.mark.parametrize(("metodo", "path"), sorted(ESPERADO), ids=lambda x: x if isinstance(x, str) else None)
def test_sin_el_permiso_exacto_responde_403_con_la_causa(metodo, path, client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    modulo, accion = ESPERADO[(metodo, path)]
    tenant = tenant_factory()
    rol = rol_factory(tenant, nombre="Casi todo", permisos=_todos_menos(modulo, accion))
    headers = auth_headers_factory(usuario_factory(tenant, rol=rol))

    resp = client.request(metodo, _url_con_ids(path), headers=headers, json={})

    assert resp.status_code == 403, (metodo, path, resp.status_code, resp.text)
    detalle = resp.json()["detail"]
    assert "Casi todo" in detalle and frase_permiso(modulo, accion) in detalle


@pytest.mark.parametrize(("metodo", "path"), sorted(ESPERADO), ids=lambda x: x if isinstance(x, str) else None)
def test_con_el_permiso_pasa_la_verificacion(metodo, path, client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    """Un rol NO administrador que tiene ese único permiso ya no recibe 403
    (puede recibir 404 por el id inventado o 422 por el cuerpo vacío)."""
    modulo, accion = ESPERADO[(metodo, path)]
    tenant = tenant_factory()
    rol = rol_factory(tenant, nombre="Solo eso", permisos={modulo: [accion]})
    headers = auth_headers_factory(usuario_factory(tenant, rol=rol))

    resp = client.request(metodo, _url_con_ids(path), headers=headers, json={})

    assert resp.status_code != 403, (metodo, path, resp.text)
    assert resp.status_code != 401


def test_rol_sin_ningun_permiso_no_entra_a_nada(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    headers = auth_headers_factory(usuario_factory(tenant, rol=rol_factory(tenant, permisos={})))
    for metodo, path in ESPERADO:
        resp = client.request(metodo, _url_con_ids(path), headers=headers, json={})
        assert resp.status_code == 403, (metodo, path, resp.status_code)
    # Pero sí puede saber quién es.
    me = client.get(f"{API}/seguridad/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["permisos"] == {} and me.json()["es_administrador"] is False


def test_las_rutas_de_ia_ya_no_son_publicas(client):
    assert client.get(f"{API}/ia/status").status_code == 401
    assert client.get(f"{API}/ia/sugerencias").status_code == 401


# ---------------------------------------------------------------------------
# 3. Aislamiento entre empresas: nunca datos ajenos
# ---------------------------------------------------------------------------
@pytest.fixture()
def dos_empresas(client, tenant_factory, usuario_factory, auth_headers_factory):
    """Empresa A con un recurso de cada tipo; admin de la empresa B."""
    tenant_a, tenant_b = tenant_factory(), tenant_factory()
    admin_a = usuario_factory(tenant_a)
    ha = auth_headers_factory(admin_a)
    hb = auth_headers_factory(usuario_factory(tenant_b))

    def crear(ruta, cuerpo):
        r = client.post(f"{API}{ruta}", headers=ha, json=cuerpo)
        assert r.status_code == 201, (ruta, r.text)
        return r.json()

    cat = crear("/catalogo/categorias", {"nombre": "Bebidas"})
    zona = crear("/ajustes/zonas", {"nombre": "Terraza"})
    mesa = crear("/ajustes/mesas", {"nombre": "B2", "zona_id": zona["id"]})
    prov = crear("/compras/proveedores", {"tipo_persona": "juridica", "nit": "890903938-8", "razon_social": "Proveedor de Pruebas", "representante_nombre": "Ana Prueba"})
    insumo = crear("/inventario/insumos", {"nombre": "Gaseosa fría", "unidad": "unidad"})
    prod = crear("/catalogo/productos", {"nombre": "Gaseosa", "precio": "3000", "receta": [{"insumo_id": insumo["id"], "cantidad": "1", "unidad": "unidad"}]})
    compra = crear("/compras/compras", {"proveedor_id": prov["id"], "fecha": "2026-01-01T09:00:00", "confirmar": True, "items": [{"insumo_id": insumo["id"], "cantidad": "10", "unidad": "unidad", "precio_unitario": "1800"}]})
    caja = crear("/caja/abrir", {"base_inicial": "50000"})
    cobrada = crear("/ordenes", {"tipo": "llevar", "items": [{"producto_id": prod["id"]}]})
    venta = crear("/caja/cobros", {"orden_id": cobrada["id"], "pagos": [{"medio": "efectivo", "monto": "3000"}]})
    gasto = crear("/gastos", {"fecha": "2026-01-02", "categoria": "gas", "descripcion": "Pipeta de gas", "valor": "90000"})
    orden = crear("/ordenes", {"tipo": "llevar", "cliente_nombre": "Cliente Dos", "items": [{"producto_id": prod["id"]}, {"producto_id": prod["id"]}]})
    conteo = crear("/inventario/conteos", {"lineas": [{"insumo_id": insumo["id"], "contado": "8"}]})
    rol = crear("/seguridad/roles", {"nombre": "Vendedor", "permisos": {"ventas": ["ver"]}})
    usuario = crear("/seguridad/usuarios", {"nombre_completo": "Pedro Pérez", "email": f"{uuid.uuid4().hex[:8]}@a.com", "password": "clave-segura-123", "rol_id": rol["id"]})

    ids = {
        "categoria_id": cat["id"], "zona_id": zona["id"], "mesa_id": mesa["id"], "proveedor_id": prov["id"], "producto_id": prod["id"], "insumo_id": insumo["id"], "conteo_id": conteo["id"],
        "compra_id": compra["id"], "venta_id": venta["id"], "caja_id": caja["id"], "gasto_id": gasto["id"], "orden_id": orden["id"], "item_id": orden["items"][0]["id"], "comanda_id": orden["comandas"][0]["id"], "rol_id": rol["id"], "usuario_id": usuario["id"],
    }
    return ha, hb, ids


# Cuerpos VÁLIDOS: si el cuerpo fuera inválido, un 422 escondería una fuga.
CUERPOS = {
    ("PUT", "categoria_id"): {"nombre": "Robada"},
    ("PUT", "zona_id"): {"nombre": "Robada"},
    ("PUT", "mesa_id"): {"nombre": "ROBADA"},
    ("PUT", "proveedor_id"): {"razon_social": "Robada SAS"},
    ("PUT", "producto_id"): {"nombre": "Robado"},
    ("PUT", "insumo_id"): {"nombre": "Robado"},
    ("PATCH", "producto_id"): {"activo": False, "agotado": True},
    ("PUT", "orden_id"): {"tipo": "llevar", "cliente_nombre": "Robado Ajeno"},
    # Sirve para agregar platos, anular uno o la orden y entregar.
    ("POST", "orden_id"): {"items": [{"producto_id": str(uuid.uuid4())}], "motivo": "Robado por otra empresa"},
    ("PUT", "usuario_id"): {"nombre_completo": "Nombre Robado"},
    ("PUT", "rol_id"): {"descripcion": "robado"},
    ("PATCH", None): {"activo": False},
    ("POST", "insumo_id"): {"cantidad": "1", "unidad": "unidad", "motivo": "vencido"},
    ("POST", "venta_id"): {"motivo": "Robado por otra empresa"},
    ("PUT", "gasto_id"): {"fecha": "2026-01-02", "categoria": "otros", "descripcion": "Robado", "valor": "1"},
}


def _rutas_con_id():
    for metodo, path in sorted(ESPERADO):
        param = next((p[1:-1] for p in path.split("/") if p.startswith("{")), None)
        if param:
            yield metodo, path, param


@pytest.mark.parametrize(("metodo", "path", "param"), list(_rutas_con_id()))
def test_otra_empresa_recibe_404_y_nunca_datos_ajenos(metodo, path, param, client, dos_empresas):
    ha, hb, ids = dos_empresas
    url = API + path
    for nombre, valor in ids.items():
        url = url.replace("{" + nombre + "}", valor)
    cuerpo = CUERPOS.get((metodo, param)) or CUERPOS.get((metodo, None)) if metodo in ("PUT", "PATCH", "POST") else None

    resp = client.request(metodo, url, headers=hb, json=cuerpo)

    assert resp.status_code == 404, (metodo, path, resp.status_code, resp.text[:200])
    assert ids[param] not in resp.text
    # Y en la empresa dueña, el recurso sigue ahí sin cambios.
    base = path.split("/{")[0]
    if metodo in ("PUT", "PATCH", "DELETE", "POST") and ("GET", f"{base}/{{{param}}}") in ESPERADO:
        dueno = client.get(f"{API}{base}/{ids[param]}", headers=ha)
        assert dueno.status_code == 200
        assert "robad" not in dueno.text.lower()


def test_los_listados_de_otra_empresa_no_traen_nada_ajeno(client, dos_empresas):
    ha, hb, ids = dos_empresas
    for ruta in ("/catalogo/categorias", "/ajustes/zonas", "/ajustes/mesas", "/compras/proveedores", "/catalogo/productos", "/inventario/insumos",
                 "/inventario/movimientos", "/inventario/conteos", "/compras/compras", "/caja/ventas", "/caja/cierres", "/gastos", "/ordenes", "/seguridad/usuarios", "/seguridad/roles"):
        texto = client.get(f"{API}{ruta}", headers=hb).text
        for valor in ids.values():
            assert valor not in texto, (ruta, valor)


# ---------------------------------------------------------------------------
# 4. Administrador y escalada de privilegios
# ---------------------------------------------------------------------------
@pytest.fixture()
def empresa(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    admin = usuario_factory(tenant)  # rol administrador por defecto
    gestor_rol = rol_factory(
        tenant,
        nombre="Gestor",
        permisos={"usuarios": ["ver", "crear", "editar", "cambiar_estado", "eliminar"], "roles": ["ver", "crear", "editar", "eliminar"], "ventas": ["ver"]},
    )
    gestor = usuario_factory(tenant, rol=gestor_rol)
    return {
        "tenant": tenant, "admin": admin, "gestor": gestor, "gestor_rol": gestor_rol,
        "h_admin": auth_headers_factory(admin), "h_gestor": auth_headers_factory(gestor),
    }


def test_el_rol_administrador_no_se_elimina_ni_se_le_editan_permisos(client, empresa):
    rol_admin = empresa["admin"].rol_id
    r = client.delete(f"{API}/seguridad/roles/{rol_admin}", headers=empresa["h_admin"])
    assert r.status_code == 409 and "no se puede eliminar" in r.json()["detail"]
    r = client.put(f"{API}/seguridad/roles/{rol_admin}", headers=empresa["h_admin"], json={"permisos": {"ventas": ["ver"]}})
    assert r.status_code == 409 and "acceso total" in r.json()["detail"]
    # La descripción sí se puede cambiar.
    r = client.put(f"{API}/seguridad/roles/{rol_admin}", headers=empresa["h_admin"], json={"descripcion": "Dueño"})
    assert r.status_code == 200 and r.json()["es_administrador"] is True


def test_quien_no_es_admin_no_puede_asignar_el_rol_administrador(client, empresa):
    rol_admin = str(empresa["admin"].rol_id)
    r = client.post(f"{API}/seguridad/usuarios", headers=empresa["h_gestor"], json={
        "nombre_completo": "Nuevo Jefe", "email": "jefe@x.com", "password": "clave-segura-123", "rol_id": rol_admin})
    assert r.status_code == 403 and "Solo un administrador puede asignar" in r.json()["detail"]
    r = client.put(f"{API}/seguridad/usuarios/{empresa['gestor'].id}", headers=empresa["h_gestor"], json={"rol_id": rol_admin})
    assert r.status_code in (403, 409)


def test_nadie_cambia_su_propio_rol_ni_edita_los_permisos_de_su_rol(client, empresa, rol_factory):
    otro = rol_factory(empresa["tenant"], nombre="Otro", permisos={"ventas": ["ver"]})
    r = client.put(f"{API}/seguridad/usuarios/{empresa['gestor'].id}", headers=empresa["h_gestor"], json={"rol_id": str(otro.id)})
    assert r.status_code == 409 and "tu propio rol" in r.json()["detail"]
    r = client.put(f"{API}/seguridad/roles/{empresa['gestor_rol'].id}", headers=empresa["h_gestor"],
                   json={"permisos": {**empresa["gestor_rol"].permisos, "compras": ["ver"]}})
    assert r.status_code == 403 and "propio rol" in r.json()["detail"]


def test_quien_no_es_admin_no_concede_permisos_que_no_tiene(client, empresa):
    r = client.post(f"{API}/seguridad/roles", headers=empresa["h_gestor"], json={"nombre": "Contador", "permisos": {"compras": ["ver"], "ventas": ["ver"]}})
    assert r.status_code == 403
    assert "ver compras" in r.json()["detail"] and "ver ventas" not in r.json()["detail"]
    r = client.post(f"{API}/seguridad/roles", headers=empresa["h_gestor"], json={"nombre": "Consulta", "permisos": {"ventas": ["ver"]}})
    assert r.status_code == 201


def test_quien_no_es_admin_no_toca_a_un_administrador(client, empresa):
    admin_id = empresa["admin"].id
    for metodo, sufijo, cuerpo in (("PUT", "", {"nombre_completo": "Otro Nombre"}), ("PATCH", "/estado", {"activo": False}), ("DELETE", "", None)):
        r = client.request(metodo, f"{API}/seguridad/usuarios/{admin_id}{sufijo}", headers=empresa["h_gestor"], json=cuerpo)
        assert r.status_code == 403, (metodo, r.text)


def test_degradar_al_ultimo_administrador_se_bloquea(client, empresa, usuario_factory, auth_headers_factory, rol_factory):
    """Dos administradores; uno pasa al otro a un rol normal: permitido. Luego
    el único que queda no puede ser degradado por nadie."""
    b = usuario_factory(empresa["tenant"], rol=empresa["admin"].rol)
    hb = auth_headers_factory(b)
    ventas = rol_factory(empresa["tenant"], nombre="Ventas", permisos={"ventas": ["ver"]})
    r = client.put(f"{API}/seguridad/usuarios/{empresa['admin'].id}", headers=hb, json={"rol_id": str(ventas.id)})
    assert r.status_code == 200
    # b es ahora el único admin; un gestor con usuarios:editar no puede tocarlo…
    r = client.put(f"{API}/seguridad/usuarios/{b.id}", headers=empresa["h_gestor"], json={"rol_id": str(ventas.id)})
    assert r.status_code == 403
    # …y el propio b no puede cambiarse de rol.
    r = client.put(f"{API}/seguridad/usuarios/{b.id}", headers=hb, json={"rol_id": str(ventas.id)})
    assert r.status_code == 409


# ---------------------------------------------------------------------------
# 5. Costos y márgenes
# ---------------------------------------------------------------------------
def test_sin_costos_ver_no_hay_costo_ni_margen(client, tenant_factory, rol_factory, usuario_factory, auth_headers_factory):
    tenant = tenant_factory()
    ha = auth_headers_factory(usuario_factory(tenant))
    descripcion, permisos_cajero = ROLES_DE_EJEMPLO["Cajero"]
    hc = auth_headers_factory(usuario_factory(tenant, rol=rol_factory(tenant, nombre="Cajero", permisos={**permisos_cajero, "productos": ["ver"], "insumos": ["ver"]})))

    insumo = client.post(f"{API}/inventario/insumos", headers=ha, json={"nombre": "Leche", "unidad": "L", "costo_unitario": "2500"}).json()
    prod = client.post(f"{API}/catalogo/productos", headers=ha, json={"nombre": "Café con leche", "precio": "4000",
                       "receta": [{"insumo_id": insumo["id"], "cantidad": "200", "unidad": "ml"}]}).json()
    assert prod["costo"] == "500.00"

    visto = client.get(f"{API}/catalogo/productos/{prod['id']}", headers=hc).json()
    assert visto["costo"] is None and visto["margen"] is None and visto["precio"] == "4000.00"
    assert client.get(f"{API}/inventario/insumos/{insumo['id']}", headers=hc).json()["costo_unitario"] is None


# ---------------------------------------------------------------------------
# Registro, sesión y catálogo
# ---------------------------------------------------------------------------
def test_el_registro_crea_administrador_y_roles_de_ejemplo(client, db_session):
    correo = f"{uuid.uuid4().hex[:8]}@nueva.com"
    token = client.post(f"{API}/seguridad/registro", json={"nombre_empresa": "Nueva SAS", "email": correo, "password": "clave-segura-123", "acepta_condiciones": True}).json()["access_token"]
    me = client.get(f"{API}/seguridad/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["es_administrador"] is True
    assert me["permisos"] == todos_los_permisos()
    roles = {r.nombre: r for r in db_session.query(Rol).filter(Rol.tenant_id == me["tenant"]["id"]).all()}
    assert set(roles) == {"Administrador", "Cajero", "Mesero", "Cocinero"}
    assert roles["Administrador"].es_administrador and not roles["Cajero"].es_administrador
    assert roles["Cajero"].permisos == ROLES_DE_EJEMPLO["Cajero"][1]


def test_el_catalogo_trae_solo_las_acciones_de_cada_modulo(client, empresa):
    catalogo = client.get(f"{API}/seguridad/permisos", headers=empresa["h_admin"]).json()
    por_clave = {m["clave"]: m for m in catalogo["modulos"]}
    assert por_clave["compras"]["acciones"] == ["ver", "crear", "cambiar_estado", "anular"]
    assert por_clave["costos"]["acciones"] == ["ver"]
    assert "editar" not in por_clave["ventas"]["acciones"]
    assert "eliminar" not in por_clave["ordenes"]["acciones"]
    assert por_clave["dashboard"]["acciones"] == ["ver"]


def test_un_rol_no_acepta_acciones_que_su_modulo_no_tiene(client, empresa):
    r = client.post(f"{API}/seguridad/roles", headers=empresa["h_admin"], json={"nombre": "Raro", "permisos": {"ventas": ["editar"]}})
    assert r.status_code == 422
