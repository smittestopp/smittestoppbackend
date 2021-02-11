import os
from unittest import mock

import pytest

from corona_backend import sql


async def test_connect_to_database():
    # mock a database and test if sql code can successfully connect to the mocked db

    db_string = "sql_db"
    with mock.patch("pyodbc.connect") as mock_connect:
        mock_connect.return_value = db_string
        db = await sql.connect_to_database()
        mock_connect.assert_called_once()

        params = {
            k.strip(): v.strip()
            for k, v in [x.split("=") for x in mock_connect.call_args[0][0].split(";")]
        }
        assert params.get("SERVER") == os.environ["SQL_SERVER"]
        assert params.get("DATABASE") == os.environ["SQL_DATABASE"]
        assert db == db_string


async def test_connect_to_database_retries():
    # mock a database and test if the sql code can retry and connect to the mocked db

    class TestException(Exception):
        pass

    with mock.patch("pyodbc.connect") as mock_connect:
        mock_connect.side_effect = TestException("test sql connect retries")
        with pytest.raises(TestException):
            await sql.connect_to_database()
        assert mock_connect.call_count == sql.CONNECT_RETRIES
