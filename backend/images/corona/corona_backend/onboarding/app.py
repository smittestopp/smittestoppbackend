#!/usr/bin/env python3
"""
Web entrypoint for backend services
"""

import asyncio
import json
import os
import time
from functools import partial

import pyodbc
import tornado.options
from opencensus.ext.azure import metrics_exporter
from tornado import web
from tornado.log import app_log

from corona_backend import devices, graph, handlers
from corona_backend import middleware as mw
from corona_backend import pin, sql
from corona_backend.graph import phone_number_for_device_id
from corona_backend.handlers import (
    B2CHandler,
    BaseHandler,
    RevokeConsentSuccessMixin,
    revoke_and_delete,
)
from corona_backend.test import create_test_user
from corona_backend.utils import exponential_backoff, mask_phone

TESTER_NUMBERS = set(os.environ.get("TESTER_NUMBERS", "").split(","))
PROVISIONING_TIMEOUT = int(os.environ.get("PROVISIONING_TIMEOUT") or "20")


class RegisterDeviceHandler(B2CHandler):
    async def find_user(self, phone_number, timeout=3):
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
            # is this 400? This shouldn't happen, so maybe it ought to be 500
            raise web.HTTPError(400, f"No user found associated with {masked_number}")
        return user

    @web.authenticated
    async def post(self):
        phone_number = self.current_user["_phonenumber"]

        is_test = False
        TESTER_NUMBERS = set(os.environ.get("TESTER_NUMBERS", "").split(","))
        if phone_number in TESTER_NUMBERS and self.request.headers.get("Test-Number"):
            is_test = True
            tester_number = phone_number
            phone_number = self.request.headers["Test-Number"]

        masked_number = mask_phone(phone_number)
        user = await handlers.find_user(phone_number)

        if is_test:
            if user.get(graph.extension_attr_name("testCredentials")):
                app_log.info(
                    f"Tester {tester_number} is impersonating test user {phone_number}"
                )
            else:
                app_log.error(
                    f"Tester {tester_number} attempted to impersonate non-test user {phone_number}"
                )
                raise web.HTTPError(403, f"{phone_number} is not a test user")

        # TODO: check and unset consent revocation on new registration
        if user.get(graph.extension_attr_name("consentRevoked")):
            consent_revoked_date = user.get(
                graph.extension_attr_name("consentRevokedDate")
            )
            app_log.warning(
                f"Phone number {masked_number} had previously revoked consent on {consent_revoked_date}."
                " Resetting for new device registration."
            )
            await graph.reset_consent(user)

        existing_device_id = user.get(graph.extension_attr_name("deviceId"))
        if existing_device_id:
            app_log.warning(
                f"Phone number {masked_number} is already associated with device id {existing_device_id}. Registering new device."
            )

        device_future = asyncio.ensure_future(devices.create_new_device())
        tic = time.perf_counter()
        try:
            await asyncio.wait_for(device_future, timeout=PROVISIONING_TIMEOUT)
        except asyncio.TimeoutError:
            self.settings["consecutive_failures"] += 1
            app_log.error(
                "Timeout registering device ({consecutive_failures}/{consecutive_failure_limit} before abort)".format(
                    **self.settings
                )
            )
            if (
                self.settings["consecutive_failures"]
                >= self.settings["consecutive_failure_limit"]
            ):
                app_log.critical("Aborting due to consecutive failure limit!")
                loop = asyncio.get_event_loop()
                loop.call_later(2, loop.stop)
            raise web.HTTPError(500, "Timeout registering device")
        else:
            self.settings["consecutive_failures"] = 0
            toc = time.perf_counter()
            app_log.info(f"Registered device in {int(1000 * (toc-tic))}ms")
        device = await device_future
        device_id = device["deviceId"]
        device_key = device["authentication"]["symmetricKey"]["primaryKey"]
        iothub_hostname = devices.iothub_hostname

        # store device id on user in AD
        try:
            await graph.store_device_id(user, device_id)
        except Exception:
            # failed to associated user with device
            # delete the device from IoTHub since nobody is going to use it
            await devices.delete_devices(device_id)
            raise

        self.write(
            json.dumps(
                {
                    "DeviceId": device_id,
                    "PhoneNumber": phone_number,
                    "HostName": iothub_hostname,
                    "SharedAccessKey": device_key,
                    "ConnectionString": ";".join(
                        [
                            f"HostName={iothub_hostname}",
                            f"DeviceId={device_id}",
                            f"SharedAccessKey={device_key}",
                        ]
                    ),
                }
            )
        )


