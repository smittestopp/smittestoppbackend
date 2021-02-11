"""Dump development deployment device ids to .csv

Requires development-environment environment variables
to access AD and corona_backend

Usage (run in corona image):

    make build/corona
    cat test/device-id-csv.py | docker run --rm -i --env-file secrets/dev/env-file $(make tag/corona) python3 > deviceIds.csv
"""

import asyncio

from tornado.log import enable_pretty_logging

from corona_backend.graph import list_users, device_groups_for_user, extension_attr_name


async def collect_devices():
    """yield all phone number, device group pairs"""

    sem = asyncio.Semaphore(64)

    async def process_one(user):
        results = []
        async with sem:
            async for device in device_groups_for_user(user):
                results.append((user["displayName"], device))
        return sorted(
            results, key=lambda user_device: user_device[1]["createdDateTime"]
        )

    pending = set()
    done = set()
    async for user in list_users():
        if user.get(extension_attr_name("testCredentials")):
            continue
        pending.add(asyncio.ensure_future(process_one(user)))
        done, pending = await asyncio.wait(pending, timeout=1e-3)
        for f in done:
            for phone, device in f.result():
                yield phone, device["displayName"], device["createdDateTime"]
    if pending:
        for results in await asyncio.gather(*pending):
            for phone, device in results:
                yield phone, device["displayName"], device["createdDateTime"]


async def device_id_csv():
    """Print the phone,deviceId mapping as csv
    each phone can have multiple device ids
    """
    print("phoneNumber,deviceId,created")
    async for phone, device_id, created in collect_devices():
        print(f"{phone},{device_id},{created}")


async def main():
    enable_pretty_logging()
    await device_id_csv()


if __name__ == "__main__":
    asyncio.run(main())
