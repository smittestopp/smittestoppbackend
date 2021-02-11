import asyncio
import datetime
import os
import uuid
from collections import namedtuple
from unittest import mock
from unittest.mock import MagicMock

import pytest
from dateutil.parser import parse as parse_date
from testfixtures import LogCapture

from corona_backend import graph
from corona_backend import test as test_utils
from corona_backend import utils

DeviceUser = namedtuple("DeviceUser", ["group", "user"])


PHONE_NUMBER_BLACKLIST_FILE_TEST = os.path.join(
    os.path.dirname(__file__), "PHONE_NUMBER_BLACKLIST_FILE_TEST"
)


@pytest.fixture
def user(event_loop):
    # Setup user
    phone_number = "+00000000"
    user_resp = event_loop.run_until_complete(graph.find_user_by_phone(phone_number))
    if user_resp is None:
        user_resp = event_loop.run_until_complete(
            test_utils.create_test_user(phone_number)
        )
    user_resp["phone_number"] = phone_number

    yield user_resp

    # Tear down user
    event_loop.run_until_complete(test_utils.delete_test_user(user_resp["id"]))


@pytest.fixture
def user_with_device_id(user, event_loop):
    device_id = "".join(str(uuid.uuid1()).split("-"))
    group_resp = event_loop.run_until_complete(graph.store_device_id(user, device_id))

    yield DeviceUser(group=group_resp, user=user)

    event_loop.run_until_complete(graph.delete_device_group(device_id))


@pytest.fixture
def three_users(request, event_loop):
    phone_numbers = ["+001337123", "+001337124", "+001337125"]

    def teardown():
        # Some users may have been deleted during the tests.
        # We only attempt to delete the remaining to avoid 404 from graph API.
        remaining_users = event_loop.run_until_complete(
            graph.find_users_by_phone(phone_numbers)
        )
        event_loop.run_until_complete(
            test_utils.delete_test_users_with_ids(
                [user["id"] for user in remaining_users]
            )
        )

    # In case teardown failed in previous test run.
    teardown()

    remaining_users = event_loop.run_until_complete(
        graph.find_users_by_phone(phone_numbers)
    )
    event_loop.run_until_complete(
        test_utils.delete_test_users_with_ids([user["id"] for user in remaining_users])
    )
    users = event_loop.run_until_complete(
        test_utils.create_test_users_from_numbers(phone_numbers)
    )

    yield users

    request.addfinalizer(teardown)


async def test_ensure_custom_attrs_exist():
    # smoke test for now

    await graph.ensure_custom_attrs_exist()


async def test_reset_consent_and_store_consent_revoked(user):
    extra_attrs = [
        graph.extension_attr_name(attr)
        for attr in ("deviceId", "consentRevoked", "consentRevokedDate")
    ]

    def get_user():

        select = "id, displayName," + ",".join(extra_attrs)

        return graph.graph_request(f"/users/{user['id']}", params={"$select": select})

    await graph.reset_consent(user)
    u = await get_user()

    for attr in extra_attrs:
        assert attr not in u, attr

    await graph.store_consent_revoked(user)

    u = await get_user()

    assert extra_attrs[0] not in u
    assert extra_attrs[1] in u
    assert extra_attrs[2] in u
    assert u[extra_attrs[1]] is True
    timestamp = parse_date(u[extra_attrs[2]])
    # This is something to be aware of!
    now = datetime.datetime.now(datetime.timezone.utc)
    # Just put some tolerance here, say 10 seconds
    assert (now - timestamp).total_seconds() < 10

    await graph.reset_consent(user)
    u = await get_user()
    # FIXME: Not sure if this is expected behaviour?
    for attr in extra_attrs:
        assert attr not in u, attr


async def test_find_user_by_phone(user):
    """Test that the phone number from the user
    created in the setup method has the correct id
    """

    res = await graph.find_user_by_phone(user["phone_number"], select="id")
    assert res["id"] == user["id"]
    assert res["displayName"] == user["phone_number"]
    assert res["logName"] == utils.mask_phone(user["phone_number"])


