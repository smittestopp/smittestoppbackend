"""pytest configuration"""
import asyncio
import base64
import datetime
import inspect
import time
from typing import Any, Dict
from unittest.mock import Mock, patch

import pyodbc
import pytest
from _pytest.monkeypatch import MonkeyPatch
from tornado import ioloop
from tornado.platform.asyncio import AsyncIOMainLoop

from corona_backend import devices, testsql
from corona_backend.fhi.handlers.helsenorge import HelseNorgeHandler

from . import mocks

time_fmt_str = "%Y-%m-%dT%H:%M:%SZ"

TEST_DEVICE_ID = "device_id1"
TEST_DEVICE_KEY_STR = "N06P7k1n6btKy2XKBp0vD/42KhDOUg7EE+ury9SB94G2zPSkld/mB0Ye1olgXvWCo+7piLMOzhHyrTmH9jMqXQ=="
TEST_2ND_DEVICE_KEY_STR = "BWJdrJe94M6ORNqDr/Z8NDFgR8majB1iomuNtLQiC5FrA++d35u8Y36Lcvq69w3hhDIC9Yla3mgw0WfaORoyJg=="
TEST_DEVICE_KEY = base64.b64decode(TEST_DEVICE_KEY_STR)
TEST_2ND_DEVICE_KEY = base64.b64decode(TEST_2ND_DEVICE_KEY_STR)


def pytest_collection_modifyitems(items):
    """add asyncio marker to all async tests"""
    for item in items:
        if inspect.iscoroutinefunction(item.obj):
            item.add_marker("asyncio")


@pytest.fixture
def io_loop(event_loop, request):
    """Make sure tornado io_loop is run on asyncio"""
    ioloop.IOLoop.configure(AsyncIOMainLoop)
    io_loop = AsyncIOMainLoop()
    io_loop.make_current()
    assert asyncio.get_event_loop() is event_loop
    assert io_loop.asyncio_loop is event_loop

    def _close():
        io_loop.clear_current()
        io_loop.close(all_fds=True)

    request.addfinalizer(_close)
    return io_loop


def make_async(f):
    async def inner(*args, **kwargs):
        return f(*args, **kwargs)

    return inner


def make_async_generator(f):
    async def inner(*args, **kwargs):
        for x in f(*args, **kwargs):
            yield x

    return inner


@pytest.fixture(scope="module")
def monkeymodule():
    """Makes monkey patching possible in module scope"""
    mpatch = MonkeyPatch()
    yield mpatch
    mpatch.undo()


@pytest.fixture(scope="module")
def setup_testdb(monkeymodule):
    testdb = testsql.setup_testdb()

    monkeymodule.setenv("SQL_SERVER", testdb.server)
    monkeymodule.setenv("SQL_CLIENT_ID", "")
    monkeymodule.setenv("SQL_PASSWORD", "Pa55w0rd")
    monkeymodule.setenv("SQL_DATABASE", testsql.TEST_DATABASE_NAME)
    monkeymodule.setenv("TEST_SQL_CONTAINER", "corona_test_sql_container")

    yield

    testdb.drop()


@pytest.fixture
def trucate_tables_after_test(event_loop):
    tables = []

    def _set(tables_to_be_truncated):
        for table in tables_to_be_truncated:
            tables.append(table)

    yield _set

    event_loop.run_until_complete(testsql.truncate_tables(tables))


@pytest.fixture
def db_user_serviceapi(monkeypatch):
    monkeypatch.setenv("SQL_USER", testsql.DB_USER_SERVICE_API)
    yield
    monkeypatch.undo()


@pytest.fixture
def db_user_registration(monkeypatch):
    monkeypatch.setenv("SQL_USER", testsql.DB_USER_REGISTRATION)
    yield
    monkeypatch.undo()


@pytest.fixture
def device(event_loop) -> Dict[str, Any]:

    device = event_loop.run_until_complete(devices.create_new_device())

    yield device

    # Tear down
    event_loop.run_until_complete(devices.delete_devices(device["deviceId"]))


@pytest.fixture
def sql_log_access_mock():
    mock = Mock(return_value=None)
    with patch("corona_backend.sql.log_access", new=make_async(mock)):
        yield mock


@pytest.fixture
def sql_log_access_connection_error():
    mock = Mock(side_effect=pyodbc.InterfaceError)
    with patch("corona_backend.sql.log_access", new=make_async(mock)):
        yield mock


@pytest.fixture
def sql_log_access_exception():
    mock = Mock(side_effect=pyodbc.IntegrityError)
    with patch("corona_backend.sql.log_access", new=make_async(mock)):
        yield mock


@pytest.fixture(scope="module")
def now_at_utc_mock():
    mock = datetime.datetime.strptime("2018-03-12T10:12:45Z", time_fmt_str)
    with patch("corona_backend.utils.now_at_utc", new=lambda: mock):
        yield mock


