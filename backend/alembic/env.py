import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Añadir la raíz del proyecto (directorio backend) al sys.path
# para que Alembic pueda encontrar los módulos de la aplicación
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Navegar un nivel hacia arriba desde alembic/env.py para llegar a /app
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.append(PROJECT_ROOT)

# Importar la Base de nuestros modelos y la configuración
from app.db.session import Base
from app.core.config import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interprete the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata # <--- NUESTRA BASE DE MODELOS

# other values from the config, defined by the needs of env.py,
# can be acquired: my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_url():
    """Obtiene la URL de la base de datos desde la configuración.
    Alembic generalmente funciona mejor con drivers síncronos como psycopg2.
    Reemplazamos 'postgresql+asyncpg' por 'postgresql'.
    """
    # Usar la representación de cadena explícita de Pydantic
    # o construirla manualmente si es necesario
    if settings.DATABASE_URL:
        db_url = str(settings.DATABASE_URL) # Reintentar con str(), puede que funcione ahora
    else:
        raise ValueError("DATABASE_URL no está configurada")

    if db_url.startswith("postgresql+asyncpg"):
        db_url = db_url.replace("+asyncpg", "")
    return db_url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_url()
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
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
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