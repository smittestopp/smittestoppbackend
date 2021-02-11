import asyncio
import uuid
from typing import Any, Dict

import pytest
from tornado.httpclient import HTTPError

from corona_backend import devices

DEVICE_KEYS = ["deviceId", "etag", "generationId"]
DEVICE_ATTRS = ["device_id", "etag", "generation_id"]


def compare_device(retrieved_device: Dict[str, Any], device: Dict[str, Any]) -> None:
    for key in DEVICE_KEYS:
        assert key in retrieved_device
        assert retrieved_device.get(key) == device.get(key)


def test_new_device_id() -> None:

    device_id = devices.new_device_id()
    assert isinstance(device_id, str)
    assert len(device_id) == 32


def test_new_device_secret() -> None:
    device_secret = devices.new_device_secret()
    assert isinstance(device_secret, str)
    assert len(device_secret) == 44


async def test_get_device(device: Dict[str, Any]) -> None:

    # retrieved_device = devices.get_device(device_id)
    d1 = await devices.get_device(device["deviceId"])
    compare_device(d1, device)


async def test_get_devices_one(device):

    # The difference between get_device and get_devices is that
    # get_devices returns a twin and also queries the database.
    # This makes testing difficult since the time of the query
    # depends on connection. In stead we just check that the correct
    # query string is passed
    for i in range(30):
        found_devices = await get_devices(device["deviceId"])
        # it can take a while to register, so try a few times
        if not found_devices:
            await asyncio.sleep(1)
    assert len(found_devices) == 1
    assert found_devices[0]["deviceId"] == device["deviceId"]


async def test_get_devices_limit():
    # use per_page < limit to ensure continuation is tested
    found_devices = await get_devices(per_page=10, limit=100)
    # note: 100 will only work if the iothub is active,
    # but this is generally the case
    assert len(found_devices) == 100
    # make sure that they are probably devices
    assert all(d["deviceId"] for d in found_devices)


async def test_get_device_when_device_does_not_exist():

    device_id = uuid.uuid1()
    with pytest.raises(HTTPError):
        await devices.get_device(device_id)

    retrieved_devices = await get_devices(device_id)
    assert len(retrieved_devices) == 0


async def test_create_and_delete_device():

    device = await devices.create_new_device()
    assert device["status"] == "enabled"
    device_id = device.get("deviceId")

    retrieved_device = await devices.get_device(device_id)

    # Check similar attributes
    compare_device(retrieved_device, device)

    await devices.delete_devices(device_id)

    # We should get an error because this device does not exist anymore
    with pytest.raises(HTTPError) as e:
        await devices.get_device(device_id)
    assert e.value.code == 404


async def get_devices(*device_ids, **kwargs):
    """Helper function for get devies that returns
    a list in stead of a generator.
    """
    items = []
    async for device in devices.get_devices(*device_ids, **kwargs):
        items.append(device)
    return items


async def test_iothub_request_get(device):

    device_id = device.get("deviceId")
    retrieved_device = await devices.iothub_request(
        f"/devices/{device_id}", method="GET"
    )
    for k in DEVICE_KEYS:
        assert device[k] == retrieved_device[k]
