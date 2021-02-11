import base64
import hmac
import json
import os
import time
from datetime import datetime
from unittest.mock import patch

import pytest
import tornado
from testfixtures import LogCapture

import corona_backend.onboarding.app
from corona_backend import middleware as mw
from corona_backend import pin, testsql

from . import conftest
from .conftest import TEST_DEVICE_ID, TEST_DEVICE_KEY, make_async


@pytest.fixture(scope="module", autouse=True)
async def testsetup(setup_testdb, now_at_utc_mock):
    """Setup for pin tests.

    Creates testdb, inserts test-data, and tears down testdb when tests complete."""

    with testsql.set_db_user(testsql.DB_USER_SERVICE_API):
        await pin.store_pin_code(
            phone_number="+0013371337", pin_code="test_pin_1", timestamp=now_at_utc_mock
        )


@pytest.fixture
def app():
    handlers = [
        ("/pin", corona_backend.onboarding.app.PinHandler),
    ]
    return tornado.web.Application(handlers,)


async def test_fetch_or_generate_pin_within_threshold():
    with patch(
        "corona_backend.pin.get_latest_pin_code_after_threshold",
        new=make_async(lambda phone_number, threshold: "pin_code_1"),
    ):
        pin_code = await pin.fetch_or_generate_pin(phone_number="+0012341234")
        assert pin_code == "pin_code_1"


async def test_fetch_or_generate_pin_outside_threshold(
    generate_pin_mock, store_pin_code_mock
):
    with patch(
        "corona_backend.pin.get_latest_pin_code_after_threshold",
        new=make_async(lambda phone_number, threshold: None),
    ):
        pin_code = await pin.fetch_or_generate_pin(phone_number="+0012341234")
        assert pin_code == "pin_code_1"
        store_pin_code_mock.assert_called_with(
            phone_number="+0012341234",
            pin_code="pin_code_1",
            timestamp=datetime(2018, 3, 12, 10, 12, 45),
        )


def pin_request(digest, device_id, timestamp_str):
    return dict(
        method="GET",
        headers={
            "Authorization": f"SMST-HMAC-SHA256 {device_id};{timestamp_str};{digest}",
        },
    )


def happy_pin_request():
    timestamp_str = str(int(time.time()))
    b64_digest = mw.create_signature_base64(
        TEST_DEVICE_KEY,
        device_id=TEST_DEVICE_ID,
        timestamp=timestamp_str,
        scope="GET|/pin",
    )
    return pin_request(b64_digest, TEST_DEVICE_ID, timestamp_str)


async def assert_invalid_pin_req(
    http_client, base_url, req, expected_resp,
):
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/pin", **req)
    assert e.value.code == expected_resp["status"]
    assert json.loads(e.value.response.body) == expected_resp


async def test_pin_handler_happy(
    http_client,
    base_url,
    db_user_serviceapi,
    get_device_mock_auth,
    phone_number_for_device_id_mock,
):
    req = happy_pin_request()

    expected_resp_body = {
        "pin_codes": [{"pin_code": "test_pin_1", "created_at": "2018-03-12T10:12:45Z"}]
    }

    resp = await http_client.fetch(f"{base_url}/pin", **req)

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body


async def test_pin_handler_happy_signed_with_secondary_key(
    http_client,
    base_url,
    db_user_serviceapi,
    get_device_mock_auth,
    timestamp,
    phone_number_for_device_id_mock,
):
    b64_digest = mw.create_signature_base64(
        key=conftest.TEST_2ND_DEVICE_KEY,
        device_id=conftest.TEST_DEVICE_ID,
        timestamp=timestamp,
        scope="GET|/pin",
    )
    req = pin_request(b64_digest, TEST_DEVICE_ID, timestamp)

    expected_resp_body = {
        "pin_codes": [{"pin_code": "test_pin_1", "created_at": "2018-03-12T10:12:45Z"}]
    }

    resp = await http_client.fetch(f"{base_url}/pin", **req)
    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body


async def test_pin_handler_auth_unknown_device(
    http_client, base_url, get_device_mock_auth, timestamp,
):
    capture = LogCapture()

    invalid_test_device_id = "device_id_1_invalid"

    b64_digest = mw.create_signature_base64(
        TEST_DEVICE_KEY,
        device_id=TEST_DEVICE_ID,
        timestamp=timestamp,
        scope="GET|/pin",
    )
    req = pin_request(b64_digest, invalid_test_device_id, timestamp)

    expected_resp = {"status": 403, "message": "Forbidden"}

    await assert_invalid_pin_req(http_client, base_url, req, expected_resp)

    capture.check_present(
        (
            "tornado.application",
            "WARNING",
            f"Invalid device id: {invalid_test_device_id}",
        )
    )

    capture.uninstall()


