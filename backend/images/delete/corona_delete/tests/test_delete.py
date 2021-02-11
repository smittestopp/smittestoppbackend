import asyncio
import random
import json
import time
import uuid
from collections import namedtuple
from unittest import mock
from datetime import datetime, timedelta, timezone
import os
from unittest.mock import MagicMock

import objgraph
import pytest
from testfixtures import LogCapture

from corona_backend import graph
from corona_backend import test as test_utils


def with_db(*, persistent=False, pooled=True, **params):
    """Dummy decorator for mocking decorator in
    delete module
    """

    def decorator(f):
        def wrap(*args, **kwargs):
            return f(*args, **kwargs)

        return wrap

    return decorator


# Mock out the with_db decorator
# TODO: Do this in a more clean way. Now we need to
# mock `corona_backend.sql.with_db` before we import
# corona_delete.delete
mock.patch("corona_backend.sql.with_db", with_db).start()

from corona_delete import delete  # isort:skip

DeviceUser = namedtuple("DeviceUser", ["group", "user"])

TEST_PHONE_NUMBER = "+00000000"

PERSISTENT_CHECK_DB = os.environ.get("PERSISTENT_CHECK_DB", "") == "1"


async def clean_test_user(phone_number=TEST_PHONE_NUMBER):
    try:
        user = await graph.find_user_by_phone(phone_number)
    except Exception:
        pass
    else:
        if user is not None:
            await graph.delete_user(user)


@pytest.fixture()
def user(event_loop):
    event_loop.run_until_complete(clean_test_user())
    # Create user
    phone_number = TEST_PHONE_NUMBER
    user_resp = event_loop.run_until_complete(test_utils.create_test_user(phone_number))
    user_resp["phone_number"] = phone_number

    yield user_resp

    # Tear down user
    event_loop.run_until_complete(test_utils.delete_test_user(user_resp["id"]))


async def find_groups_to_delete():
    groups = []
    async for group in delete.find_groups_to_delete():
        groups.append(group)
    return groups


async def test_find_groups_to_delete(user):
    device_id = "".join(str(uuid.uuid1()).split("-"))
    device = await graph.store_device_id(user, device_id)

    # Get groups that are marked for deletion
    groups = await find_groups_to_delete()
    old_device_ids = {group["displayName"] for group in groups}

    assert device_id not in old_device_ids

    await graph.mark_for_deletion(device)

    groups = await find_groups_to_delete()
    new_device_ids = {group["displayName"] for group in groups}

    assert device_id in new_device_ids
    await graph.delete_device_group(device_id)


async def test_find_groups_to_delete_without_timestamp(user):
    # Create fake id
    device_id = "".join(str(uuid.uuid1()).split("-"))

    device = await graph.store_device_id(user, device_id)

    group_id = device["id"]

    groups = await find_groups_to_delete()
    old_device_ids = {group["displayName"] for group in groups}

    assert device_id not in old_device_ids

    # Mark group for deletion without a timestamp
    await graph.graph_request(
        f"/groups/{group_id}",
        method="PATCH",
        body=json.dumps(
            {
                graph.extension_attr_name("toDelete"): True,
                graph.extension_attr_name("toDeleteDate"): None,
            }
        ),
        headers={"Content-Type": "application/json"},
    )

    capture = LogCapture("tornado.application")

    # Since there is not timestamp it should not have been deleted
    groups = await find_groups_to_delete()
    device_ids = {group["displayName"] for group in groups}
    assert device_id not in device_ids

    capture.check_present(
        (
            "tornado.application",
            "WARNING",
            f"Group {device_id} marked toDelete, but no date! Saving for later.",
        ),
        (
            "tornado.application",
            "INFO",
            f"Marking device id group {device_id} for deletion",
        ),
    )

    # Calling it again should now delete it
    groups = await find_groups_to_delete()
    device_ids = {group["displayName"] for group in groups}
    assert device_id in device_ids

    await graph.delete_device_group(device_id)

    capture.uninstall()


# @pytest.mark.gen_test
# def test_delete_sql_data():
#
#     db = mock.MagicMock()
#     device_id = "".join(str(uuid.uuid1()).split("-"))
#
#     capture = LogCapture("tornado.application")
#
#     delete.delete_sql_data(db, device_id)
#
#     capture.check_present(
#         ("tornado.application", "WARNING", f"Deleting SQL data for {device_id}"),
#     )
#
#     db.execute.assert_called_once_with(r"{CALL deleteforUUID (?)}", (device_id,))
#
#     capture.uninstall()

@with_db(pooled=False)
def test_delete_sql_data():
    db = mock.MagicMock()
    device_ids = ["test_device1", "test_device2", "test_device3"]

    delete.delete_sql_data(db, *device_ids)

    # assert db.execute.call_count == 9 # remove this assert in case the code regarding sql in delete_sql_data further changed

    for device_id in device_ids:
        db.execute.assert_called_with(r"{CALL latestActivityForUUID(?)}", (device_id,))
        db.execute.assert_called_once_with(r"{CALL deleteforUUID (?)}", (device_id,))


