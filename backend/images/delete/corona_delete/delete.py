"""Watch the user list for consent revocation and delete user data"""

import asyncio
import concurrent.futures
import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from queue import Queue, Empty
from threading import Thread

import azure.core.exceptions
from dateutil.parser import parse as parse_date
from tornado.httpclient import HTTPClientError
from tornado.log import app_log
from tornado.options import parse_command_line, define, options

from corona_backend import devices, graph, sql
from corona_backend.utils import timer
from . import storage

# number of concurrent deletions outstanding
# except when processing a backlog, we are actually limited by DB_THREADS making sql delete requests
CONCURRENCY = int(os.environ.get("CONCURRENCY") or 10)
# number of failures to allow before aborting the task
MAX_FAILURES = int(os.environ.get("MAX_FAILURES") or 1)

# intervals (number and time) for logging progress
LOG_COUNT_INTERVAL = int(os.environ.get("LOG_COUNT_INTERVAL") or 100)
LOG_TIME_INTERVAL = int(os.environ.get("LOG_TIME_INTERVAL") or 30)

# expiry for undelete folder
UNDELETE_DAYS = int(os.environ.get("UNDELETE_DAYS") or 2)
# expiry for .rewrite folder
REWRITE_DAYS = int(os.environ.get("REWRITE_DAYS") or 2)
# expiry for data lake files
DATA_LAKE_DAYS = int(os.environ.get("DATA_LAKE_DAYS") or 30)

# idle cutoff for user inactivity
IDLE_CUTOFF_DAYS = int(os.environ.get("IDLE_CUTOFF_DAYS") or 30)
IDLE_CUTOFF = datetime.now(timezone.utc) - timedelta(days=IDLE_CUTOFF_DAYS)
# limit the number of deletions in a given run
IDLE_DELETE_LIMIT = int(os.environ.get("IDLE_DELETE_LIMIT") or 0)

# batch variables for deletions
DELETE_BATCH_SIZE = int(os.environ.get("DELETE_BATCH_SIZE") or 1)
DELETE_BATCH_SECONDS = int(os.environ.get("DELETE_BATCH_SECONDS") or 30)

# the date before which we assume sql data doesn't need to be deleted again
# because re-running SQL delete is so slow
# this should not normally be set, but it is now while we are re-importing data from the lake to the db
SQL_CUTOFF_DATE = os.environ.get("SQL_CUTOFF_DATE")
if SQL_CUTOFF_DATE:
    SQL_CUTOFF_DATE = parse_date(SQL_CUTOFF_DATE)

# backlog date is a date cutoff so we can limit processing to
# only old data when there's been a backlog buildup
BACKLOG_DATE = os.environ.get("BACKLOG_DATE")

PERSISTENT_CHECK_DB = os.environ.get("PERSISTENT_CHECK_DB", "") == "1"

to_delete = graph.extension_attr_name("toDelete")
to_delete_date = graph.extension_attr_name("toDeleteDate")
iot_deleted_date = graph.extension_attr_name("iotDeletedDate")
sql_deleted_date = graph.extension_attr_name("sqlDeletedDate")
lake_deleted_date = graph.extension_attr_name("lakeDeletedDate")
consent_revoked = graph.extension_attr_name("consentRevoked")


def isonow():
    """ISO8601 UTC timestamp for now"""
    return datetime.utcnow().isoformat() + "Z"


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
        # default readahead limit: 2x concurrency waiting in the pipeline
        readahead_limit = concurrency * 3
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
            done, pending = await check_progress(pending, timeout=1e-3)
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


