import asyncio
import base64
import json
import os
import random
import uuid
from unittest import mock

import pytest
import tornado
from testfixtures import LogCapture
from tornado.httpclient import HTTPRequest

import corona_backend.handlers
import corona_backend.onboarding.app
from corona_backend import devices, graph
from corona_backend import middleware as mw
from corona_backend import sql
from corona_backend import test as test_utils
from corona_backend import testsql, utils
from corona_backend.handlers import common_endpoints

from .conftest import TEST_DEVICE_ID, TEST_DEVICE_KEY

TEST_PHONE_NUMBER = f"+00{random.randint(1,9999):06}"
TEST_PHONE_NUMBER = "+00001234"
MASKED_TEST_PHONE_NUMBER = utils.mask_phone(TEST_PHONE_NUMBER)

TEST_TOKEN = "secret"
CONSECUTIVE_FAILURE_LIMIT = 2


@pytest.fixture(scope="module", autouse=True)
async def testsetup(setup_testdb):
    """Setup for handler tests.
    Creates testdb and tears down testdb when tests complete."""


def get_test_payload(phonenumber=TEST_PHONE_NUMBER):
    return {
        "_access_token": TEST_TOKEN,
        "_phonenumber": phonenumber,
    }


def post_request_args(phone_number=TEST_PHONE_NUMBER):
    return dict(
        method="POST",
        body=b"",
        headers={"Authorization": f"Bearer {TEST_TOKEN}", "Test-Number": phone_number},
    )


@pytest.fixture
def app():
    with mock.patch.object(corona_backend.pin, "PIN_ENABLED", True):
        endpoints = corona_backend.onboarding.app.endpoints() + common_endpoints()
    return tornado.web.Application(
        endpoints,
        consecutive_failures=0,
        consecutive_failure_limit=CONSECUTIVE_FAILURE_LIMIT,
    )


pytest_usefixtures = "http_server"


@pytest.mark.parametrize("pin_enabled", (True, False))
def test_pin_enabled_endpoints(pin_enabled):
    with mock.patch.object(corona_backend.pin, "PIN_ENABLED", pin_enabled):
        endpoints = corona_backend.onboarding.app.endpoints()
    paths = [ep[0] for ep in endpoints]
    if pin_enabled:
        assert "/pin" in paths
    else:
        assert "/pin" not in paths


async def test_HealthHandler_response(app, http_client, base_url):
    assert base_url != "/"

    response = await http_client.fetch(f"{base_url}/health")

    assert response.code == 200
    assert response.body == b"ok"


async def test_register_device(http_client, base_url):

    os.environ["TESTER_NUMBERS"] += f",{TEST_PHONE_NUMBER}"

    await clean_test_user()
    await test_utils.create_test_user(TEST_PHONE_NUMBER)

    capture = LogCapture()

    # Get the user
    user = await graph.find_user_by_phone(TEST_PHONE_NUMBER)

    # Remove all devices associated with user
    await graph.dissociate_user_devices(user)

    capture.check_present(
        (
            "tornado.application",
            "INFO",
            f"Dissociating devices from {utils.mask_phone(TEST_PHONE_NUMBER)}",
        )
    )

    with mock.patch.object(
        corona_backend.onboarding.app.RegisterDeviceHandler, "get_current_user"
    ) as m:

        m.return_value = get_test_payload()
        response = await http_client.fetch(
            f"{base_url}/register-device", **post_request_args()
        )
        # Check that `get_current_user` was called
        m.assert_any_call()

        capture.check_present(
            (
                "tornado.application",
                "INFO",
                "Tester {0} is impersonating test user {0}".format(TEST_PHONE_NUMBER),
            )
        )

        assert response.code == 200

        body = json.loads(response.body)

        # Check phone number
        assert body["PhoneNumber"] == TEST_PHONE_NUMBER
        # Check keys in connection string
        for key in ["HostName=", "DeviceId=", "SharedAccessKey="]:
            assert key in body["ConnectionString"]

        # Check that we have the correct device_id

        # Get all devices associated with user
        groups = await graph.graph_request(f"/users/{user['id']}/memberOf")
        # For this test user we should only have one device
        assert len(groups) == 1
        device = groups[0]
        assert body["DeviceId"] == device["displayName"]

    # Clean up
    await graph.dissociate_user_devices(user)
    capture.uninstall()


async def test_register_device_without_test_number_in_test_enviroment(
    http_client, base_url
):

    phone_number = os.environ.get("TESTER_NUMBERS", "+00").split(",")[0]
    if phone_number.startswith("+00"):
        return

    capture = LogCapture()
    with mock.patch.object(
        corona_backend.onboarding.app.RegisterDeviceHandler, "get_current_user"
    ) as m:

        m.return_value = get_test_payload(phone_number)
        with pytest.raises(tornado.httpclient.HTTPClientError) as e:
            await http_client.fetch(
                f"{base_url}/register-device", **post_request_args(phone_number)
            )
    assert e.value.code == 403
    capture.check_present(
        (
            "tornado.application",
            "ERROR",
            "Tester {0} attempted to impersonate non-test user {0}".format(
                phone_number
            ),
        )
    )
    capture.uninstall()


