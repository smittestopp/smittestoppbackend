"""Delete all devices and users from the system

Requires development-environment environment variables
to access AD and corona_backend

Usage (run in corona image):

    make build/corona
    cat test/delete_all_users.py | docker run --rm -i --env-file secrets/dev/env-file $(make tag/corona) python3
"""

import asyncio
import os
import time
from collections import defaultdict

# fetch needs enough time to wait-out rate limit resets (150s)
os.environ["FETCH_TIMEOUT"] = "600"

from tornado.httpclient import HTTPClientError
from tornado.log import app_log, enable_pretty_logging

from corona_backend import graph
from corona_backend.devices import delete_device, get_devices

CONCURRENCY = 32
MAX_FAILURES = 32
IOT_ONLY = False
LOG_TIME_INTERVAL = 30
LOG_COUNT_INTERVAL = 1000
iot_deleted_date = graph.extension_attr_name("iotDeletedDate")

# consume_concurrently from delete image
async def consume_concurrently(
    iterable,
    process_one,
    label="iteration",
    concurrency=CONCURRENCY,
    max_failures=MAX_FAILURES,
    counts=None,
    readahead_limit=None,
):

    if counts is None:
        counts = defaultdict(int)

    tic = time.perf_counter()

    sem = asyncio.Semaphore(concurrency)
    if readahead_limit is None:
        readahead_limit = 128
    readahead_sem = asyncio.Semaphore(readahead_limit)

    async def process_with_semaphore(item):
        """wrap process_one in a semaphore

        to limit concurrency
        """
        async with readahead_sem:
            async with sem:
                return await process_one(item)

    def log_progress(*, extra="", force=False):
        """Log the current deletion counts"""
        toc = time.perf_counter()
        if (
            not force
            and counts["done"] < log_progress.last_log_count + LOG_COUNT_INTERVAL
            and toc < log_progress.last_log_time + LOG_TIME_INTERVAL
        ):
            # don't need to log yet
            return
        counts_str = ", ".join(
            f"{key}={value}" for key, value in sorted(counts.items())
        )
        delta_n = counts["done"] - log_progress.last_log_count
        delta_t = toc - log_progress.last_log_time
        rate = delta_n / delta_t
        app_log.info(
            f"{label} counts{' ' + extra if extra else ''} (elapsed={toc-tic:.0f}s {rate:.1f} it/s): {counts_str}"
        )
        log_progress.last_log_count = counts["done"]
        log_progress.last_log_time = toc

    log_progress.last_log_time = tic
    log_progress.last_log_count = 0

    async def check_progress(pending, timeout=None):
        """Wait for pending tasks, check for failures, and log progress"""
        done, pending = await asyncio.wait(pending, timeout=timeout)
        counts["done"] += len(done)
        counts["todo"] -= len(done)
        for f in done:
            if f.exception():
                counts["failed"] += 1
                try:
                    await f
                except Exception:
                    app_log.exception("Failure processing deletion")
                    if counts["failed"] >= max_failures:
                        log_progress(extra="aborting", force=True)
                        raise

        log_progress()
        return done, pending

    if not hasattr(iterable, "__aiter__"):
        # wrap sync iterable in async generator
        sync_iterable = iterable

        async def aiter():
            for item in sync_iterable:
                yield item

        iterable = aiter()

    pending = set()
    async for item in iterable:
        counts["total"] += 1
        counts["todo"] += 1
        async with readahead_sem:
            pending.add(asyncio.ensure_future(process_with_semaphore(item)))
        if len(pending) >= 10:
            done, pending = await check_progress(pending, timeout=1e-4)
            for f in done:
                if not f.exception():
                    yield f.result()

    # wait for the rest to finish
    while pending:
        done, pending = await check_progress(pending, timeout=1)
        for f in done:
            if not f.exception():
                yield f.result()

    log_progress(extra="completed", force=True)


async def delete_all_devices():
    """yield all phone number, device group pairs"""

    counts = defaultdict(int)

    async def process_one_user(user):
        """Delete one user from AD"""
        if IOT_ONLY:
            return
        if user.get(graph.extension_attr_name("testCredentials")):
            return
        if not user["displayName"].startswith("+"):
            return
        counts["aduser"] += 1
        await graph.delete_user(user)

    async def process_one_deleted_user(user):
        """Delete one user from AD"""
        if IOT_ONLY:
            return
        if user.get(graph.extension_attr_name("testCredentials")):
            return
        if not user["displayName"].startswith("+"):
            return
        counts["aduser"] += 1
        await graph.delete_deleted_user(user)

    async def process_one_group(group):
        """Delete one device from AD and IoTHub"""
        device_id = group["displayName"]
        # delete iot before AD
        if not group.get(iot_deleted_date):
            await process_one_device(device_id)
            counts["iot"] += 1
            if IOT_ONLY:
                # only bother recording iot metadata if we aren't
                # about to delete the group from AD
                await graph.mark_iot_deleted(group)
        if not IOT_ONLY:
            counts["adgroup"] += 1
            await graph.delete_group(group)

    async def process_one_device(device_id):
        """Delete one device from IoTHub"""
        if isinstance(device_id, dict):
            # device dict
            device_id = device_id["deviceId"]
        try:
            await delete_device(device_id)
        except HTTPClientError as e:
            if e.code == 404:
                app_log.warning(f"Device already deleted: {device_id}")
            else:
                raise
        counts["iot"] += 1

    where = "IoTHub" if IOT_ONLY else "AD and IoTHub"
    app_log.info(f"Cleaning up devices in {where}")
    async for group in consume_concurrently(
        graph.list_groups(), process_one_group, label="device deletion", counts=counts,
    ):
        pass

    if not IOT_ONLY:
        app_log.info("Cleaning up AD users")
        async for user in consume_concurrently(
            graph.list_users(), process_one_user, label="user deletion", counts=counts,
        ):
            pass
        app_log.info("Permanently cleaning up AD users")
        async for user in consume_concurrently(
            graph.list_deleted_users(), process_one_deleted_user, label="permanent user deletion", counts=counts,
        ):
            pass


    app_log.info("Cleaning up orphaned IoT devices")
    # cleanup orphaned devices in iothub
    async for device in consume_concurrently(
        get_devices(),
        process_one_device,
        label="orphan device deletion",
        counts=counts,
    ):
        pass


async def main():
    enable_pretty_logging()
    await delete_all_devices()


if __name__ == "__main__":
    # import argparse
    # parser = argparse.ArgumentParser()
    # parser.add_argument("action", choices=("iothub-only", "everything"), default="iothub-only")
    # opts = parser.parse_args()
    # IOT_ONLY = opts.action == "iothub-only"

    if IOT_ONLY:
        what = "all iothub devices"
    else:
        what = "all users and data from IoTHub and AD"
    print(f"Deleting {what} in 10s...")
    time.sleep(10)
    asyncio.run(main())
