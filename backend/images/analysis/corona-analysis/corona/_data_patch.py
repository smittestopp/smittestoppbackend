"""Patches for running corona analysis on the backend

should probably go away by contributing to analysis repo

adapted from async code in corona_backend
"""

import os
import struct
import time
from urllib.parse import urlencode

import jwt
import pyodbc
import requests
from tornado.log import app_log

_token_cache = {}

_expiry_buffer = 600  # number of seconds before expiry to request a new token

SQL_COPT_SS_ACCESS_TOKEN = 1256


def get_access_token(
    tenant_id,
    client_id,
    client_secret,
    scope="https://database.windows.net/.default",
    clear_cache=False,
):
    """Request an access token for the ms graph API

    Cache the result to re-use tokens until they are close to expiring
    """
    cache_key = (tenant_id, client_id, scope)

    if clear_cache:
        _token_cache.pop(cache_key, None)

    cached = _token_cache.get(cache_key)
    if cached:
        expiry = cached["expiry"]
        # don't re-use tokens that are within 10 minutes of expiring
        seconds_remaining = expiry - time.time()
        if seconds_remaining >= _expiry_buffer:
            app_log.debug("Reusing cached token")
            return cached["token"]
        else:
            app_log.info(
                f"Cached token is expiring in {int(seconds_remaining)}s, not using it"
            )
            _token_cache.pop(cache_key)

    app_log.info(f"Requesting new token for {scope}")
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    body_data = dict(
        client_id=client_id,
        client_secret=client_secret,
        grant_type="client_credentials",
        scope=scope,
    )

    resp = requests.post(
        token_url,
        data=urlencode(body_data),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    resp_json = resp.json()
    token = resp_json["access_token"]
    payload = jwt.decode(token, verify=False)

    # store in expiring cache
    _token_cache[cache_key] = {"token": token, "expiry": payload["exp"]}
    seconds = payload["exp"] - time.time() - _expiry_buffer
    app_log.info(f"Token acquired, using for {seconds:.0f} seconds")
    return token


def get_db_token(clear_cache=False):
    """Request an access token for the database

    returning it in the weird binary format SQL Server uses
    """
    token = get_access_token(
        tenant_id=os.environ["SQL_TENANT_ID"],
        client_id=os.environ["SQL_CLIENT_ID"],
        client_secret=os.environ["SQL_CLIENT_SECRET"],
        clear_cache=clear_cache,
    )
    encoded_token = token.encode("utf_16_le")
    odbc_token = struct.pack("=i", 2 * len(encoded_token)) + encoded_token
    return odbc_token


CONNECT_RETRIES = int(os.environ.get("SQL_CONNECT_RETRIES") or "6")
CONNECT_FIRST_INTERVAL = float(os.environ.get("SQL_CONNECT_FIRST_INTERVAL") or "0.3")


def connect_to_azure_database():
    """Get a database token suitable for pyodbc

    which requires some weird utf16 encoding

    To be used with `attrs_before={SQL_COPT_SS_ACCESS_TOKEN: db_token}`
    """
    params = {
        "DRIVER": "{ODBC Driver 17 for SQL Server}",
        "SERVER": os.environ["SQL_SERVER"],
        "PORT": "1433",
        "DATABASE": os.environ["SQL_DATABASE"],
        "ApplicationIntent": "ReadOnly",
    }
    kwargs = {}
    token = None
    if os.environ.get("SQL_CLIENT_ID"):
        odbc_token = get_db_token()
        kwargs["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: odbc_token}
    elif os.environ.get("SQL_USER"):
        params["USER"] = os.environ["SQL_USER"]
        params["PASSWORD"] = os.environ["SQL_PASSWORD"]
    else:
        raise ValueError(
            "Must specify SQL_USER,PASSWORD or SQL_CLIENT_ID,SECRET for token access"
        )

    for i in range(CONNECT_RETRIES):
        try:
            return pyodbc.connect(
                ";".join(f"{key}={value}" for key, value in params.items()),
                autocommit=True,
                ansi=True,
                **kwargs,
            )
        except Exception as e:
            if i + 1 == CONNECT_RETRIES:
                raise
            app_log.error(f"Error connecting to database, retrying: {e}")
            # bizarre - retrying with the same bytes object fails
            # but retrying with the same byte *value* usually succeeds
            # still, we have the highest success rate if we don't retry with a token that has failed
            # (this may be purely due to the extra time taken to request the token)
            odbc_token = get_db_token(clear_cache=True)
            kwargs["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: odbc_token}
            time.sleep(2 ** i * CONNECT_FIRST_INTERVAL)
