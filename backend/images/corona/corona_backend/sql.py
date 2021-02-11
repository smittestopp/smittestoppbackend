"""SQL utilities"""

import asyncio
import datetime
import json
import os
import struct
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import objgraph
import pyodbc
from tornado.log import app_log

from corona_backend import utils

from .graph import request_graph_token

# from .utils import isoformat, mask_phone, timer, now_at_utc

SQL_COPT_SS_ACCESS_TOKEN = 1256

DEBUG_OBJGRAPH = os.environ.get("DEBUG_OBJGRAPH") == "1"


async def get_database_token(tenant_id, client_id, client_secret, clear_cache=False):
    """Get a database token suitable for pyodbc

    which requires some weird utf16 encoding

    To be used with `attrs_before={SQL_COPT_SS_ACCESS_TOKEN: db_token}`
    """
    token = await request_graph_token(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret,
        scope="https://database.windows.net/.default",
        clear_cache=clear_cache,
    )

    encoded_token = token.encode("utf_16_le")
    return struct.pack("=i", 2 * len(encoded_token)) + encoded_token


CONNECT_RETRIES = int(os.environ.get("SQL_CONNECT_RETRIES") or "6")
CONNECT_FIRST_INTERVAL = float(os.environ.get("SQL_CONNECT_FIRST_INTERVAL") or "0.3")


