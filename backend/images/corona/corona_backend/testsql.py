import os
from contextlib import contextmanager

import docker
import pyodbc
from _pytest.monkeypatch import MonkeyPatch

from corona_backend.sql import with_db

SQL_SERVER = os.environ["SQL_SERVER"]
TEST_SQL_CONTAINER = os.environ.get("TEST_SQL_CONTAINER")
TEST_DATABASE_NAME = "tmp_testdb"

DB_USER_ANALYTICS = "fhi-smittestop-analytics-login"
DB_USER_SLETTESERVICE = "fhi-smittestop-sletteservice-login"
DB_USER_SERVICE_API = "fhi-smittestop-serviceapi-login"
DB_USER_SQL_IMPORT = "fhi-smittestop-sqlimport-login"
DB_USER_REGISTRATION = "fhi-smittestop-registration-login"


class TestDb(object):
    def __init__(self, conn, server):
        self.conn = conn
        self.server = server

    def drop(self):
        pass
        # self.conn.execute(f"DROP DATABASE {TEST_DATABASE_NAME}").commit()
        # self.conn.close()


@contextmanager
def set_db_user(user):
    mpatch = MonkeyPatch()
    mpatch.setenv("SQL_USER", user)
    try:
        yield
    finally:
        mpatch.undo()


async def truncate_tables(tables):
    """Removes all data from table

    Used for test cleanup.
    Must only be used in tests...
    """

    @with_db()
    def do(db):
        cursor = db.cursor()
        for table in tables:
            cursor.execute(f"TRUNCATE TABLE {table}")
        cursor.commit()

    with set_db_user("SA"):
        await do()


def connect_to_testdb_server(server):
    params = {
        "DRIVER": "{ODBC Driver 17 for SQL Server}",
        "PORT": "1433",
        "SERVER": server,
        "DATABASE": "",
        "UID": "SA",
        "PWD": "Pa55w0rd",
    }

    connection_string = ";".join(f"{key}={value}" for key, value in params.items())

    return pyodbc.connect(connection_string, ansi=True)


docker_client = docker.from_env()


def setup_testdb():
    """ Runs a mssql database in a docker container for testing.

    Can only be called when the docker container `corona_test_sql_container`
    is running (see /corona/sql/testsql).

    Drops `tmp_testdb` if exists and creates a new one with the same name.
    Sets database connection environment variables to point to tmp_testdb.
    Uses docker sdk to run alembic migrations inside `corona_test_sql_container`

    When tests are completed `tmp_testdb` should be dropped.

    Returns: Database connection.
    """

    testdb_container = docker_client.containers.get("corona_test_sql_container")
    testdb_container_ip = testdb_container.attrs["NetworkSettings"]["IPAddress"]

    conn = connect_to_testdb_server(testdb_container_ip)
    conn.autocommit = True
    conn.execute(
        f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME}; CREATE DATABASE {TEST_DATABASE_NAME}"
    )

    output = testdb_container.exec_run(
        "alembic upgrade head",
        stdout=True,
        environment={"SQL_DATABASE": f"{TEST_DATABASE_NAME}"},
    )
    if output[0] != 0:
        raise Exception(f"Failed to migrate {TEST_DATABASE_NAME}", output[1])

    return TestDb(conn=conn, server=testdb_container_ip)