async def find_users_to_delete(limit=None):
    """Find users whose devices should be deleted"""
    async for user in graph.list_users(filter=f"{consent_revoked} eq true"):
        if user.get(consent_revoked):
            app_log.warning(f"User {user['logName']} with consent revoked not removed!")
            yield user
        else:
            app_log.warning(
                f"User {user['logName']} without consent revoked shouldn't have been returned by query."
            )

    inactive = await find_inactive_devices()
    app_log.info(f"Found {len(inactive)} inactive devices")
    counts = defaultdict(int)

    async def process_one(uuid_activity):
        uuid, last_activity = uuid_activity
        group = await graph.get_group(uuid)
        if group is None:
            app_log.info(f"No group for inactive device {uuid}")
            counts["no_group"] += 1
            return
        if group.get(consent_revoked):
            app_log.info(f"Already marked for deletion: {uuid}")
            counts["deleted"] += 1
            return
        user = await graph.user_for_device(group)
        if user is None:
            app_log.info(f"No user for inactive device {uuid}")
            counts["no_user"] += 1
            # FIXME: something went wrong. Mark device id group for deletion?
            return

        # check other devices on the same user
        # in case of new device registrations,
        # don't delete data from a user's old phone
        other_device_activity = None
        device_ids = [uuid]
        async for group in graph.device_groups_for_user(user):
            device_id = group["displayName"]
            if device_id != uuid:
                device_ids.append(device_id)
            # First check for recent registration (cheap)
            if parse_date(group["createdDateTime"]) >= IDLE_CUTOFF:
                app_log.info(f"Recently registered device {device_id}")
                counts["new"] += 1
                if device_id == uuid:
                    app_log.warning(
                        f"WRONG activity: recently registered {device_id} not idle"
                    )
                    counts["wrong"] += 1
                other_device_activity = True
                break
            try:
                device = await devices.get_device(device_id)
            except Exception as e:
                app_log.warning(f"Failed to get device {device_id}: ({e})")
                counts["iot_err"] += 1
                pass
            else:
                if parse_date(device["lastActivityTime"]) >= IDLE_CUTOFF:
                    counts["iot"] += 1
                    app_log.info(f"Activity on {device_id} in IoTHub")
                    if device_id == uuid:
                        app_log.warning(
                            f"WRONG activity: iothub active {device_id} not idle"
                        )
                        counts["wrong"] += 1
                    other_device_activity = True
                    break
            if device_id != uuid:
                # if not registered since cutoff, check for activity in SQL
                if await check_sql_data(device_id, activity_cutoff=IDLE_CUTOFF):
                    counts["sql"] += 1
                    app_log.info(f"Activity on {device_id} in SQL")
                    other_device_activity = True
                    break
        if other_device_activity:
            app_log.info(f"{uuid} is associated with other more recent device activity")
            counts["active"] += 1
        else:
            app_log.info(f"User {user['logName']} is inactive since {last_activity}")
            app_log.info(f"Inactive devices: {','.join(device_ids)}")
            counts["idle"] += 1
            return user

    yielded = 0
    async for user in consume_concurrently(
        inactive, process_one, counts=counts, label="Inactive users"
    ):
        if user:
            yield user
            yielded += 1
            if limit and yielded >= limit:
                app_log.info(f"Reached idle user limit={limit}")
                return


async def find_groups_to_delete():
    filter = f"{to_delete} eq true"
    if BACKLOG_DATE:
        filter = f"{filter} and {to_delete_date} le {BACKLOG_DATE}"
    count = 0
    async for group in graph.list_groups(filter=filter):
        if not group.get(to_delete):
            raise RuntimeError(
                f"Group {group['displayName']} does not have toDelete set!"
            )
        if not group.get(to_delete_date):
            app_log.warning(
                f"Group {group['displayName']} marked toDelete, but no date! Saving for later."
            )
            await graph.mark_for_deletion(group)
            continue
        count += 1
        if count % 100 == 0:
            app_log.info(f"Found {count} devices to delete")
        yield group
    app_log.info(f"Found {count} total devices to delete")


@sql.with_db(ApplicationIntent="ReadOnly")
def find_inactive_devices(db, cutoff=IDLE_CUTOFF):
    """Check for device ids that need deleting"""
    app_log.info(f"Checking for devices inactive since {cutoff}")
    cur = db.execute(r"{CALL getLastActivityBefore(?)}", (cutoff,))
    return cur.fetchall()