async def test_register_device_with_consent_revoked_resets_consent(
    http_client, base_url
):

    await clean_test_user()
    await test_utils.create_test_user(TEST_PHONE_NUMBER)

    os.environ["TESTER_NUMBERS"] += f",{TEST_PHONE_NUMBER}"

    capture = LogCapture()

    # Get the user
    user = await graph.find_user_by_phone(TEST_PHONE_NUMBER)
    await graph.store_consent_revoked(user)

    capture.check_present(
        (
            "tornado.application",
            "INFO",
            f"Storing revoked consent on user {utils.mask_phone(TEST_PHONE_NUMBER)}",
        )
    )

    user = await graph.find_user_by_phone(TEST_PHONE_NUMBER)

    assert graph.extension_attr_name("consentRevoked") in user
    assert user[graph.extension_attr_name("consentRevoked")] is True

    with mock.patch.object(
        corona_backend.onboarding.app.RegisterDeviceHandler, "get_current_user"
    ) as m:

        m.return_value = get_test_payload()
        await http_client.fetch(f"{base_url}/register-device", **post_request_args())

    capture.check_present(
        (
            "tornado.application",
            "WARNING",
            f"Clearing revoked consent on user {utils.mask_phone(TEST_PHONE_NUMBER)}",
        )
    )
    user = await graph.find_user_by_phone(TEST_PHONE_NUMBER)
    assert graph.extension_attr_name("consentRevoked") not in user

    capture.uninstall()


async def test_register_device_create_new_device_timeout_raises_500(
    http_client, base_url, app,
):
    async def timeout_error(*args, **kwargs):
        await asyncio.sleep(
            float(corona_backend.onboarding.app.PROVISIONING_TIMEOUT) + 1
        )

    device_future = asyncio.ensure_future(timeout_error())

    app.settings["consecutive_failures"] = 0
    app.settings["consecutive_failure_limit"] = 2

    capture = LogCapture("tornado.application")

    with mock.patch.object(
        corona_backend.onboarding.app.RegisterDeviceHandler, "get_current_user"
    ) as m_auth:
        m_auth.return_value = get_test_payload()

        with mock.patch.object(devices, "create_new_device") as m_create_device:

            m_create_device.return_value = device_future

            with pytest.raises(tornado.httpclient.HTTPClientError) as e:
                await http_client.fetch(
                    f"{base_url}/register-device", **post_request_args()
                )

            assert e.value.code == 500

    assert app.settings["consecutive_failures"] == 1
    capture.check_present(
        (
            "tornado.application",
            "ERROR",
            "Timeout registering device (1/2 before abort)",
        ),
    )
    capture.uninstall()


async def test_register_device_create_new_device_reach_consecutive_failure_limit_raises_500(  # noqa
    http_client, base_url, app,
):
    async def timeout_error(*args, **kwargs):
        await asyncio.sleep(
            float(corona_backend.onboarding.app.PROVISIONING_TIMEOUT) + 1
        )

    device_future = asyncio.ensure_future(timeout_error())

    app.settings["consecutive_failures"] = 0
    app.settings["consecutive_failure_limit"] = 1

    capture = LogCapture("tornado.application")

    with mock.patch.object(
        corona_backend.onboarding.app.RegisterDeviceHandler, "get_current_user"
    ) as m_auth:
        m_auth.return_value = get_test_payload()

        with mock.patch.object(devices, "create_new_device") as m_create_device:
            m_create_device.return_value = device_future

            with pytest.raises(tornado.httpclient.HTTPClientError) as e:
                await http_client.fetch(
                    f"{base_url}/register-device", **post_request_args()
                )

            assert e.value.code == 500

    assert app.settings["consecutive_failures"] == 1

    # Check log
    capture.check_present(
        (
            "tornado.application",
            "ERROR",
            "Timeout registering device (1/1 before abort)",
        ),
        (
            "tornado.application",
            "CRITICAL",
            "Aborting due to consecutive failure limit!",
        ),
    )
    capture.uninstall()


async def clean_test_user(phone_number=TEST_PHONE_NUMBER):
    try:
        user = await graph.find_user_by_phone(phone_number)
    except Exception:
        pass
    else:
        if user is not None:
            await graph.delete_user(user)


