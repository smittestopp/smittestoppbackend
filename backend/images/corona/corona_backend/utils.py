"""General utilities"""
import asyncio
import datetime
import json
import logging
import os
import random
import socket
import time
import warnings
from contextlib import contextmanager

from tornado import ioloop
from tornado.httpclient import AsyncHTTPClient, HTTPClientError
from tornado.log import app_log
from tornado.simple_httpclient import HTTPTimeoutError

FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT") or 20)

# demote azure logger to warning because it logs debug-level data at info-level
logging.getLogger("azure").setLevel(logging.WARNING)

try:
    AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")
except ImportError as e:
    warnings.warn(f"Could not load pycurl: {e}\npycurl is recommended for production.")


async def fetch(url_or_req, *args, timeout=FETCH_TIMEOUT, **kwargs):
    """Fetch with a wrapper to log errors"""

    channel = {}
    try:
        url = url_or_req.url
        method = url_or_req.method
    except AttributeError:
        url = url_or_req
        method = kwargs.get("method", "GET")

    log_url = f"{method} {url.split('?', 1)[0]}"
    deadline = time.perf_counter() + timeout

    async def retry_connections():
        app_log.info(f"{log_url}")
        try:
            return await AsyncHTTPClient().fetch(url_or_req, *args, **kwargs)
        except (TimeoutError, HTTPTimeoutError, socket.gaierror) as e:
            app_log.error(f"Socket error fetching {log_url}: {e}")
            return False
        except HTTPClientError as e:
            # retry on server availability errors
            if e.code in {502, 503, 599}:
                app_log.error(f"Error fetching {log_url}: {e}")
                return False
            elif e.code == 429:
                retry_after_header = e.response.headers.get("Retry-After")
                try:
                    retry_after = int(retry_after_header)
                except Exception as e:
                    app_log.error(f"Failed to handle Retry-After: {retry_after_header}")
                    retry_after = 30
                app_log.error(
                    f"Rate limit fetching {log_url}: {e} retrying after {retry_after}s"
                )
                max_sleep = max(0, deadline - time.perf_counter())
                await asyncio.sleep(min(max_sleep, retry_after))
                return False
            else:
                raise

    try:
        return await exponential_backoff(
            retry_connections, timeout=timeout, fail_message=""
        )
    except HTTPClientError as e:
        if e.response is None:
            app_log.error(f"Error fetching {log_url}: {e}")
            raise

        if e.response and e.response.body:
            message = e.response.body.decode("utf-8", "replace")[:1024]
            try:
                body_json = json.loads(message)
                message = body_json["error_description"]
            except (KeyError, ValueError):
                pass
            app_log.error(f"Error fetching {log_url}: {message}")
        raise


def mask_phone(phone_number):
    """Mask a phone number, e.g. +4712345678 -> +47XXXX678

    Mostly for logging purposes
    """
    mask_len = len(phone_number) - 6
    return f"{phone_number[:3]}{'X' * mask_len}{phone_number[-3:]}"


async def exponential_backoff(
    pass_func,
    fail_message,
    start_wait=0.2,
    scale_factor=2,
    max_wait=5,
    timeout=10,
    timeout_tolerance=0.1,
    *args,
    **kwargs,
):
    """
    Exponentially backoff until `pass_func` is true.

    Imported from JupyterHub 1.1 (BSD 3-Clause license)

    The `pass_func` function will wait with **exponential backoff** and
    **random jitter** for as many needed iterations of the Tornado loop,
    until reaching maximum `timeout` or truthiness. If `pass_func` is still
    returning false at `timeout`, a `TimeoutError` will be raised.

    The first iteration will begin with a wait time of `start_wait` seconds.
    Each subsequent iteration's wait time will scale up by continuously
    multiplying itself by `scale_factor`. This continues for each iteration
    until `pass_func` returns true or an iteration's wait time has reached
    the `max_wait` seconds per iteration.

    `pass_func` may be a future, although that is not entirely recommended.

    Parameters
    ----------
    pass_func
        function that is to be run
    fail_message : str
        message for a `TimeoutError`
    start_wait : optional
        initial wait time for the first iteration in seconds
    scale_factor : optional
        a multiplier to increase the wait time for each iteration
    max_wait : optional
        maximum wait time per iteration in seconds
    timeout : optional
        maximum time of total wait in seconds
    timeout_tolerance : optional
        a small multiplier used to add jitter to `timeout`'s deadline
    *args, **kwargs
        passed to `pass_func(*args, **kwargs)`

    Returns
    -------
    value of `pass_func(*args, **kwargs)`

    Raises
    ------
    TimeoutError
        If `pass_func` is still false at the end of the `timeout` period.

    Notes
    -----
    See https://www.awsarchitectureblog.com/2015/03/backoff.html
    for information about the algorithm and examples. We're using their
    full Jitter implementation equivalent.
    """
    loop = ioloop.IOLoop.current()
    deadline = loop.time() + timeout
    # add jitter to the deadline itself to prevent re-align of a bunch of
    # timing out calls once the deadline is reached.
    if timeout_tolerance:
        tol = timeout_tolerance * timeout
        deadline = random.uniform(deadline - tol, deadline + tol)
    scale = 1
    while True:
        ret = await pass_func(*args, **kwargs)
        # Truthy!
        if ret:
            return ret
        remaining = deadline - loop.time()
        if remaining < 0:
            # timeout exceeded
            break
        # add some random jitter to improve performance
        # this prevents overloading any single tornado loop iteration with
        # too many things
        dt = min(max_wait, remaining, random.uniform(0, start_wait * scale))
        scale *= scale_factor
        await asyncio.sleep(dt)
    raise TimeoutError(fail_message)


@contextmanager
def timer(message):
    """Context manager for reporting time measurements"""
    tic = time.perf_counter()
    extra = ""
    try:
        yield
    except Exception:
        extra = " (failed)"
        raise
    finally:
        toc = time.perf_counter()
        ms = int(1000 * (toc - tic))
        app_log.info(f"{message}{extra}: {ms}ms")


def isoformat(dt):
    """iso8601 utc timestamp with Z instead of +00:00"""
    if dt is None:
        return dt
    if type(dt) is datetime.date:
        return dt.isoformat()
    if dt.tzinfo:
        return dt.astimezone(datetime.timezone.utc).isoformat().split("+", 1)[0] + "Z"
    else:
        return dt.isoformat() + "Z"


def now_at_utc():
    return datetime.datetime.now(datetime.timezone.utc)