async def test_pin_handler_auth_indigestible(
    http_client, base_url, get_device_mock_auth, timestamp
):
    capture = LogCapture()

    # This "digest" will raise error in base64.b64decode(b64_digest)
    indecodable_digest = "foo"

    req = pin_request(indecodable_digest, TEST_DEVICE_ID, timestamp)

    expected_resp = {"status": 403, "message": "Forbidden"}

    await assert_invalid_pin_req(http_client, base_url, req, expected_resp)

    capture.check_present(
        (
            "tornado.application",
            "WARNING",
            f"Invalid base64 digest: {indecodable_digest}",
        )
    )

    capture.uninstall()


async def test_pin_handler_auth_bad_key(
    http_client, base_url, get_device_mock_auth, timestamp
):
    capture = LogCapture()

    invalid_test_device_key = os.urandom(16)
    b64_digest = mw.create_signature_base64(
        invalid_test_device_key,
        device_id=TEST_DEVICE_ID,
        timestamp=timestamp,
        scope="GET|/pin",
    )
    req = pin_request(b64_digest, TEST_DEVICE_ID, timestamp)

    expected_resp = {"status": 403, "message": "Forbidden"}

    await assert_invalid_pin_req(http_client, base_url, req, expected_resp)

    capture.check_present(
        ("tornado.application", "WARNING", "Signature does not match")
    )

    capture.uninstall()


async def test_pin_handler_auth_bad_message(
    http_client, base_url, get_device_mock_auth, timestamp
):
    capture = LogCapture()

    b64_digest = mw.create_signature_base64(
        TEST_DEVICE_KEY,
        device_id=TEST_DEVICE_ID,
        timestamp=timestamp + "_somethingelse",
        scope="GET|/pin",
    )
    req = pin_request(b64_digest, TEST_DEVICE_ID, timestamp)

    expected_resp = {"status": 403, "message": "Forbidden"}

    await assert_invalid_pin_req(http_client, base_url, req, expected_resp)

    capture.check_present(
        ("tornado.application", "WARNING", "Signature does not match")
    )

    capture.uninstall()


async def test_pin_handler_auth_bad_timing(
    http_client, base_url,
):
    timestamp_str_too_old = str(int(time.time()) - 7200)
    timestamp_str_too_young = str(int(time.time()) + 7200)

    for timestamp_str in [timestamp_str_too_old, timestamp_str_too_young]:
        b64_digest = mw.create_signature_base64(
            TEST_DEVICE_KEY,
            device_id=TEST_DEVICE_ID,
            timestamp=timestamp_str,
            scope="GET|/pin",
        )
        req = pin_request(b64_digest, TEST_DEVICE_ID, timestamp_str)

        expected_resp = {
            "status": 400,
            "message": f"Timestamp {timestamp_str} out of bounds",
        }

        await assert_invalid_pin_req(http_client, base_url, req, expected_resp)


async def test_pin_handler_auth_invalid_time_format(
    http_client, base_url, get_device_mock_auth,
):
    timestamp_str = "2018-03-12T10:12:45Z"
    expected_resp = {
        "status": 400,
        "message": f"Invalid timestamp: {timestamp_str}, expected unix timestamp",
    }

    b64_digest = mw.create_signature_base64(
        conftest.TEST_DEVICE_KEY,
        device_id=TEST_DEVICE_ID,
        timestamp=timestamp_str,
        scope="GET|/pin",
    )
    req = pin_request(b64_digest, TEST_DEVICE_ID, timestamp_str)

    await assert_invalid_pin_req(http_client, base_url, req, expected_resp)


async def test_pin_handler_digest_with_other_algorithms(
    http_client, base_url, get_device_mock_auth, timestamp
):
    # Other common digest algorithms
    algorithms_digest = ["sha1", "sha224", "sha384", "md5"]

    scope = "GET|/pin"
    msg = f"{TEST_DEVICE_ID}|{timestamp}|{scope}".encode("utf8")

    expected_resp = {"status": 403, "message": "Forbidden"}

    capture = LogCapture()

    for algorithm_digest in algorithms_digest:
        digest = hmac.digest(conftest.TEST_DEVICE_KEY, msg, algorithm_digest)
        b64_digest = base64.b64encode(digest).decode("ascii")
        req = pin_request(b64_digest, TEST_DEVICE_ID, timestamp)

        await assert_invalid_pin_req(http_client, base_url, req, expected_resp)

        capture.check_present(
            ("tornado.application", "WARNING", "Signature does not match")
        )

    capture.uninstall()


async def test_pin_handler_pin_code_does_not_exist(
    http_client,
    base_url,
    get_device_mock_auth,
    phone_number_for_device_id_mock_no_pin_associated,
    db_user_serviceapi,
):

    expected_resp = {"pin_codes": []}

    req = happy_pin_request()
    resp = await http_client.fetch(f"{base_url}/pin", **req)

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp


async def test_pin_handler_no_phone_number_matched(
    http_client, base_url, get_device_mock_auth, empty_phone_number_for_device_id_mock,
):

    expected_resp = {"status": 404, "message": "No phone number matched to the device"}

    req = happy_pin_request()

    await assert_invalid_pin_req(http_client, base_url, req, expected_resp)