@pytest.fixture()
def redis_lookup_mock():
    # TODO: Should be possible to just use Mock/MagicMock
    mock = mocks.LookupHandlerRedisMock
    with patch("corona_backend.fhi.handlers.fhi.get_redis", new=mock):
        yield mock


@pytest.fixture()
def redis_lookup_result_mock():
    # TODO: Should be possible to just use Mock/MagicMock
    mock = mocks.LookupResultsHandlerRedisMock
    with patch("corona_backend.fhi.handlers.fhi.get_redis", new=mock):
        yield mock


@pytest.fixture()
def redis_lookup_no_result_mock():
    mock = mocks.LookupResultsHandlerRedisNoResultMock
    with patch("corona_backend.fhi.handlers.fhi.get_redis", new=mock):
        yield mock


@pytest.fixture()
def redis_lookup_no_result_analysis_in_progress_mock():
    mock = mocks.LookupResultsHandlerRedisAnalyisInProgressMock
    with patch("corona_backend.fhi.handlers.fhi.get_redis", new=mock):
        yield mock


@pytest.fixture()
def redis_lookup_result_analysis_error_mock():
    mock = mocks.LookupResultsHandlerRedisAnalyisErrorMock
    with patch("corona_backend.fhi.handlers.fhi.get_redis", new=mock):
        yield mock


@pytest.fixture()
def request_id_mock():
    mock = "1234"
    with patch("corona_backend.fhi.handlers.fhi.uuid.uuid4", new=lambda: mock):
        yield mock


@pytest.fixture()
def find_user_mock():
    mock = Mock(return_value={"displayName": "+0012341234", "logName": "Foo Name"})
    with patch("corona_backend.graph.find_user_by_phone", new=make_async(mock)):
        yield mock


@pytest.fixture()
def find_user_none_mock():
    mock = Mock(return_value=None)
    with patch("corona_backend.graph.find_user_by_phone", new=make_async(mock)):
        yield mock


@pytest.fixture()
def device_ids_mock():
    mock = Mock(return_value=["device_id1", "device_id2"])
    with patch(
        "corona_backend.graph.device_ids_for_user", new=make_async_generator(mock)
    ):
        yield mock


@pytest.fixture()
def device_ids_single_mock():
    mock = Mock(return_value="device_id3")
    with patch(
        "corona_backend.graph.device_ids_for_user", new=make_async_generator(mock)
    ):
        yield mock


@pytest.fixture()
def device_ids_empty_mock():
    mock = Mock(return_value=[])
    with patch(
        "corona_backend.graph.device_ids_for_user", new=make_async_generator(mock)
    ):
        yield mock


@pytest.fixture()
def user_for_device_mock():
    mock = Mock(
        side_effect=[
            {"displayName": "+0012341234"},
            {"displayName": "+0012341235"},
            {"displayName": "+0012341236"},
        ]
    )
    with patch("corona_backend.graph.user_for_device", new=make_async(mock)):
        yield mock


@pytest.fixture()
def get_device_mock():
    mock = Mock(
        side_effect=[
            {"deviceId": "device_id1", "lastActivityTime": "2020-03-12T10:11:45Z"},
            {"deviceId": "device_id2", "lastActivityTime": "2020-04-11T11:12:35Z"},
            {"deviceId": "device_id3", "lastActivityTime": "2020-04-11T11:12:36Z"},
        ]
    )
    with patch("corona_backend.devices.get_device", new=make_async(mock)):
        yield mock


@pytest.fixture()
def get_gps_event_mock():
    mock = Mock(
        return_value=(
            [
                {
                    "time_from": "2018-03-12T10:12:45Z",
                    "time_to": "2018-03-12T10:12:46Z",
                    "latitude": "59.890597",
                    "longitude": "10.533402",
                    "accuracy": 1,
                    "speed": 100,
                    "speed_accuracy": 1,
                    "altitude": 3,
                    "altitude_accuracy": 1,
                },
                {
                    "time_from": "2018-03-12T10:12:45Z",
                    "time_to": "2018-03-12T10:12:46Z",
                    "latitude": "59.890597",
                    "longitude": "10.533403",
                    "accuracy": 1,
                    "speed": 100,
                    "speed_accuracy": 1,
                    "altitude": 3,
                    "altitude_accuracy": 1,
                },
            ],
            2,
        )
    )
    with patch("corona_backend.sql.get_gps_events", new=make_async(mock)):
        yield mock


@pytest.fixture()
def get_access_log_mock():
    mock = Mock(
        return_value=(
            [
                {
                    "timestamp": "2018-03-12T10:12:45Z",
                    "phone_number": "+0012341234",
                    "person_name": "Don Juan",
                    "person_organization": "Some Organization",
                    "person_id": "",
                    "technical_organization": "Norsk Helsenett",
                    "legal_means": "Some legal means",
                    "count": 2,
                },
                {
                    "timestamp": "2018-03-12T10:12:45Z",
                    "phone_number": "+0012341233",
                    "person_name": "",
                    "person_organization": "Some Other Organization",
                    "person_id": "",
                    "technical_organization": "Norsk Helsenett",
                    "legal_means": "Some legal means",
                    "count": 1,
                },
            ],
            2,
        )
    )
    with patch("corona_backend.sql.get_access_log", new=make_async(mock)):
        yield mock