@sql.with_db(persistent=PERSISTENT_CHECK_DB, ApplicationIntent="ReadOnly")
def check_sql_data(db, device_id, activity_cutoff=None):
    """Check if there's data to delete"""
    app_log.info(f"Checking for SQL data for {device_id}")
    cur = db.execute(r"{CALL latestActivityForUUID(?)}", (device_id,))
    rows = cur.fetchall()
    if not rows:
        app_log.info(f"No SQL activity for {device_id}")
        return False
    last_activity = rows[0][1]
    if last_activity and last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    if last_activity and (activity_cutoff is None or activity_cutoff < last_activity):
        app_log.info(f"Last SQL activity for {device_id}: {last_activity}")
        return True
    return False


@sql.with_db(pooled=False)
def delete_sql_data(db, *device_ids):
    """Find and delete data from the sql database

    Returns [True|False] for whether each device actually had data to delete
    """
    device_csv = ",".join(device_ids)
    app_log.warning(f"Deleting SQL data for {device_csv}")
    deleted_something = []
    # TODO: single csv call
    for device_id in device_ids:
        # run activity check again because check_sql_data runs against the read replica
        # which can be out of date relative to master
        # this appears important for re-run after a short period
        activity_rows = db.execute(
            r"{CALL latestActivityForUUID(?)}", (device_id,)
        ).fetchall()
        if not activity_rows:
            app_log.info(f"No SQL activity to delete for {device_id}")
            deleted_something.append(False)
            continue
        last_activity = activity_rows[0][1]
        if not last_activity:
            app_log.info(f"No SQL activity to delete for {device_id}")
            deleted_something.append(False)
            continue
        deleted_something.append(True)
        cursor = db.execute(r"{CALL deleteforUUID (?)}", (device_id,))
        cursor.commit()
    return deleted_something


class Deleter:
    """object wrapping batched async deletions

    deletions are run serially in batches in a background thread
    """

    Halt = object()

    def __init__(
        self, batch_seconds=DELETE_BATCH_SECONDS, batch_size=DELETE_BATCH_SIZE
    ):
        self.batch_seconds = batch_seconds
        self.batch_size = batch_size
        self.batch = []
        self.queue = Queue()
        self.thread = Thread(target=self.consume)
        self.thread.start()

    def stop(self, block=False):
        """Stop the deletion thread

        if block=True, block and wait for the thread to quit
        else: return awaitable Future for completion of the thread
        """
        app_log.warning("Stopping deletion queue")
        concurrent_future = concurrent.futures.Future()
        self.queue.put((self.Halt, concurrent_future))
        if block:
            self.thread.join()
        else:
            return asyncio.wrap_future(concurrent_future)

    def request_deletion(self, device_id):
        """Submit a device id for batch deletion"""
        app_log.info(f"Requesting db deletion of {device_id}")

        if not self.thread.is_alive():
            raise RuntimeError("Deletion thread not running!")

        # wrap thread-safe concurrent Future in awaitable asyncio Future
        # we will use thread-safe Future internally, caller will await asyncio Future
        concurrent_future = concurrent.futures.Future()
        asyncio_future = asyncio.wrap_future(concurrent_future)
        self.queue.put((device_id, concurrent_future))
        return asyncio_future

    def consume(self):
        """Consume the deletion queue in the background"""
        self.batch = batch = []
        finished = False
        finish_future = None
        while not finished:
            should_delete = False
            try:
                device_id, future = self.queue.get(timeout=self.batch_seconds)
            except Empty:
                # idle, submit deletion if there's anything to delete
                should_delete = bool(batch)
            else:
                if device_id is self.Halt:
                    # received halt message, delete anything pending and exit
                    app_log.info(
                        f"Halt of deletion requested, {len(batch)} items to delete"
                    )
                    finished = True
                    finish_future = future
                    should_delete = bool(batch)
                else:
                    # deletion requested, add to batch and delete if batch is full
                    app_log.debug(f"Device {device_id} added to deletion batch")
                    batch.append((device_id, future))
                    should_delete = len(batch) >= self.batch_size

            if not should_delete:
                continue

            # consume the batch
            app_log.info(f"Submitting {len(batch)} devices for deletion")
            device_ids = []
            futures = []
            for device_id, future in batch:
                device_ids.append(device_id)
                futures.append(future)
            batch[:] = []
            with timer(f"Deleted {len(device_ids)} devices from the db"):
                try:
                    deleted_somethings = asyncio.run(delete_sql_data(*device_ids))
                except Exception as e:
                    app_log.error(f"Error processing deletion: {e}")
                    # propagate errors to awaited Futures
                    for future in futures:
                        future.set_exception(e)
                else:
                    # signal deletions as completed
                    for deleted_something, future in zip(deleted_somethings, futures):
                        future.set_result(deleted_something)
        app_log.info("Exiting deletion queue")
        if finish_future:
            finish_future.set_result(None)


