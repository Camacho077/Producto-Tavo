import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Permite importar "app.*" al correr alembic desde /backend
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.config import settings
from app.db.session import Base

# Importar todos los modelos para que Alembic los detecte en autogenerate
from app.db.models import Tenant  # noqa: F401
from app.modules.seguridad.models import Usuario, Rol  # noqa: F401
from app.modules.catalogo.models import Categoria, Producto, RecetaItem, Modificador, ComboItem  # noqa: F401
from app.modules.inventario.models import Insumo, MovimientoInsumo  # noqa: F401
from app.modules.compras.models import Proveedor, Compra, CompraItem, proveedor_insumos  # noqa: F401
from app.modules.ventas.models import Venta, VentaItem, Pedido, PedidoItem, PedidoEvento  # noqa: F401
from app.modules.ajustes.models import Zona, Mesa  # noqa: F401
from app.modules.imagenes.models import Imagen  # noqa: F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Usa la URL real de la app (desde .env) en vez de la del .ini.
# ALEMBIC_DATABASE_URL permite apuntar a otra base (ej. la de pytest) sin
# tocar la configuración global de la app — ver backend/tests/conftest.py.
config.set_main_option("sqlalchemy.url", os.environ.get("ALEMBIC_DATABASE_URL", settings.DATABASE_URL))

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