class RevokeConsentHandler(B2CHandler, RevokeConsentSuccessMixin):
    """
    POST /permissions/revoke-consent

    RESPONSE: application/json
    {
        "status": "Success",
        "message": "..."
    }

    Immediately:

    - dissociate phone number from device ids
    - mark device ids for deletion by deletion service

    """

    @web.authenticated
    async def post(self):
        phone_number = self.current_user["_phonenumber"]

        TESTER_NUMBERS = set(os.environ.get("TESTER_NUMBERS", "").split(","))
        is_test = False
        if phone_number in TESTER_NUMBERS and self.request.headers.get("Test-Number"):
            is_test = True
            phone_number = self.request.headers["Test-Number"]

        await revoke_and_delete(phone_number)

        if is_test:
            # recreate test users after deletion
            await create_test_user(phone_number)

        self.write_success()


class PinHandler(BaseHandler):
    """ Retrieve pin codes for a given device id

    All text messages sent from FHI should include a pin code and the
    respective pin code(s) should be visible for the end user in the app.
    """

    @mw.hmac_authentication
    async def get(self):
        device_id = self.current_user
        phone_number = await phone_number_for_device_id(device_id=device_id)
        if phone_number:
            pin_codes = await pin.get_pin_codes(phone_number=phone_number)
            self.write(json.dumps({"pin_codes": pin_codes}))
        else:
            raise web.HTTPError(
                404, "No phone number matched to the device",
            )


class ContactIdsHandler(BaseHandler):
    """Allocate and retrieve new bluetooth contact ids"""

    @mw.hmac_authentication
    async def post(self):
        device_id = self.current_user
        contact_ids = await sql.request_contact_ids(device_id)
        self.write(json.dumps({"contact_ids": contact_ids}))


class BirthYearHandler(BaseHandler):
    """Associate a device with a birth year

    If the user of the device has more devices,
    associate them accordingly.
    """

    @mw.hmac_authentication
    async def post(self):
        data = json.loads(self.request.body)
        birth_year = data["birthyear"]

        user = await graph.user_for_device(self.current_user)

        values = []
        async for device_id in graph.device_ids_for_user(user):
            values.append((device_id, birth_year))

        try:
            await sql.upsert_birth_year(values=values)
        except pyodbc.InterfaceError as e:
            app_log.exception(f"Connection error in app.BirthYearHandler.post: {e}")
            raise web.HTTPError(
                503, "Internal temporary server error - please try again"
            )


def endpoints():
    """Return the handlers list for the onboarding service"""
    handlers = [
        ("/register-device", RegisterDeviceHandler),
        ("/revoke-consent", RevokeConsentHandler),
        ("/contactids", ContactIdsHandler),
        ("/birthyear", BirthYearHandler),
    ]
    if pin.PIN_ENABLED:
        handlers.append(("/pin", PinHandler))
    return handlers


def main(port):
    tornado.options.parse_command_line()
    loop = tornado.ioloop.IOLoop.current()

    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        _exporter = metrics_exporter.new_metrics_exporter()
        app_log.info("Metric exporter started.")

    # initialize AD extension attributes
    loop.run_sync(graph.ensure_custom_attrs_exist)
    graph.keep_jwt_keys_updated()
    handlers.start_app(
        endpoints(),
        port,
        consecutive_failures=0,
        consecutive_failure_limit=int(os.environ.get("CONSECUTIVE_FAILURE_LIMIT", "3")),
        xheaders=True,
    )


if __name__ == "__main__":
    main(int(os.environ.get("PORT", "8080")))
