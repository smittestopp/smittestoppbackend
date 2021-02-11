"""Common bases for application entrypoints (FHI and user backend)"""
import asyncio
import json
import os
import signal
from functools import partial
from http.client import responses

import tornado.ioloop
import tornado.options
from tornado import web
from tornado.httpserver import HTTPServer
from tornado.log import app_log
from tornado_prometheus import MetricsHandler, PrometheusMixIn

from corona_backend.utils import exponential_backoff, mask_phone

from . import graph, log


async def find_user(phone_number, timeout=3):
    """Lookup user by phone number"""
    masked_number = mask_phone(phone_number)
    try:
        user = await exponential_backoff(
            partial(graph.find_user_by_phone, phone_number),
            fail_message=f"Number not found: {masked_number}",
            timeout=timeout,
            start_wait=1,
        )
    except TimeoutError:
        raise web.HTTPError(400, f"No user found associated with {masked_number}")
    return user


class BaseHandler(web.RequestHandler):
    """Base handler for API endpoints"""

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")

    def write_error(self, status_code, **kwargs):
        """Write JSON errors instead of HTML"""
        exc_info = kwargs.get("exc_info")
        message = ""
        exception = None
        status_message = responses.get(status_code, "Unknown Error")
        if exc_info:
            exception = exc_info[1]
            # get the custom message, if defined
            try:
                message = exception.log_message % exception.args
            except Exception:
                pass

            # construct the custom reason, if defined
            reason = getattr(exception, "reason", "")
            if reason:
                status_message = reason

        self.set_header("Content-Type", "application/json")

        self.write(
            json.dumps({"status": status_code, "message": message or status_message})
        )


class B2CHandler(BaseHandler):
    """Handler for app endpoints that authenticates with B2C tokens"""

    def get_current_user(self):
        return graph.get_user_token(self)


async def revoke_and_delete(phone_number):
    masked_number = mask_phone(phone_number)
    user = await graph.find_user_by_phone(phone_number)
    if user is None:
        raise web.HTTPError(404, f"No user found associated with {masked_number}")

    # store consent-revoked marker on user
    await graph.store_consent_revoked(user)
    # delete devices from iothub so they won't be able to publish data anymore
    await graph.process_user_deletion(user)


class RevokeConsentSuccessMixin(object):
    def write_success(self):
        self.write(
            json.dumps(
                {
                    "Status": "Success",
                    "Message": (
                        "Your phone number is no longer associated with any data."
                        " The underlying anonymized data will be deleted shortly."
                    ),
                }
            )
        )


class HealthHandler(web.RequestHandler):
    # Don't log successful health checks
    log_success = False

    def get(self):
        # check health of this service
        self.write("ok")


class MeteredApplication(PrometheusMixIn, web.Application):
    pass


def stop_loop(*args):
    """signal handler for stopping the event loop

    called on SIGTERM
    """
    app_log.info("Shutting down...")
    loop = asyncio.get_event_loop()
    loop.call_soon_threadsafe(loop.stop)


def common_endpoints():
    """common endpoints for all apps"""
    return [
        ("/health", HealthHandler),
        ("/metrics", MetricsHandler),
    ]


def start_app(handlers, port, **settings):
    """Start an app, given handler list and port

    - adds health endpoint
    - starts event loop
    """

    signal.signal(signal.SIGTERM, stop_loop)
    tornado.options.parse_command_line()
    handlers = handlers + common_endpoints()
    app = MeteredApplication(handlers, log_function=log.log_request, **settings)

    ssl_cert = os.environ.get("SSL_CERT")
    ssl_key = os.environ.get("SSL_KEY")
    if ssl_cert or ssl_key:
        ssl_options = dict(certfile=ssl_cert, keyfile=ssl_key,)
        proto = "https"
    else:
        ssl_options = None
        proto = "http"

    app_log.info(f"Listening on {proto}://*:{port}")
    server = HTTPServer(app, ssl_options=ssl_options, xheaders=True)
    server.listen(port)
    tornado.ioloop.IOLoop.current().start()
