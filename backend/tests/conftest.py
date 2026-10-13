"""
Fixtures compartidas de pytest. La suite corre contra un Postgres real
(la misma imagen de infra/docker-compose.yml), en una base de datos de test
separada de la de desarrollo (`TEST_DATABASE_URL`), nunca contra SQLite:
los modelos usan UUID nativo de Postgres y la idea es probar el mismo motor
que se usa en producción.

Requiere tener el contenedor de Postgres corriendo:
    docker compose -f infra/docker-compose.yml up -d db
"""
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.db.models import Tenant
from app.db.session import get_db
from app.main import app
from app.modules.caja.models import Venta
from app.modules.inventario.models import MovimientoInsumo
from app.modules.ordenes.models import Orden
from app.modules.seguridad.models import Rol, Usuario

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _ensure_database_exists(database_url: str) -> None:
    db_name = database_url.rsplit("/", 1)[-1]
    maintenance_url = database_url.rsplit("/", 1)[0] + "/postgres"
    engine = create_engine(maintenance_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            existe = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}
            ).first()
            if not existe:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def db_engine():
    _ensure_database_exists(settings.TEST_DATABASE_URL)

    reset_engine = create_engine(settings.TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with reset_engine.connect() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    reset_engine.dispose()

    os.environ["ALEMBIC_DATABASE_URL"] = settings.TEST_DATABASE_URL
    try:
        alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)

    engine = create_engine(settings.TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    """Cada test corre dentro de un savepoint que se revierte al terminar,
    así los tests no se contaminan entre sí sin tener que recrear el schema."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


# ---------- Factories de datos de prueba ----------
@pytest.fixture()
def tenant_factory(db_session: Session):
    def _crear(**kwargs):
        tenant = Tenant(
            nombre_empresa=kwargs.pop("nombre_empresa", f"Empresa {uuid.uuid4().hex[:8]}"),
            plan=kwargs.pop("plan", "pro_ia"),
            theme_config=kwargs.pop("theme_config", {}),
            modulos_activos=kwargs.pop("modulos_activos", []),
            **kwargs,
        )
        db_session.add(tenant)
        db_session.flush()
        return tenant

    return _crear


@pytest.fixture()
def rol_factory(db_session: Session):
    """Por defecto crea un rol ADMINISTRADOR: la mayoría de los tests prueban
    reglas de negocio, no permisos, y así no dependen del catálogo. Los tests
    de permisos (test_permisos.py) crean roles limitados con
    `es_administrador=False, permisos={...}`."""

    def _crear(tenant, **kwargs):
        if "permisos" in kwargs and "es_administrador" not in kwargs:
            kwargs["es_administrador"] = False
        rol = Rol(
            tenant_id=tenant.id,
            nombre=kwargs.pop("nombre", f"Rol {uuid.uuid4().hex[:8]}"),
            descripcion=kwargs.pop("descripcion", None),
            es_administrador=kwargs.pop("es_administrador", True),
            **kwargs,
        )
        db_session.add(rol)
        db_session.flush()
        return rol

    return _crear


@pytest.fixture()
def usuario_factory(db_session: Session, rol_factory):
    def _crear(tenant, rol=None, **kwargs):
        if rol is None:
            rol = rol_factory(tenant)
        usuario = Usuario(
            tenant_id=tenant.id,
            nombre_completo=kwargs.pop("nombre_completo", "Usuario de Prueba"),
            email=kwargs.pop("email", f"{uuid.uuid4().hex[:10]}@test.com"),
            hashed_password=hash_password(kwargs.pop("password", "clave-segura-123")),
            activo=kwargs.pop("activo", True),
            rol_id=rol.id,
            **kwargs,
        )
        db_session.add(usuario)
        db_session.flush()
        return usuario

    return _crear


@pytest.fixture()
def auth_headers_factory():
    def _crear(usuario: Usuario) -> dict:
        token = create_access_token(data={"sub": str(usuario.id), "tenant_id": str(usuario.tenant_id)})
        return {"Authorization": f"Bearer {token}"}

    return _crear


# ---------- Inventario por la vía correcta (2026-10-12) ----------
# El inventario es de INSUMOS: un plato se vende si alcanzan los insumos de
# su receta. Para las pruebas que solo necesitan "un producto que se pueda
# vender", `crear_producto` arma un plato cuya receta gasta UNA unidad de un
# insumo propio ("Base de <nombre>"), y `dar_stock` le compra existencias a
# ese insumo: así "stock del producto" sigue teniendo sentido.
API_V1 = "/api/v1"
PROVEEDOR_PRUEBA = {
    "tipo_persona": "juridica",
    "nit": "890903938-8",
    "razon_social": "Proveedor de Pruebas",
    "representante_nombre": "Ana Prueba",
}


def crear_insumo(client, headers, nombre, unidad="unidad", minimo="0", costo="0", existencia="0", grupo=None):
    resp = client.post(f"{API_V1}/inventario/insumos", headers=headers, json={
        "nombre": nombre, "unidad": unidad, "minimo": minimo, "costo_unitario": costo,
        "existencia_inicial": existencia, "grupo": grupo,
    })
    assert resp.status_code == 201, resp.json()
    return resp.json()


def crear_plato(client, headers, nombre, precio="1000", receta=(), **extra):
    """`receta`: [(insumo_id, cantidad, unidad)] o [(insumo_id, cantidad, unidad, merma)]."""
    lineas = [
        {"insumo_id": l[0], "cantidad": str(l[1]), "unidad": l[2], **({"merma_porcentaje": str(l[3])} if len(l) > 3 else {})}
        for l in receta
    ]
    resp = client.post(f"{API_V1}/catalogo/productos", headers=headers, json={"nombre": nombre, "precio": precio, "receta": lineas, **extra})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def crear_producto(client, headers, nombre, precio="1000", costo="0", **extra):
    """Plato con receta de UNA unidad de su propio insumo."""
    insumo = crear_insumo(client, headers, f"Base de {nombre}", costo=costo)
    return crear_plato(client, headers, nombre, precio, receta=[(insumo["id"], "1", "unidad")], **extra)


def proveedor_de_prueba(client, headers):
    existentes = client.get(f"{API_V1}/compras/proveedores", headers=headers, params={"q": "890903938"}).json()["items"]
    if existentes:
        return existentes[0]
    return client.post(f"{API_V1}/compras/proveedores", headers=headers, json=PROVEEDOR_PRUEBA).json()


def comprar(client, headers, lineas, confirmar=True, fecha="2026-01-01T09:00:00"):
    """`lineas`: [(insumo_id, cantidad, unidad, precio por esa unidad)]."""
    proveedor = proveedor_de_prueba(client, headers)
    resp = client.post(f"{API_V1}/compras/compras", headers=headers, json={
        "proveedor_id": proveedor["id"], "fecha": fecha, "confirmar": confirmar,
        "items": [{"insumo_id": i, "cantidad": str(c), "unidad": u, "precio_unitario": str(p)} for i, c, u, p in lineas],
    })
    assert resp.status_code == 201, resp.json()
    return resp.json()


def dar_stock(client, headers, producto_id, cantidad, precio="100"):
    """Compra `cantidad` del insumo de un producto hecho con `crear_producto`."""
    plato = client.get(f"{API_V1}/catalogo/productos/{producto_id}", headers=headers).json()
    insumo_id = plato["receta"][0]["insumo_id"]
    return comprar(client, headers, [(insumo_id, cantidad, "unidad", precio)])


def existencia(client, headers, insumo_id):
    return Decimal(client.get(f"{API_V1}/inventario/insumos/{insumo_id}", headers=headers).json()["existencia"])


def stock_de(client, headers, producto_id):
    """Existencia del insumo base de un producto de `crear_producto`."""
    plato = client.get(f"{API_V1}/catalogo/productos/{producto_id}", headers=headers).json()
    return existencia(client, headers, plato["receta"][0]["insumo_id"])


# ---------- Vender por la vía real (fase 6, 2026-10-12) ----------
# Una venta ya no se escribe suelta: es el COBRO de una orden. `vender` toma
# la orden (para llevar), abre la caja si hace falta y la cobra en un solo
# medio. Con `fecha` (y la sesión de la base) la lleva a ese instante —
# venta, orden y movimientos de inventario—, para probar el dashboard y la IA
# con historia: la API siempre registra la hora real del servidor.
def abrir_caja(client, headers, base="0"):
    actual = client.get(f"{API_V1}/caja/actual", headers=headers).json()["caja"]
    if actual:
        return actual
    resp = client.post(f"{API_V1}/caja/abrir", headers=headers, json={"base_inicial": base})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def tomar_orden(client, headers, items, **datos):
    """`items`: [(producto_id, cantidad)] o [producto_id]."""
    lineas = [{"producto_id": i[0], "cantidad": i[1]} if isinstance(i, tuple) else {"producto_id": i} for i in items]
    resp = client.post(f"{API_V1}/ordenes", headers=headers, json={"tipo": "llevar", **datos, "items": lineas})
    assert resp.status_code == 201, resp.json()
    return resp.json()


def cobrar_orden(client, headers, orden, medio="efectivo", propina="0"):
    abrir_caja(client, headers)
    pendiente = next(o for o in client.get(f"{API_V1}/caja/por-cobrar", headers=headers).json() if o["id"] == orden["id"])
    total = str(Decimal(pendiente["por_cobrar"]) + Decimal(propina))
    resp = client.post(f"{API_V1}/caja/cobros", headers=headers, json={
        "orden_id": orden["id"], "propina": propina, "pagos": [{"medio": medio, "monto": total}],
    })
    assert resp.status_code == 201, resp.json()
    return resp.json()


def vender(client, headers, items, *, fecha=None, db=None, medio="efectivo", cliente=None):
    datos = {"cliente_nombre": cliente} if cliente else {}
    venta = cobrar_orden(client, headers, tomar_orden(client, headers, items, **datos), medio)
    if fecha is not None:
        llevar_a_fecha(db, venta, fecha)
    return venta


def llevar_a_fecha(db, venta, fecha):
    instante = datetime.fromisoformat(fecha) if isinstance(fecha, str) else fecha
    if instante.tzinfo is not None:
        instante = instante.astimezone(timezone.utc).replace(tzinfo=None)
    v = db.get(Venta, venta["id"])
    v.fecha = instante
    orden = db.get(Orden, v.orden_id)
    orden.created_at = instante
    for mov in db.query(MovimientoInsumo).filter(MovimientoInsumo.documento_id == orden.id):
        mov.created_at = instante
    db.commit()