@pytest.mark.parametrize(
    "key", ["@odata.context", "id", "displayName", "userPrincipalName",],
)
def test_user_response_keys(user, key):
    assert key in user


def test_displayName_is_phone_number(user):
    assert user["displayName"] == user["phone_number"]


async def get_device_ids_for_user(user):
    device_ids = []
    async for device_id in graph.device_ids_for_user(user):
        device_ids.append(device_id)
    return device_ids


async def test_store_and_delete_single_device_id(user):
    groups = await graph.graph_request(f"/users/{user['id']}/memberOf")
    # No groups should have been created for user
    assert len(groups) == 0

    device_id = "".join(str(uuid.uuid1()).split("-"))

    resp_store_device_id = await graph.store_device_id(user, device_id)
    assert resp_store_device_id["displayName"] == device_id

    resp_device_ids_for_user = await get_device_ids_for_user(user)
    assert len(resp_device_ids_for_user) == 1
    assert resp_device_ids_for_user[0] == device_id

    await graph.delete_device_group(device_id)

    # Check that there is no device associated with user anymore
    resp_device_ids_for_user_deleted = await get_device_ids_for_user(user)

    assert len(resp_device_ids_for_user_deleted) == 0


async def test_store_device_id_returns_None_if_already_exist(user_with_device_id):
    user = user_with_device_id.user
    group = user_with_device_id.group
    device_id = group["displayName"]

    resp_store_device_id = await graph.store_device_id(user, device_id)
    assert resp_store_device_id is None


async def test_add_new_device_to_user_with_existing_device(user_with_device_id):
    device_id = "".join(str(uuid.uuid1()).split("-"))
    user = user_with_device_id.user
    existing_device_id = user_with_device_id.group["displayName"]

    resp_store_device_id = await graph.store_device_id(user, device_id)

    assert resp_store_device_id["displayName"] == device_id

    resp_device_ids_for_user = await get_device_ids_for_user(user)
    groups = await graph.graph_request(f"/users/{user['id']}/memberOf")

    assert len(groups) == 2
    assert (
        set(resp_device_ids_for_user)
        == {device_id, existing_device_id}
        == set([group["displayName"] for group in groups])
    )

    # Try adding yet another device
    device_id2 = "".join(str(uuid.uuid1()).split("-"))
    resp_store_device_id2 = await graph.store_device_id(user, device_id2)

    assert resp_store_device_id2["displayName"] == device_id2

    resp_device_ids_for_user = await get_device_ids_for_user(user)

    groups = await graph.graph_request(f"/users/{user['id']}/memberOf")

    assert len(groups) == 3
    assert (
        set(resp_device_ids_for_user)
        == {device_id, existing_device_id, device_id2}
        == set([group["displayName"] for group in groups])
    )
    await graph.delete_device_group(device_id)
    await graph.delete_device_group(device_id2)

    resp_device_ids_for_user = await get_device_ids_for_user(user)
    groups = await graph.graph_request(f"/users/{user['id']}/memberOf")

    assert len(resp_device_ids_for_user) == len(groups) == 1


async def test_dissociate_user_devices(user_with_device_id):
    user = user_with_device_id.user
    resp_device_ids_for_user = await get_device_ids_for_user(user)

    assert len(resp_device_ids_for_user) == 1
    device_id = resp_device_ids_for_user[0]

    # Remove all devices
    await graph.dissociate_user_devices(user, iot_deleted=True)
    device_group = await graph.get_group(device_id)

    resp_device_ids_for_user = await get_device_ids_for_user(user)

    assert len(resp_device_ids_for_user) == 0

    # Add two new devices
    device_id1 = "".join(str(uuid.uuid1()).split("-"))
    device_id2 = "".join(str(uuid.uuid1()).split("-"))

    await graph.store_device_id(user, device_id1)
    await graph.store_device_id(user, device_id2)
    resp_device_ids_for_user = await get_device_ids_for_user(user)
    assert len(resp_device_ids_for_user) == 2

    # Remove all devices
    await graph.dissociate_user_devices(user)
    resp_device_ids_for_user = await get_device_ids_for_user(user)

    assert len(resp_device_ids_for_user) == 0


