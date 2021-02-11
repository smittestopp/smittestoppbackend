"""Testing"""
import asyncio
import base64
import json
import os
import socket

from tornado.log import app_log, enable_pretty_logging
from tornado.simple_httpclient import HTTPTimeoutError

from . import graph
from .utils import exponential_backoff


async def get_test_users(select=None):
    """yield all test users"""
    if select is None:
        attr_name = graph.extension_attr_name("deviceId")
        select = f"id,displayName,{attr_name},mailNickname"
    async for user in graph.paged_graph_request(
        "/users",
        params={
            "$select": select,
            "$filter": f"{graph.extension_attr_name('testCredentials')} eq true",
        },
    ):
        yield graph.wrap_user(user)


async def get_test_user_by_phone_number(phone_number, select=None):
    check_test_user_phone_number(phone_number)
    if select is None:
        select = f"id,displayName"

    users = await graph.graph_request(
        "/users",
        params={"$select": select, "$filter": (f"displayName eq '{phone_number}'")},
    )
    if len(users) != 0:
        raise RuntimeError(f"No user was found with phone nubmer {phone_number}")
    elif len(users) > 1:
        raise RuntimeError(f"More than one was found with phone nubmer {phone_number}")
    else:
        return users[0]


def check_test_user_phone_number(phone_number):
    if not phone_number.startswith("+00"):
        raise ValueError(
            f"test users must have invalid phone numbers like '+00...', got {phone_number}"
        )


async def delete_test_user(user_id):
    app_log.info(f"Delete test user {user_id}")
    await graph.graph_request(f"/users/{user_id}", method="DELETE")
    app_log.info(f"Deleted test user {user_id}")


async def create_test_user(phone_number):
    check_test_user_phone_number(phone_number)
    app_log.info(f"Creating test user {phone_number}")

    response = await graph.graph_request(
        "/users",
        method="POST",
        body=json.dumps(
            {
                "displayName": phone_number,
                "accountEnabled": False,
                "identities": [
                    {
                        "signInType": "phoneNumber",
                        "issuer": f"{graph.tenant_name}.onmicrosoft.com",
                        "issuerAssignedId": phone_number,
                    },
                ],
                # make it a test account
                graph.extension_attr_name("testCredentials"): True,
                "passwordProfile": {
                    "password": base64.encodebytes(os.urandom(16)).decode("ascii")
                },
                "passwordPolicies": "DisablePasswordExpiration",
            }
        ),
    )
    app_log.info(f"Created test user {phone_number}")
    return response


async def create_test_users_from_numbers(phone_numbers, concurrency=10):
    users = []
    sem = asyncio.Semaphore(concurrency)

    async def do_one(phone_number):
        async with sem:
            user = await create_test_user(phone_number)
            users.append(user)

    pending = set()
    for phone_number in phone_numbers:
        pending.add(asyncio.ensure_future(do_one(phone_number)))

    await asyncio.gather(*pending)

    return users


async def delete_test_users_with_ids(user_ids, concurrency=10):
    sem = asyncio.Semaphore(concurrency)

    async def do_one(user_id):
        async with sem:
            await delete_test_user(user_id)

    pending = set()
    for user_id in user_ids:
        pending.add(asyncio.ensure_future(do_one(user_id)))

    await asyncio.gather(*pending)


async def create_test_users(num_users, concurrency=10, total=False):
    existing_numbers = set()
    async for user in get_test_users(select="displayName"):
        existing_numbers.add(user["displayName"])

    num_created = 0
    n = 1
    sem = asyncio.Semaphore(concurrency)

    async def do_one(phone_number):
        async def try_again():
            try:
                await create_test_user(phone_number)
            except (TimeoutError, HTTPTimeoutError, socket.gaierror) as e:
                app_log.error(f"Error creating {phone_number}: {e}")
                return False
            else:
                return True

        async with sem:
            await exponential_backoff(
                try_again, fail_message=f"Failed to create test user {phone_number}"
            )

    pending = set()
    if total:
        num_users -= len(existing_numbers)
    while num_created < num_users:
        phone_number = f"+00{n:06}"
        n += 1
        if phone_number in existing_numbers:
            # test number already exists
            print(phone_number, "exists")
            continue
        num_created += 1

        pending.add(asyncio.ensure_future(do_one(phone_number)))
        done, pending = await asyncio.wait(pending, timeout=1e-3)
        if done:
            await asyncio.gather(*done)

    await asyncio.gather(*pending)


async def main():
    enable_pretty_logging()

    await create_test_users(10000, 64, total=True)


if __name__ == "__main__":
    asyncio.run(main())
