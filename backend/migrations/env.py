from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401
from app.core.config import settings
from app.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

# Every API instance runs Alembic during startup. Serialize migrations at the
# database level so simultaneous Render instances cannot race on schema DDL.
MIGRATION_LOCK_ID = 731904218


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        lock_acquired = False
        try:
            if connection.dialect.name == "postgresql":
                connection.exec_driver_sql(
                    "SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,)
                )
                lock_acquired = True
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if lock_acquired:
                connection.exec_driver_sql(
                    "SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,)
                )


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
