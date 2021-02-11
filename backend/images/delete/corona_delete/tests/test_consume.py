import asyncio
import inspect
import logging
from collections import defaultdict

from corona_delete.delete import consume_concurrently


def pytest_collection_modifyitems(items):
    """add asyncio marker to all async tests"""
    for item in items:
        if inspect.iscoroutinefunction(item.obj):
            item.add_marker("asyncio")


async def produce_fast(n):
    for i in range(n):
        await asyncio.sleep(0)
        print(f"producing {i}")
        yield i


async def consume_slow(item, time_per_item=0.1):
    print(f"consuming {item}")
    await asyncio.sleep(time_per_item)
    return item


async def test_concurrent_consume(caplog):
    caplog.set_level(logging.INFO)
    counts = defaultdict(int)
    async for item in consume_concurrently(
        produce_fast(64), process_one=consume_slow, concurrency=4, counts=counts,
    ):
        # test readahead fraction (3x concurrency)
        assert counts["todo"] < 16

    for record in caplog.records:
        assert record.levelno < logging.ERROR

    assert "complete" in caplog.records[-1].message
