#!/usr/bin/env python3
"""Worker processing analysis requests from redis job queue"""

import datetime
import json
import os
import sys
import time
import traceback

import pyodbc
import rediswq

from dateutil.parser import parse as parse_date
import tornado.options
from tornado.log import app_log

from corona.data import connect_to_azure_database
from corona.analysis.analysis_pipeline import run_analysis_pipeline

ANALYSIS_LEASE_SECONDS = int(os.environ.get("ANALYSIS_LEASE_SECONDS") or 120)
ANALYSIS_DAYS = int(os.environ.get("ANALYSIS_DAYS") or 0)
PIN_TIME_TO = os.environ.get("PIN_TIME_TO")
if PIN_TIME_TO:
    PIN_TIME_TO = parse_date(PIN_TIME_TO)


def set_to_list(obj):
    """Cast sets to list to make them jsonable"""
    if isinstance(obj, set):
        return sorted(obj)
    return obj


def process_one(q, item):
    """Process one request off the queue"""
    task = json.loads(item.decode("utf-8"))
    device_id = task["device_id"]
    request_id = task["request_id"]
    result_key = task["result_key"]
    expiry = task["expiry"]

    kwargs = {}

    # always include reequest_id in kwargs, to be used as correlation-id for logging, etc.
    kwargs["request_id"] = request_id

    # defaults for time range from env, if unspecified
    if PIN_TIME_TO:
        kwargs["timeTo"] = PIN_TIME_TO
    if ANALYSIS_DAYS:
        time_to = kwargs.get("timeTo", datetime.datetime.now(datetime.timezone.utc))
        time_from = time_to - datetime.timedelta(days=ANALYSIS_DAYS)
        kwargs["timeFrom"] = time_from

    # allow setting from API
    if task.get("time_from"):
        kwargs["timeFrom"] = parse_date(task["time_from"])
    if task.get("time_to"):
        kwargs["timeTo"] = parse_date(task["time_to"])

    app_log.info(
            json.dumps(
                {
                    "event": "analysis_starting",
                    "device_id": device_id,
                    "request_id": request_id
                }))

    result = {"device_id": device_id, "request_id": request_id, "status": "success"}

    try:
        result["result"] = run_analysis_pipeline(device_id, **kwargs)
    except pyodbc.InterfaceError:
        app_log.exception(f"request_id:{request_id} Database error running analysis on {device_id}")
        # release it to gc, don't complete the result
        q.release(item)
        return
    except Exception:
        exc_info = sys.exc_info()
        app_log.exception(f"request_id:{request_id} Failure running analysis on {device_id}")
        result["status"] = "error"
        result["message"] = "".join(traceback.format_exception(*exc_info))

    log_keys = result.keys()
    log_result_keys = []
    if result["status"] == "success":
        # safe-guard, probably not needed
        if "result" in result and isinstance(result["result"], dict):
            log_result_keys = result["result"].keys()
        else:
            app_log.info(
                    json.dumps(
                        {
                            "event": "unexpected_analysis_result",
                            "request_id": request_id,
                            "status": "unexpected_error",
                            "result": result
                        }))

    app_log.info(
            json.dumps(
                {
                    "event": "analysis_finished",
                    "device_id": device_id,
                    "request_id": request_id,
                    "status": result["status"],
                    "keys": ", ".join(log_keys),
                    "result-keys": ", ".join(log_result_keys)
                }))
    q.complete(item, result_key, expiry, json.dumps(result, default=set_to_list))


def main():
    host = os.getenv("REDIS_SERVICE_HOST", "localhost")
    password = os.getenv("REDIS_PASSWORD")
    queue_name = os.getenv("REDIS_JOBQUEUE_NAME", "analysis-jobs")

    tornado.options.parse_command_line()
    # test azure connection
    app_log.info("Testing database connection...")
    db = connect_to_azure_database()
    db.close()
    app_log.info("Database connection okay!")

    q = rediswq.RedisWQ(name=queue_name, host=host, password=password)
    app_log.info("Worker with sessionID: " + q.sessionID())
    app_log.info(f"Running with lease time {ANALYSIS_LEASE_SECONDS}")
    gc_interval = max(ANALYSIS_LEASE_SECONDS // 4, 10)
    app_log.info(f"Running garbage collection if idle for {gc_interval}")
    while True:
        item = q.lease(
            lease_secs=ANALYSIS_LEASE_SECONDS, block=True, timeout=gc_interval,
        )
        if item is None:
            app_log.debug("Waiting for work")
            q.gc()
            continue
        tic = time.perf_counter()
        process_one(q, item)
        toc = time.perf_counter()
        app_log.info(f"Analysis completed in {int(toc-tic)}s")


if __name__ == "__main__":
    main()
