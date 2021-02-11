"""alembic logging setup"""
import logging
import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from sqlalchemy import create_engine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    """Get the sqlalchemy connection url from environment variables"""

    params = {
        "DRIVER": os.environ.get("ODBC_DRIVER", "{ODBC Driver 17 for SQL Server}"),
        "PORT": os.environ.get("SQL_PORT", "1433"),
        "SERVER": os.environ["SQL_SERVER"],
        "DATABASE": os.environ.get("SQL_DATABASE", ""),
        "UID": os.environ.get("SQL_USER", "sa"),
        "PWD": os.environ.get("SQL_PASSWORD", "Pa55w0rd"),
    }

    log = logging.getLogger("alembic")
    log.info("Connecting to {}@{}:{}/{}".format(params['UID'], params['SERVER'], params['PORT'], params['DATABASE']))
    connection_string = ";".join("{}={}".format(key, value) for key, value in params.items())

    return "mssql+pyodbc:///?odbc_connect={}".format(quote_plus(connection_string))


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """

    log = logging.getLogger("alembic")
    log.info("Run migrations offline")

    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    log = logging.getLogger("alembic")
    log.info("Run migrations online")

    connectable = create_engine(get_url())

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

