"""interface with iothub devices
Check out

https://github.com/Azure/azure-iot-sdk-python/blob/master/azure-iot-hub/azure/iot/hub/iothub_registry_manager.py#L50

for info about how to interact wit the IoTHubRegistryManager

Note: talk to the IotHub REST API ourselves because
IoTHubRegistryManager has extreme performance problems
"""
import asyncio
import base64
import datetime
import json
import os
import re
import secrets
import struct
import time
import uuid
from binascii import b2a_hex
from threading import local

from azure.iot.hub.sastoken import SasToken
from tornado.httpclient import HTTPRequest
from tornado.httputil import url_concat
from tornado.log import app_log

from .utils import fetch

before_times = datetime.datetime(
    year=2000, month=1, day=1, tzinfo=datetime.timezone.utc
)
iothub_connection_str = os.environ["IOTHUB_CONNECTION_STRING"]
client_threads = int(os.environ.get("IOTHUB_CLIENT_THREADS") or "4")

iothub_hostname = re.search(
    r"hostname=([^;]+);", iothub_connection_str, flags=re.IGNORECASE
).group(1)

API_VERSION = "2020-03-01"

connection_info = {}
for part in iothub_connection_str.strip(";").split(";"):
    key, value = part.split("=", 1)
    connection_info[key.lower()] = value

_local = local()


async def iothub_request(path, *, headers=None, body=None, method="GET", raw=False):
    """Make an HTTP request to IoTHub ourselves"""
    sastoken = SasToken(
        connection_info["hostname"],
        key=connection_info["sharedaccesskey"],
        key_name=connection_info["sharedaccesskeyname"],
    )

    if isinstance(body, str):
        body = body.encode("utf8")

    req_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": "0" if body is None else str(len(body)),
        # see iot.hub.auth.signed_session
        "Authorization": str(sastoken),
    }
    if headers:
        req_headers.update(headers)

    url = url_concat(
        f"https://{connection_info['hostname']}{path}", {"api-version": API_VERSION},
    )
    if method == "GET":
        body = None

    req = HTTPRequest(method=method, url=url, headers=req_headers, body=body)
    resp = await fetch(req)
    if raw:
        return resp
    if "application/json" in resp.headers.get("Content-Type", ""):
        return json.loads(resp.body.decode("utf8"))
    if resp.body:
        return resp.body


def new_device_id():
    """Generate a new device id

    use uuid4 with:

    - 4B timestamp to guarantee no collisions outside one second
    """
    buf = uuid.uuid4().bytes
    # add timer and hostname hash snippet
    buf = b"".join([struct.pack("I", int(time.time())), buf[4:]])
    return b2a_hex(buf).decode("ascii")


def new_device_secret():
    """return a new device secret

    as a base64 string
    """
    return base64.encodebytes(secrets.token_bytes(32)).decode("ascii").strip()


async def create_new_device():
    """Create a new device

    Returns the connection string
    """
    device_id = new_device_id()
    primary_key = new_device_secret()
    secondary_key = new_device_secret()
    tic = time.perf_counter()
    body = json.dumps(
        {
            "deviceId": device_id,
            "status": "True",
            "authentication": {
                "symmetricKey": {
                    "primaryKey": primary_key,
                    "secondaryKey": secondary_key,
                },
                "type": "sas",
            },
            "capabilities": {"iotEdge": False},
        }
    )
    device = None
    status = "failed"
    try:
        device = await iothub_request(f"/devices/{device_id}", method="PUT", body=body)
        status = "ok"
        return device
    finally:
        toc = time.perf_counter()
        app_log.info(
            f"Registered device {device_id} (status={status}) in {int(1000 * (toc-tic))}ms"
        )


def get_device(device_id):
    """Get a single device from device_id.

    This uses the API from the IoTHubRegistryManager.
    If your need to get a lot of devices you should
    use the `get_devices` method instead which gets
    the devices using queries.
    """
    return iothub_request(f"/devices/{device_id}")


async def lookup_device_keys(device_id):
    """Lookup primary and secondary keys for the associated device_id

    This is used to sign HMACs in requests from the app
    where we do not authenticate with B2C token.
    """

    device = await get_device(device_id)
    if device is None:
        return None
    return device["authentication"]["symmetricKey"]


query_string = r"""
SELECT deviceId, lastActivityTime, connectionState, properties
FROM devices
"""


async def get_devices(*device_ids, limit=None, per_page=10000):
    """Get devices

    async generator
    """
    query = query_string
    if device_ids:
        device_id_str = "[{}]".format(
            ",".join([f"'{device_id}'" for device_id in device_ids])
        )
        query = " ".join([query, f"WHERE deviceId IN {device_id_str}"])

    headers = {}
    if limit:
        per_page = min(per_page, limit)
        headers = {"x-ms-max-item-count": str(per_page)}
    count = 0
    continuation_token = "..."
    while continuation_token:
        resp = await iothub_request(
            "/devices/query",
            body=json.dumps({"query": query}),
            method="POST",
            headers=headers,
            raw=True,
        )
        # TODO: optimization; schedule next fetch before yield?
        results = json.loads(resp.body.decode("utf8"))
        for device in results:
            yield device
            count += 1
            if limit and count >= limit:
                return
        continuation_token = resp.headers.get("x-ms-continuation")
        if continuation_token:
            headers["x-ms-continuation"] = continuation_token


def delete_device(device_id):
    """Delete one device"""
    return iothub_request(
        f"/devices/{device_id}", headers={"If-Match": "*"}, method="DELETE"
    )


async def delete_devices(*device_ids, raise_on_error=True):
    """Delete one or more device ids

    After deletion, messages will not be able to arrive
    """
    if not device_ids:
        raise ValueError("Please specify a device id to delete")
    app_log.info(f"Deleting devices: {','.join(device_ids)}")
    futures = []
    for device_id in device_ids:
        futures.append(delete_device(device_id))
    return await asyncio.gather(*futures, return_exceptions=not raise_on_error)


async def main():
    """Test device connections by reporting on all devices"""
    connected_count = 0
    inactive_count = 0
    total = 0
    async for device in get_devices():
        total += 1
        if device.connection_state == "Connected":
            connected_count += 1
        if not device.last_activity_time or device.last_activity_time < before_times:
            inactive_count += 1
        else:
            print(
                device.device_id,
                device.last_activity_time,
                device.connection_state,
                device.properties.reported["$metadata"]["$lastUpdated"],
            )
    print(f"total = {total}")
    print(f"inactive = {inactive_count}")
    print(f"connected = {connected_count}")


if __name__ == "__main__":
    asyncio.run(main())
