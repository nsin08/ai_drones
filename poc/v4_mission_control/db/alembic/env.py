from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import all v4 models so Alembic autogenerate can detect all tables.
# Works both locally (import from poc.v4_mission_control) and in Docker
# (code is copied to /app so module is just v4_mission_control).
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

try:
    from poc.v4_mission_control.models import (  # noqa: F401 — side-effect import
        Base, Command, Drone, DroneSnapshot, Event, Mission, Operator, Task
    )
    from poc.v4_mission_control.config import get_settings as _get_settings
except ModuleNotFoundError:
    from v4_mission_control.models import (  # noqa: F401 — side-effect import
        Base, Command, Drone, DroneSnapshot, Event, Mission, Operator, Task
    )
    from v4_mission_control.config import get_settings as _get_settings

target_metadata = Base.metadata

# Override DB URL from application settings (respects MC_V4_DATABASE_URL env var)
_settings = _get_settings()
config.set_main_option("sqlalchemy.url", _settings.DATABASE_URL)

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
