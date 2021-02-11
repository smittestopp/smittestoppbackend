"""pytest configuration"""
import asyncio
import inspect

import pytest
from tornado import ioloop
from tornado.platform.asyncio import AsyncIOMainLoop


def pytest_collection_modifyitems(items):
    """add asyncio marker to all async tests"""
    for item in items:
        if inspect.iscoroutinefunction(item.obj):
            item.add_marker("asyncio")


@pytest.fixture
def io_loop(event_loop, request):
    """Make sure tornado io_loop is run on asyncio"""
    ioloop.IOLoop.configure(AsyncIOMainLoop)
    io_loop = AsyncIOMainLoop()
    io_loop.make_current()
    assert asyncio.get_event_loop() is event_loop
    assert io_loop.asyncio_loop is event_loop

    def _close():
        io_loop.clear_current()
        io_loop.close(all_fds=True)

    request.addfinalizer(_close)
    return io_loop