async def connect_to_database(**extra_params):
    """Connect to the azure database"""

    params = {
        "DRIVER": "{ODBC Driver 17 for SQL Server}",
        "SERVER": os.environ["SQL_SERVER"],
        "PORT": "1433",
        "DATABASE": os.environ["SQL_DATABASE"],
    }
    params.update(extra_params)

    kwargs = {}
    token = None
    if os.environ.get("SQL_CLIENT_ID"):
        token = await get_database_token(
            tenant_id=os.environ["SQL_TENANT_ID"],
            client_id=os.environ["SQL_CLIENT_ID"],
            client_secret=os.environ["SQL_CLIENT_SECRET"],
        )
        kwargs["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: token}
    elif os.environ.get("SQL_USER"):
        params["UID"] = os.environ["SQL_USER"]
        params["PWD"] = os.environ["SQL_PASSWORD"]
    else:
        raise ValueError(
            "Must specify SQL_USER+PASSWORD or SQL_CLIENT_ID,SECRET for token access"
        )
    connection_string = ";".join(f"{key}={value}" for key, value in params.items())
    for i in range(CONNECT_RETRIES):
        app_log.info(f"Attempting connection to {params['SERVER']}")
        try:
            return pyodbc.connect(connection_string, ansi=True, pooling=True, **kwargs)
        except Exception as e:
            if i + 1 == CONNECT_RETRIES:
                raise
            app_log.error(
                f"Error connecting to database, retrying: {e}. Attempt: {str(i)}"
            )
            # db connection seems to fail sometimes!
            # bizarre - retrying with the same bytes object fails
            # but retrying with the same byte *value* succeeds
            if token:
                token = await get_database_token(
                    tenant_id=os.environ["SQL_TENANT_ID"],
                    client_id=os.environ["SQL_CLIENT_ID"],
                    client_secret=os.environ["SQL_CLIENT_SECRET"],
                    clear_cache=True,
                )
                kwargs["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: token}
            await asyncio.sleep(2 ** i * CONNECT_FIRST_INTERVAL)


db_pools = defaultdict(
    lambda: ThreadPoolExecutor(int(os.environ.get("DB_THREADS") or 4))
)


_check_connection_query = r"SELECT CASE DATABASEPROPERTYEX( DB_NAME(), 'Updateability') WHEN 'READ_ONLY' THEN 'Y' ELSE 'N' END"


def with_db(*, persistent=False, pooled=True, **params):
    """Decorator for calling a function in a background thread

    Arguments passed to with_db are passed along to connect_to_database
    """
    if persistent and not params.get("ApplicationIntent", "").lower() == "readonly":
        raise ValueError("persistent connections only allowed read-only")

    if pooled:
        pool_key = json.dumps(params, sort_keys=True)
    else:
        # use single dedicated thread for unpooled requests
        pool_key = False
        if pool_key not in db_pools:
            db_pools[pool_key] = ThreadPoolExecutor(1)
    db_pool = db_pools[pool_key]

    def decorator(f):
        async def async_with_db(*args, **kwargs):
            def in_thread():
                db = None
                if persistent:
                    try:
                        db = async_with_db.local.db
                    except AttributeError:
                        pass
                    else:
                        try:
                            db.execute(_check_connection_query).fetchall()
                        except Exception as e:
                            app_log.error(f"Not reusing closed connection: {e}")
                            del async_with_db.local.db
                            db = None

                if db is None:
                    with utils.timer("db connect"):
                        # Check the object counts before pyodbc connection.
                        if DEBUG_OBJGRAPH:
                            app_log.info(
                                f"Checking the object counts before pyodbc connection: {objgraph.growth()}"
                            )

                        db = asyncio.run(connect_to_database(**params))

                        # Check the object counts after pyodbc connection.
                        # There should be a pyodbc object in memory
                        if DEBUG_OBJGRAPH:
                            app_log.info(
                                f"Checking the object counts after pyodbc connection: {objgraph.growth()}"
                            )

                    if persistent:
                        async_with_db.local.db = db

                with utils.timer(f"db query {f.__name__}"):
                    try:
                        return f(db, *args, **kwargs)
                    finally:
                        if not persistent:
                            # Check the object counts before pyodbc connection is closed.
                            # Check if the pyodbc object still exists in memory
                            if DEBUG_OBJGRAPH:
                                app_log.info(
                                    f"Checking the object counts before pyodbc connection closes: {objgraph.growth()}"
                                )

                            db.close()

                            # Check the object counts after pyodbc connection is closed.
                            # Check if the pyodbc object is removed from memory
                            if DEBUG_OBJGRAPH:
                                app_log.info(
                                    f"Checking the object counts after pyodbc connection closes: {objgraph.growth()}"
                                )

            with utils.timer(f"async db query {f.__name__}"):
                return await asyncio.wrap_future(db_pool.submit(in_thread))

        # attach method to close connections when persisten
        def close_in_thread():
            try:
                db = async_with_db.local.db
            except AttributeError:
                pass
            else:
                db.close()
                del async_with_db.local.db

        def close():
            for i in range(2 * len(db_pool)):
                db_pool.submit(close_in_thread).result()

        async_with_db.local = threading.local()
        async_with_db.close = close

        return async_with_db

    return decorator


# SQL access functions


def cast_nullable_float(n):
    """Cast to float (we get some Decimal from SQL) allowing for None"""
    if n is None:
        return n
    return float(n)


@with_db()
def log_access(
    db,
    *,
    timestamp,
    phone_numbers,
    person_name,
    person_id,
    person_organization,
    organization,
    legal_means,
):
    """Log a single data access event to one or more phone numbers"""
    if isinstance(phone_numbers, str):
        phone_numbers = [phone_numbers]
    for phone_number in phone_numbers:
        cursor = db.execute(
            r"{CALL dbo.applogInsert (?,?,?,?,?,?,?)}",
            (
                timestamp,
                phone_number,
                person_name,
                person_id,
                person_organization,
                organization,
                legal_means,
            ),
        )
        cursor.commit()


@with_db(ApplicationIntent="ReadOnly")
def get_access_log(
    db,
    phone_number,
    person_name="",
    person_id="",
    person_organization="",
    organization="<none>",
    page_number=1,
    per_page=30,
):
    """Fetch the access log for a given phone number"""
    total = group_total = 0
    app_log.info(f"Getting access log for {utils.mask_phone(phone_number)}")
    events = []
    for (
        timestamp,
        number,
        p_name,
        p_id,
        p_org,
        technical_org,
        legal_means,
        group_total,
        total,
    ) in db.execute(
        "{CALL applogfetch(?, ?, ?, ?, ?, ?, ?)}",
        phone_number,
        person_name,
        person_id,
        person_organization,
        organization,
        page_number,
        per_page,
    ).fetchall():
        person_fields = {}
        if not p_id and p_name.isdigit():
            p_id = p_name
            p_name = ""
            app_log.warning(
                f"Including extra match from old person id record: {timestamp} {p_id}"
            )
        elif p_org is None:
            try:
                person_fields = json.loads(p_name)
            except ValueError:
                pass
            else:
                app_log.warning(
                    f"Including extra match from old JSON record: {timestamp} {person_fields}"
                )
        event = {
            "timestamp": utils.isoformat(timestamp),
            "phone_number": phone_number,
            "person_name": p_name or "",
            "person_organization": p_org or "",
            "person_id": p_id or "",
            "technical_organization": technical_org or "Norsk Helsenett",
            "legal_means": legal_means,
            "count": group_total,
        }
        event.update(person_fields)
        events.append(event)

    return events, total


@with_db(ApplicationIntent="ReadOnly")
def get_gps_events(
    db, device_ids, page_number=1, per_page=30, time_from=None, time_to=None
):
    """Retrieve gps events from the database for one or more devices

    Returns gps events as a list of dicts
    """
    if isinstance(device_ids, str):
        device_ids = [device_ids]

    if time_from is None:
        time_from = utils.now_at_utc() - datetime.timedelta(days=90)
    if time_to is None:
        time_to = utils.now_at_utc() + datetime.timedelta(hours=1)

    events = []
    total = 0
    for (
        plaform,
        osversion,
        appversion,
        model,
        time_from,
        time_to,
        latitude,
        longitude,
        accuracy,
        speed,
        speed_accuracy,
        altitude,
        altitude_accuracy,
        total,
    ) in db.execute(
        "{CALL getdatabyUUIDList (?,?,?,?,?)}",
        (",".join(device_ids), time_from, time_to, page_number, per_page),
    ).fetchall():
        # from schema, *all* fields are nullable
        # so make sure that any casting handles None
        event = {
            "time_from": utils.isoformat(time_from),
            "time_to": utils.isoformat(time_to),
            "latitude": cast_nullable_float(latitude),
            "longitude": cast_nullable_float(longitude),
            "accuracy": accuracy,
            "speed": speed,
            "speed_accuracy": speed_accuracy,
            "altitude": altitude,
            "altitude_accuracy": altitude_accuracy,
        }
        events.append(event)
    return events, total


@with_db()
def request_contact_ids(
    db, device_id, *, count=10,
):
    """Request new contact ids for a given device id

    proc signature:

    getnewuuids(@uuid varchar(36), @howmany int=100)
    -> select @uuid, new_uuid, @created

    """
    contact_ids = []
    cursor = db.execute(r"{CALL getnewuuids (?,?)}", (device_id, count))
    for (dev_id, contact_id, created,) in cursor.fetchall():
        contact_ids.append(contact_id)
    cursor.commit()
    return contact_ids


@with_db()
def upsert_birth_year(db, values):
    cursor = db.cursor()
    cursor.executemany("{CALL dbo.upsertBirthYear(?, ?)}", values)
    cursor.commit()


@with_db()
def get_birth_year(db, device_id):
    row = db.execute(r"SELECT birthyear FROM dbo.getBirthYear(?)", device_id).fetchone()
    if row:
        return row[0]