async def test_extract_deleted_numbers(three_users):
    phone_numbers = [user["displayName"] for user in three_users]

    users_to_delete = three_users[:-1]

    await asyncio.gather(
        *(graph.process_user_deletion(user) for user in users_to_delete)
    )

    deleted_numbers = await graph.extract_deleted_numbers(phone_numbers)

    assert set(deleted_numbers) == set(user["displayName"] for user in users_to_delete)

    await test_utils.delete_test_user(three_users[-1]["id"])


def test_wrap_user_empty():
    user = {}
    wrapped_user = graph.wrap_user(user)
    assert wrapped_user["logName"] == utils.mask_phone("unknown")


def test_wrap_user_with_logName():
    phone_number = "+001234567"
    u = {"displayName": phone_number}
    wrapped_user = graph.wrap_user(u)
    assert wrapped_user["logName"] == utils.mask_phone(phone_number)


def test_set_group_attribute(user_with_device_id, event_loop):
    group = user_with_device_id.group
    run = event_loop.run_until_complete
    timestamp = datetime.datetime.utcnow().isoformat()
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    run(graph.set_group_attr(group, sqlDeletedDate=timestamp))
    after = run(graph.get_group(group["displayName"]))
    assert parse_date(
        after.get(graph.extension_attr_name("sqlDeletedDate"))
    ) == parse_date(timestamp)


def test_get_blacklist():

    blacklist_temp = {"+4712345678", "+4700000000"}
    assert blacklist_temp == graph.get_blacklist(PHONE_NUMBER_BLACKLIST_FILE_TEST)


async def test_mark_iot_deleted(user_with_device_id):
    current_time = datetime.datetime.now(datetime.timezone.utc)
    group = user_with_device_id.group
    await graph.mark_iot_deleted(group, current_time.isoformat())
    after = await graph.get_group(group["displayName"])
    assert (
        parse_date(after.get(graph.extension_attr_name("iotDeletedDate")))
        == current_time
    )


def test_update_jwt_keys_keep_jwt_keys_updated(event_loop):
    # smoke test
    public_keys_expected = event_loop.run_until_complete(
        graph.update_jwt_keys(public_keys=None)
    )
    pc = graph.keep_jwt_keys_updated(interval_seconds=60, run_first=True)
    assert pc
    pc.stop()
    assert public_keys_expected is not None


async def test_user_for_device_and_phone_number_for_device_id(user_with_device_id):
    # associate a device id with a user
    device_id_test = "".join(str(uuid.uuid1()).split("-"))
    user_test = user_with_device_id.user
    group_resp_test = await graph.store_device_id(user_test, device_id_test)

    assert isinstance(group_resp_test, dict)

    # test if a correct phone number related with the user can be returned
    user_returned = await graph.user_for_device(device_id_test)

    assert user_returned["displayName"] == user_test["displayName"]

    # delete the associated device
    await graph.dissociate_user_devices(user_test)
    resp_device_ids_for_user_test = await get_device_ids_for_user(user_test)

    assert len(resp_device_ids_for_user_test) == 0