@lru_cache()
def get_deleter():
    """Get cached global deletion thread"""
    app_log.info("Creating global deletion thread")
    return Deleter()


async def check_and_delete_sql(group):
    """Check if there's data to delete and then delete it, if so"""
    device_id = group["displayName"]
    has_sql_data = await check_sql_data(device_id)
    if has_sql_data:
        return await get_deleter().request_deletion(device_id)
    return has_sql_data


async def delete_everything(concurrency=CONCURRENCY, max_failures=MAX_FAILURES):
    """Delete everything marked for deletion"""
    # limit concurrent processing of deletions
    semaphore = asyncio.Semaphore(concurrency)
    now = datetime.now(timezone.utc)
    counts = defaultdict(int)

    async def process_one(group):
        device_id = group["displayName"]
        # delete the device from iothub (this should have already happened)
        deleted = []
        if not group.get(iot_deleted_date):
            try:
                await devices.delete_devices(device_id)
            except HTTPClientError as e:
                if e.code == 404:
                    pass
                else:
                    raise
            else:
                counts["iot"] += 1
            await graph.mark_iot_deleted(group)
            deleted.append("iot")
        delete_date = parse_date(group.get(to_delete_date))

        # TODO: check stored deletion dates?
        timestamp = isonow()
        if not (SQL_CUTOFF_DATE and delete_date < SQL_CUTOFF_DATE):
            deleted_sql = await check_and_delete_sql(group)
            if deleted_sql:
                counts["sql"] += 1
                deleted.append("sql")
            if deleted_sql or not group.get(sql_deleted_date):
                await graph.set_group_attr(group, sqlDeletedDate=timestamp)

        if deleted:
            app_log.info(
                f"Deleted {','.join(deleted)} for {device_id}, marked for deletion on {delete_date}"
            )
        elif SQL_CUTOFF_DATE and delete_date >= SQL_CUTOFF_DATE:
            app_log.info(
                f"Not removing {device_id}, marked for deletion on {delete_date} after {SQL_CUTOFF_DATE}"
            )
        else:

            app_log.info(
                f"Nothing left to delete for {device_id}, marked for deletion on {delete_date}"
            )
            # only after we are sure data won't be re-imported do we remove a device group
            # deletion cutoff is defined as the last possible import time
            # (iot deletion + data lake expiry + 1 day)
            last_possible_import = parse_date(group.get(iot_deleted_date)) + timedelta(
                days=DATA_LAKE_DAYS + 1
            )
            if last_possible_import < now:
                counts["group"] += 1
                app_log.warning(f"Deleting old inactive device {device_id}")
                await graph.delete_group(group)

    async for _ in consume_concurrently(
        find_groups_to_delete(),
        process_one,
        label="Deletion",
        counts=counts,
        concurrency=concurrency,
        max_failures=max_failures,
    ):
        pass