async def test_revoke_consent_handler_response(http_client, base_url):

    await clean_test_user()

    await test_utils.create_test_user(TEST_PHONE_NUMBER)

    capture = LogCapture("tornado.application")

    with mock.patch.object(
        corona_backend.onboarding.app.RevokeConsentHandler, "get_current_user"
    ) as m_auth:

        m_auth.return_value = get_test_payload()

        response = await http_client.fetch(
            f"{base_url}/revoke-consent", **post_request_args()
        )

        assert response.code == 200

        body = json.loads(response.body)

        assert body["Status"] == "Success"
        assert "Your phone number is no longer associated" in body["Message"]

    capture.check_present(
        (
            "tornado.application",
            "INFO",
            f"Storing revoked consent on user {MASKED_TEST_PHONE_NUMBER}",
        ),
        (
            "tornado.application",
            "INFO",
            f"Dissociating devices from {MASKED_TEST_PHONE_NUMBER}",
        ),
        ("tornado.application", "INFO", f"Deleting user {MASKED_TEST_PHONE_NUMBER}",),
    )

    capture.uninstall()


async def async_pass():
    """ monkey patch for MagicMock
    """
    pass


class AsyncMockPass(mock.MagicMock):
    def __await__(self):
        return async_pass().__await__()


async def async_return_one():
    """ monkey patch for MagicMock
    """
    fut = asyncio.Future()
    fut.set_result([1])
    return await fut


class AsyncMockReturnOne(mock.MagicMock):
    def __await__(self):
        return async_return_one().__await__()


async def test_revoke_consent_handler_store_consent_revoked_called(
    http_client, base_url
):

    await clean_test_user()

    user_resp = await test_utils.create_test_user(TEST_PHONE_NUMBER)

    with mock.patch.object(
        corona_backend.onboarding.app.RevokeConsentHandler, "get_current_user"
    ) as m_auth:

        m_auth.return_value = get_test_payload()

        with mock.patch(
            "corona_backend.graph.store_consent_revoked", new=AsyncMockPass()
        ) as m:

            await http_client.fetch(f"{base_url}/revoke-consent", **post_request_args())

            m.assert_called_once()
            assert user_resp["id"] == m.call_args[0][0]["id"]


async def test_revoke_consent_handler_delete_devices(http_client, base_url):

    await clean_test_user()

    user_resp = await test_utils.create_test_user(TEST_PHONE_NUMBER)
    device_id = "".join(str(uuid.uuid1()).split("-"))
    await graph.store_device_id(user_resp, device_id)

    class TestException(Exception):
        pass

    with mock.patch.object(
        corona_backend.onboarding.app.RevokeConsentHandler, "get_current_user"
    ) as m_auth:

        m_auth.return_value = get_test_payload()

        with mock.patch(
            "corona_backend.devices.delete_devices", new=AsyncMockReturnOne()
        ) as m:

            await http_client.fetch(f"{base_url}/revoke-consent", **post_request_args())

            m.assert_called_once()
            m.assert_called_with(device_id, raise_on_error=False)

    await clean_test_user()


async def test_request_contact_ids(
    http_client, base_url, device, timestamp, request_contact_ids_mock
):

    await clean_test_user()
    device_id = device["deviceId"]
    device_key_b64 = device["authentication"]["symmetricKey"]["primaryKey"]
    device_key = base64.b64decode(device_key_b64)

    user = await test_utils.create_test_user(TEST_PHONE_NUMBER)
    await graph.store_device_id(user, device_id)

    req = HTTPRequest(method="POST", url=base_url + "/contactids", body="",)
    mw.add_auth_header(req, key=device_key, device_id=device_id)
    resp = await http_client.fetch(req)
    assert resp.code == 200
    expected_ids = request_contact_ids_mock.return_value
    print(expected_ids)
    assert json.loads(resp.body.decode("utf8")) == {
        "contact_ids": expected_ids,
    }
    await clean_test_user()


async def test_birth_year_handler(
    http_client,
    base_url,
    db_user_registration,
    get_device_mock_auth,
    user_for_device_mock,
    device_ids_mock,
):
    """
    A user has two devices with the ids: [device_id1, device_id2].
    Initially there are no birth dates associated with any of the device ids.
    The user updates the birth date information twice for device_id1.
    The birth date information for device_id2 should be updated accordingly.
    """

    with testsql.set_db_user(testsql.DB_USER_SERVICE_API):
        birth_year = await sql.get_birth_year(device_id=TEST_DEVICE_ID)
        assert birth_year is None

        birth_year = await sql.get_birth_year(device_id="device_id2")
        assert birth_year is None

    req = HTTPRequest(
        method="POST", url=base_url + "/birthyear", body='{"birthyear": 1989}',
    )
    mw.add_auth_header(req, key=TEST_DEVICE_KEY, device_id=TEST_DEVICE_ID)

    for birth_year in [1989, 1990]:
        req.body = f'{{"birthyear": {birth_year}}}'
        mw.add_auth_header(req, key=TEST_DEVICE_KEY, device_id=TEST_DEVICE_ID)

        resp = await http_client.fetch(req)
        assert resp.code == 200

        with testsql.set_db_user(testsql.DB_USER_SERVICE_API):
            birth_year_stored = await sql.get_birth_year(device_id=TEST_DEVICE_ID)
            assert birth_year_stored == birth_year

            birth_year = await sql.get_birth_year(device_id="device_id2")
            assert birth_year_stored == birth_year