async def test_list_users():
    list_users_length_before = 0

    test_creds = graph.extension_attr_name("testCredentials")
    test_user_filter = f"{test_creds} eq true"
    async for user in graph.list_users(filter=test_user_filter):
        list_users_length_before += 1

    # create two test phone numbers
    phone_numbers = ["+001234567", "+001010101"]
    users = []

    # check if phone_numbers are associated with existing test users. If yes, delete them and re-create two test users
    for phone_number in phone_numbers:
        existing_user = await graph.find_user_by_phone(phone_number)
        if not existing_user:
            users.append(await test_utils.create_test_user(phone_number))

    list_users_length_after = 0
    async for user in graph.list_users(filter=test_user_filter):
        list_users_length_after += 1
    assert list_users_length_after == list_users_length_before + len(users)

    # delete created test users
    for phone_number in phone_numbers:
        test_user_deleted = await graph.find_user_by_phone(phone_number)
        await test_utils.delete_test_user(test_user_deleted["id"])


async def test_list_groups():
    # create one test phone number
    phone_number = "+0012345678"

    # check if phone_number is associated with one existing test user. If yes, delete them and re-create a test user.
    existing_user = await graph.find_user_by_phone(phone_number)
    if existing_user:
        await test_utils.delete_test_user(existing_user["id"])
    user_test = await test_utils.create_test_user(phone_number)

    list_groups_length_before = 0
    async for group in graph.list_groups():
        list_groups_length_before += 1

    # associate two test devices with the user
    device_ids = []
    resp_store_device_ids = []
    for i in range(2):
        device_id = str(uuid.uuid1())
        device_ids.append(device_id)
        resp_store_device_ids.append(await graph.store_device_id(user_test, device_id))

    groups = await graph.graph_request(f"/users/{user_test['id']}/memberOf")

    assert len(groups) == 2

    list_groups_length_after = 0
    async for group in graph.list_groups():
        list_groups_length_after += 1

    assert list_groups_length_after == list_groups_length_before + len(groups)

    # delete test devices
    for i in range(2):
        await graph.delete_device_group(device_ids[i])

    groups = await graph.graph_request(f"/users/{user_test['id']}/memberOf")

    assert len(groups) == 0

    # delete test user
    await test_utils.delete_test_user(user_test["id"])


async def test_get_user_token():

    test_phone_number = "+00001234"

    # create test user
    existing_user = await graph.find_user_by_phone(test_phone_number)

    if existing_user is None:
        await test_utils.create_test_user(test_phone_number)

    # remove devices associated with the user
    capture = LogCapture()
    user = await graph.find_user_by_phone(test_phone_number)
    await graph.dissociate_user_devices(user)
    capture.check_present(
        (
            "tornado.application",
            "INFO",
            f"Dissociating devices from {utils.mask_phone(test_phone_number)}",
        )
    )

    handler = MagicMock()
    key = os.urandom(5)
    import jwt

    payload = {
        "aud": "abc-123",
        "scp": "Device.Write",
        "signInNames.phoneNumber": test_phone_number,
    }
    token = jwt.encode(payload, key=key, headers={"kid": "test"}).decode("utf8")
    handler.request.headers = {"Authorization": f"Bearer {token}"}
    with mock.patch.object(
        jwt, "decode", lambda *args, **kwargs: payload
    ), mock.patch.dict(graph._PUBLIC_KEYS, {"test": key}):
        authenticated = graph.get_user_token(handler)

    assert authenticated is not None

    assert authenticated["_access_token"] == token
    assert authenticated["_phonenumber"] == test_phone_number

    # clean up
    await test_utils.delete_test_user(user["id"])
    capture.uninstall()


async def main():
    phone_number = "+00000000"
    res = await graph.find_user_by_phone(phone_number, select="id")
    await test_utils.delete_test_user(res["id"])
    user_resp = await test_utils.create_test_user(phone_number)
    print(list(user_resp.keys()))
    import pprint

    pprint.pprint(user_resp)
    user_id = user_resp["id"]
    pprint.pprint(user_id)
    print("#" * 40)
    res = await graph.find_user_by_phone(phone_number, select="id")
    print(res["id"])
    await test_utils.delete_test_user(res["id"])


if __name__ == "__main__":
    # asyncio.run(main())
    pytest.main()