async def expire_directories(parent_dir, expiry, dry_run=False):
    """Expire subdirectories directories older than expiry

    parent_dir is the parent directory name, e.g. 'undelete'

    expiry is the expiration cutoff as a datetime or
    an integer age in days, counted back from midnight today
    """
    if isinstance(expiry, int):
        if expiry == 0 and not dry_run:
            app_log.warning("0 expiry; not deleting all data, assuming dry run")
            dry_run = True
        now = datetime.now(timezone.utc)
        today = now - timedelta(hours=now.hour)
        expiry = today - timedelta(days=expiry)
    app_log.info(
        f"Deleting subdirectories in {storage.fs_name}/{parent_dir} older than {expiry}"
    )

    fs_client = storage.fs_clients[(storage.storage_account, storage.fs_name)]

    try:
        fs_client.get_directory_client(parent_dir).get_directory_properties()
    except azure.core.exceptions.ResourceNotFoundError:
        app_log.warning(
            f"Nothing to delete in nonexistent {storage.fs_name}/{parent_dir}"
        )
        return

    def process_one(path):
        dc = fs_client.get_directory_client(path)
        props = dc.get_directory_properties()
        if props.last_modified < expiry:
            app_log.info(
                f"{'(not really) ' * dry_run}Deleting {dc.path_name} from {props.last_modified}"
            )
            if not dry_run:
                dc.delete_directory()
        else:
            app_log.info(f"Not deleting {dc.path_name} from {props.last_modified}")

    done, pending = set(), set()
    with ThreadPoolExecutor(CONCURRENCY) as pool:
        for path in fs_client.get_paths(parent_dir, recursive=False):
            pending.add(asyncio.wrap_future(pool.submit(process_one, path)))
            done, pending = await asyncio.wait(pending, timeout=0.01)
            if done:
                await asyncio.gather(*done)

    if pending:
        await asyncio.gather(*pending)


async def delete_raw_data():
    """Delete expired files in the raw data lake

    Deletes temporary work files in .rewrite and undelete
    and deletes raw data files from IoTHub that have been imported
    already.

    FIXME: .rewrite and undelete are for recovery from targeted
    delete in the lake, which is no longer performed,
    so these will not create any more files.
    These deletions can be removed soon.
    """
    await expire_directories(".rewrite", REWRITE_DAYS)
    await expire_directories("undelete", UNDELETE_DAYS)

    cutoff = datetime.now(timezone.utc) - timedelta(days=DATA_LAKE_DAYS)
    # wraparound to previous month, just in case
    last_month = cutoff - timedelta(days=cutoff.day + 1)
    for day in (
        last_month,
        cutoff,
    ):
        await expire_directories(
            storage.iothub_data_dir + day.strftime("/%Y/%m"), DATA_LAKE_DAYS,
        )


async def delete_idle_users(
    concurrency=CONCURRENCY, limit=IDLE_DELETE_LIMIT, dry_run=False
):
    """Find users that should be deleted

    Two reasons:

    - marked as consentRevoked, but still present
      (could have been a crash during consent-revoked request)
    - last activity before 7-day activity cutoff

    Both are treated the same as an explicit revoke-consent request

    TODO: One missing case not yet implemented:

    - *never* uploaded any data. Of lower importance
      because we don't have any data about these users,
      but it would be good to reclaim their unused device ids
      and remove their phone numbers.
      Can be implemented over time in a sampling manner
      if we can make requests for users that will be random samples.
    """

    async def process_one(user):
        if not dry_run:
            await graph.process_user_deletion(user)

    async for user in consume_concurrently(
        find_users_to_delete(limit=limit),
        process_one,
        label=f"Inactive deletions{' (dry run)' * dry_run}",
    ):
        pass


async def main():
    define(
        name="idle_users",
        type=bool,
        default=False,
        help="locate and identify idle users who should be deleted",
    )

    define(
        name="dry_run",
        type=bool,
        default=False,
        help="dry run (don't actually perform deletions)",
    )

    parse_command_line()

    if options.idle_users:
        with timer(f"Deleted idle users{' (dry run)' * options.dry_run}"):
            await delete_idle_users(dry_run=options.dry_run)
        return

    with timer("Deleted old raw data files"):
        await delete_raw_data()

    deleter = get_deleter()
    with timer("Database deletion"):
        await delete_everything(concurrency=CONCURRENCY, max_failures=MAX_FAILURES)
    # wait for batched deletions to complete
    await deleter.stop(block=False)


if __name__ == "__main__":
    asyncio.run(main())
