import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app import models  # noqa: F401
from app.core.config import settings
from app.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
if config.config_file_name is not None:
    # Preserve Uvicorn/FastAPI and application loggers. The default
    # disable_existing_loggers=True hid startup exceptions in production.
    fileConfig(config.config_file_name, disable_existing_loggers=False)
logger = logging.getLogger("vexion.migrations")
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
    logger.warning("VEXION migration diagnostic: creating migration engine")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    logger.warning("VEXION migration diagnostic: opening database connection")
    with connectable.connect() as connection:
        logger.warning(
            "VEXION migration diagnostic: database connection opened (dialect=%s)",
            connection.dialect.name,
        )
        lock_acquired = False
        try:
            if connection.dialect.name == "postgresql":
                logger.warning("VEXION migration diagnostic: waiting for advisory lock")
                connection.exec_driver_sql(
                    "SELECT pg_advisory_lock(%s)", (MIGRATION_LOCK_ID,)
                )
                lock_acquired = True
                logger.warning("VEXION migration diagnostic: advisory lock acquired")
                # The SELECT above triggers SQLAlchemy autobegin. Clear that
                # implicit transaction before Alembic creates its migration
                # transaction; the session-level advisory lock survives commit.
                if connection.in_transaction():
                    connection.commit()
                    logger.warning(
                        "VEXION migration diagnostic: cleared advisory-lock query transaction"
                    )
            context.configure(connection=connection, target_metadata=target_metadata)
            logger.warning("VEXION migration diagnostic: running Alembic migrations")
            with context.begin_transaction():
                context.run_migrations()
            logger.warning("VEXION migration diagnostic: Alembic migrations completed")
        finally:
            if lock_acquired:
                logger.warning("VEXION migration diagnostic: releasing advisory lock")
                connection.exec_driver_sql(
                    "SELECT pg_advisory_unlock(%s)", (MIGRATION_LOCK_ID,)
                )
                logger.warning("VEXION migration diagnostic: advisory lock released")
    connectable.dispose()
    logger.warning("VEXION migration diagnostic: migration connection closed")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
