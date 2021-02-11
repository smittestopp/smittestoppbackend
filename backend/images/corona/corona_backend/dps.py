#!/usr/bin/env python3
"""
Device-provisioning
"""

import asyncio
import base64
import hashlib
import hmac
import os
import struct
import time
import uuid
from binascii import b2a_hex
from concurrent.futures import ProcessPoolExecutor

from tornado.log import app_log

# provisioning-related
provisioning_host = os.environ.get(
    "PROVISIONING_HOST", "global.azure-devices-provisioning.net"
)
id_scope = os.environ["ID_SCOPE"]
group_symmetric_key = os.environ["GROUP_SYMMETRIC_KEY"]


def new_device_id():
    """Generate a new device id

    use uuid4 with:

    - 4B timestamp to guarantee no collisions outside one second
    """
    buf = uuid.uuid4().bytes
    # add timer and hostname hash snippet
    buf = b"".join([struct.pack("I", int(time.time())), buf[4:]])
    return b2a_hex(buf).decode("ascii")


def derive_device_key(device_id, group_symmetric_key):
    """
    The unique device ID and the group master key should be encoded into "utf-8"
    After this the encoded group master key must be used to compute an HMAC-SHA256 of the encoded registration ID.
    Finally the result must be converted into Base64 format.
    The device key is the "utf-8" decoding of the above result.
    """
    message = device_id.encode("utf-8")
    signing_key = base64.b64decode(group_symmetric_key.encode("utf-8"))
    signed_hmac = hmac.HMAC(signing_key, message, hashlib.sha256)
    device_key_encoded = base64.b64encode(signed_hmac.digest())
    return device_key_encoded.decode("utf-8")


def provision_new_device_blocking(registration_id=None):
    """provision a new device

    This is a blocking function, called from the async wrapper below.

    azure.iot.device has an aio API,
    but it's proven to fail with fairly low concurrency

    Instead, we call this function in a background process

    To avoid resource issues, we spawn a new process
    for every call!
    """
    from azure.iot.device import ProvisioningDeviceClient

    # TODO: allow requesting keys for an existing id ?!
    if registration_id is None:
        registration_id = new_device_id()
    device_key = derive_device_key(registration_id, group_symmetric_key)
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=registration_id,
        id_scope=id_scope,
        symmetric_key=device_key,
    )

    result = provisioning_device_client.register()

    if result.status == "assigned":
        return (result.registration_state, device_key)
    else:
        raise ValueError("registration status was %s" % result.status)


async def provision_new_device(registration_id=None):
    """Provision a new device

    Calls blocking provisioning in a fresh subprocess every time
    (not a pool!) because there is evidence that
    the device provisioning code has issues with load/concurrency/stale state.

    Fresh process costs more, but ensures a clean slate for each invocation.
    """
    app_log.info(f"Registering device {registration_id}")
    with ProcessPoolExecutor(1) as pool:
        return await asyncio.wrap_future(
            pool.submit(provision_new_device_blocking, registration_id)
        )