@pytest.fixture()
def deleted_nums_mock():
    mock = Mock(return_value=["+0012341234"])
    with patch("corona_backend.graph.extract_deleted_numbers", new=make_async(mock)):
        yield mock


@pytest.fixture()
def current_user_mock():
    def get_current_user_mock(*args, **kwargs):
        return dict(
            sub=1234,
            sub_given_name="Foo",
            sub_middle_name="Bar",
            sub_family_name="Baz",
            _phonenumber="+0012341234",
        )

    mock = get_current_user_mock()
    with patch.object(HelseNorgeHandler, "get_current_user", new=get_current_user_mock):
        yield mock


@pytest.fixture()
def user_deletion_mock():
    mock = Mock()
    with patch("corona_backend.graph.process_user_deletion", new=make_async(mock)):
        yield mock


@pytest.fixture()
def store_consent_revoked_mock():
    mock = Mock()
    with patch("corona_backend.graph.store_consent_revoked", new=make_async(mock)):
        yield mock


@pytest.fixture()
def generate_pin_mock():
    mock = Mock(side_effect=["pin_code_1", "pin_code_2"])
    with patch("corona_backend.pin.generate_pin", new=mock):
        yield mock


@pytest.fixture()
def get_latest_pin_code_after_threshold_mock():
    mock = Mock(return_value=None)
    with patch(
        "corona_backend.pin.get_latest_pin_code_after_threshold", new=make_async(mock),
    ):
        yield mock


@pytest.fixture()
def store_pin_code_mock():
    mock = Mock()
    with patch("corona_backend.pin.store_pin_code", new=make_async(mock)):
        yield mock


@pytest.fixture
def get_device_mock_auth():
    mock_data_1 = {
        "deviceId": TEST_DEVICE_ID,
        "generationId": "generationId1",
        "etag": "etag1",
        "connectionState": "Disconnected",
        "status": "enabled",
        "statusReason": None,
        "connectionStateUpdatedTime": "0001-01-01T00:00:00Z",
        "statusUpdatedTime": "0001-01-01T00:00:00Z",
        "lastActivityTime": "0001-01-01T00:00:00Z",
        "cloudToDeviceMessageCount": 0,
        "authentication": {
            "symmetricKey": {
                "primaryKey": f"{TEST_DEVICE_KEY_STR}",
                "secondaryKey": f"{TEST_2ND_DEVICE_KEY_STR}",
            },
            "x509Thumbprint": {"primaryThumbprint": None, "secondaryThumbprint": None,},
            "type": "sas",
        },
        "capabilities": {"iotEdge": False,},
    }
    mock_data_2 = {
        "authentication": {
            "symmetricKey": {
                "primaryKey": f"{TEST_DEVICE_KEY_STR}",
                "secondaryKey": f"{TEST_2ND_DEVICE_KEY_STR}",
            }
        }
    }

    def m(device_id):
        return {TEST_DEVICE_ID: mock_data_1, "deviceId2": mock_data_2}.get(device_id)

    with patch("corona_backend.devices.get_device", new=make_async(m)):
        yield m


@pytest.fixture
def timestamp():
    # return a valid timestamp str
    return str(int(time.time()))


@pytest.fixture()
def phone_number_for_device_id_mock():
    m = Mock(return_value="+0013371337")
    with patch(
        "corona_backend.onboarding.app.phone_number_for_device_id", new=make_async(m)
    ):
        yield m


@pytest.fixture()
def phone_number_for_device_id_mock_no_pin_associated():
    m = Mock(return_value="+0013371338")
    with patch(
        "corona_backend.onboarding.app.phone_number_for_device_id", new=make_async(m)
    ):
        yield m


@pytest.fixture()
def get_pin_codes_mock():
    m = Mock(return_value=["pin_code_1", "pin_code_2"])
    with patch("corona_backend.onboarding.app.get_pin_codes", new=make_async(m)):
        yield m


@pytest.fixture()
def get_empty_pin_codes_mock():
    m = Mock(return_value=[])
    with patch("corona_backend.onboarding.app.get_pin_codes", new=make_async(m)):
        yield m


@pytest.fixture()
def request_contact_ids_mock():
    m = Mock(return_value=["123", "456", "789"])
    with patch("corona_backend.sql.request_contact_ids", new=make_async(m)):
        yield m


@pytest.fixture()
def empty_phone_number_for_device_id_mock():
    m = Mock(return_value=None)
    with patch(
        "corona_backend.onboarding.app.phone_number_for_device_id", new=make_async(m)
    ):
        yield m
