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


# ---------- Stock por la vía correcta: una compra confirmada ----------
PROVEEDOR_PRUEBA = {
    "tipo_persona": "juridica",
    "nit": "890903938-8",
    "razon_social": "Proveedor de Pruebas",
    "representante_nombre": "Ana Prueba",
}


def dar_stock(client, headers, producto_id, cantidad, precio="100"):
    """El stock ya no se escribe en el producto: nace en 0 y solo lo mueven
    compras y ventas. Este helper registra una compra confirmada."""
    proveedor = client.post("/api/v1/compras/proveedores", headers=headers, json=PROVEEDOR_PRUEBA).json()
    resp = client.post(
        "/api/v1/compras/compras",
        headers=headers,
        json={
            "proveedor_id": proveedor["id"],
            "fecha": "2026-01-01T09:00:00",
            "confirmar": True,
            "items": [{"producto_id": producto_id, "cantidad": cantidad, "precio_unitario": precio}],
        },
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()