@with_db(ApplicationIntent="ReadOnly")
def test_find_inactive_devices():
    db = mock.MagicMock()
    idle_cutoff = datetime.now(timezone.utc) - timedelta(days=10)

    delete.find_inactive_devices(db, idle_cutoff)

    db.execute.assert_called_once_with(r"{CALL getLastActivityBefore(?)}", (idle_cutoff,))


@with_db(persistent=PERSISTENT_CHECK_DB, ApplicationIntent="ReadOnly")
def test_check_sql_data():
    # smoke test for now. Thorough test can be implemented after getting details into db
    device_id = "test_device1"
    db = mock.MagicMock()

    delete.check_sql_data(db, device_id)

    db.execute.assert_called_once_with(r"{CALL latestActivityForUUID(?)}", (device_id,))


class AsyncMock(mock.MagicMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def coro(self):
        return

    @property
    def return_value(self):
        return self.coro()


@pytest.fixture
def mock_delete():
    with mock.patch(
            "corona_delete.delete.delete_sql_data", new_callable=AsyncMock
    ) as m:
        yield m


@pytest.fixture
def deleter(mock_delete):
    deleter = delete.get_deleter()
    try:
        yield deleter
    finally:
        delete.get_deleter.cache_clear()
        deleter.stop(block=True)


async def test_batch_delete(request, mock_delete):
    start = time.perf_counter()
    deleter = delete.Deleter(batch_size=3, batch_seconds=1)
    request.addfinalizer(lambda: deleter.stop(block=True))
    device_id = "one"
    f = deleter.request_deletion(device_id)
    # wait for batch to process
    time.sleep(0.2)
    assert len(deleter.batch) == 1
    assert deleter.batch[0][0] == device_id
    await f
    assert f.done()
    assert deleter.batch == []
    assert mock_delete.call_count == 1
    assert mock_delete.call_args == [(device_id,)]
    device_ids = [f"dev{i}" for i in range(deleter.batch_size + 1)]
    futures = [deleter.request_deletion(device_id) for device_id in device_ids]
    tic = time.perf_counter()
    await futures[deleter.batch_size - 1]
    toc = time.perf_counter()

    assert toc - tic < deleter.batch_seconds
    assert mock_delete.call_count == 2
    assert mock_delete.call_args == [tuple(device_ids[: deleter.batch_size])]

    time.sleep(0.2)
    assert len(deleter.batch) == 1
    assert deleter.batch[0][0] == device_ids[-1]
    await futures[-1]
    assert deleter.batch == []
    assert mock_delete.call_count == 3
    assert mock_delete.call_args == [tuple(device_ids[deleter.batch_size:])]

    device_id = "stop"
    f = deleter.request_deletion(device_id)
    deleter.stop(block=True)
    assert not deleter.thread.is_alive()
    assert mock_delete.call_count == 4
    assert mock_delete.call_args == [(device_id,)]


async def store_device_ids_for_users(users, device_ids, concurrency=10):
    sem = asyncio.Semaphore(concurrency)
    groups = []

    async def process_one(user, device_id):
        async with sem:
            group = await graph.store_device_id(user, device_id)
            groups.append(group)

    pending = set()
    for i in range(len(users)):
        pending.add(asyncio.ensure_future(process_one(users[i], device_ids[i])))

    await asyncio.gather(*pending)

    return groups


async def mark_groups_for_delete(groups, concurrency=10):
    sem = asyncio.Semaphore(concurrency)

    async def process_one(group):
        async with sem:
            await graph.mark_for_deletion(group, iot_deleted=True)

    pending = set()
    for group in groups:
        pending.add(asyncio.ensure_future(process_one(group)))

    await asyncio.gather(*pending)


async def test_delete_everything(user):
    # create faked 10000 test users and device_ids
    device_ids = []
    phone_numbers = []

    for i in range(10000):
        device_id = "".join(str(uuid.uuid1()).split("-"))
        device_ids.append(device_id)
        phone_number = random.randint(9999999, 100000000).__str__()
        phone_numbers.append(phone_number)

    users = await test_utils.create_test_users_from_numbers(phone_numbers)

    # group device_ids with user and mark for deletion
    groups = await store_device_ids_for_users(users, device_ids)
    await mark_groups_for_delete(groups)

    # Show the increase in peak object counts
    objgraph.show_growth()

    deleter = delete.get_deleter()
    with mock.patch("corona_delete.delete.check_and_delete_sql",
                    MagicMock(return_value=True)):  # db operation is mocked
        await delete.delete_everything(concurrency=10, max_failures=1)
    await deleter.stop(block=False)

    # Show the increase in peak object counts after the delete_everything call
    objgraph.show_growth()

    # check if device_id marked for deletion have been deleted
    updated_groups = await find_groups_to_delete()
    updated_device_ids = {group["displayName"] for group in updated_groups}
    for device_id in device_ids:
        assert device_id not in updated_device_ids

    # delete test users
    user_ids = []
    for user in users:
        user_ids.append(user['id'])
    await test_utils.delete_test_users_with_ids(user_ids)
