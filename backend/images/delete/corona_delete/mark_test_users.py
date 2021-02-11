"""Mark all devices registered on test users as to-be-deleted"""
import asyncio
from collections import defaultdict

import tornado.options

from corona_backend import graph, devices
from corona_backend.test import get_test_users
from .delete import CONCURRENCY, consume_concurrently


async def main():
    sem = asyncio.Semaphore(CONCURRENCY)

    counts = defaultdict(int)

    async def process_one(user):
        device_ids = []
        async for device_id in graph.device_ids_for_user(user):
            device_ids.append(device_id)
            counts['devices'] += 1
        if device_ids:
            deleted = await devices.delete_devices(*device_ids, raise_on_error=False)
            for r in deleted:
                if isinstance(r, Exception):
                    counts['error'] += 1

        await graph.dissociate_user_devices(user)

    async for user in consume_concurrently(get_test_users(), process_one=process_one):
        pass

if __name__ == "__main__":

    tornado.options.parse_command_line()
    asyncio.run(main())
