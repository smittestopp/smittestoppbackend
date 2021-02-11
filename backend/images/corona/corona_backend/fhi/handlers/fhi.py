""" Handlers for serving requests by FHI. """

import datetime
import json
import os
import uuid
from functools import lru_cache

import pyodbc
import redis
from dateutil.parser import parse as parse_date
from tornado import web
from tornado.log import app_log

from corona_backend import devices, graph, handlers, pin, sql, utils

from .base import (
    ExternalRequestsHandler,
    check_api_key,
    response_from_access_log,
    response_from_gps_events,
)

LOOKUP_RESULT_EXPIRY = int(os.environ.get("LOOKUP_RESULT_EXPIRY") or 4 * 60 * 60)
REDIS_HOST = os.environ.get("REDIS_SERVICE_HOST", "localhost")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")
REDIS_JOBQUEUE_NAME = os.getenv("REDIS_JOBQUEUE_NAME", "analysis-jobs")
# result-fetch expiry (default: 4 hours)
LOOKUP_RESULT_EXPIRY = int(os.environ.get("LOOKUP_RESULT_EXPIRY") or 4 * 60 * 60)


@lru_cache()
def get_redis():
    """Caching getter for redis client"""
    return redis.StrictRedis(host=REDIS_HOST, password=REDIS_PASSWORD)


class FHIHandler(ExternalRequestsHandler):
    audit_fields = dict(
        person_name="Varslingsystem",
        person_id="",
        person_organization="Folkehelseinstituttet",
        organization="Folkehelseinstituttet",
        legal_means="Oppslag i nærkontakter for varsling",
    )

    def get_current_user(self):
        return check_api_key(self)


class LookupHandler(FHIHandler):
    schema = {
        "phone_number": str,
        "time_from": (datetime.datetime, False),
        "time_to": (datetime.datetime, False),
    }

    @web.authenticated
    async def post(self):
        body = self.get_json_body()
        phone_number = body["phone_number"]
        user = await self.lookup_user(phone_number)

        await self.audit_log(phone_numbers=[phone_number])

        phone_number = user["displayName"]
        mask_number = user["logName"]

        device_ids = []

        request_id = str(uuid.uuid4())
        app_log.info(f"Submitting analysis jobs for {mask_number}: {request_id}")
        request_info = f"lookup:{request_id}:info"
        # create job queue in redis

        db = get_redis()
        result_keys = []

        async for device_id in graph.device_ids_for_user(user):
            device_ids.append(device_id)
            result_key = f"lookup:{request_id}:result:{device_id}"
            result_keys.append(result_key)
            app_log.info(f"Submitting analysis job for {device_id}")
            job = {
                "request_id": request_id,
                "device_id": device_id,
                "result_key": result_key,
                "time_from": utils.isoformat(body.get("time_from")),
                "time_to": utils.isoformat(body.get("time_to")),
                "expiry": LOOKUP_RESULT_EXPIRY,
            }
            db.rpush(REDIS_JOBQUEUE_NAME, json.dumps(job).encode("utf8"))
            # push device id onto job queue
        if not device_ids:
            app_log.info(f"Phone number {mask_number} has no devices")
            self.set_status(404)
            self.write(
                json.dumps({"phone_number": phone_number, "found_in_system": False})
            )
            return

        app_log.info(f"Storing request info for {request_id}")
        db.set(
            request_info,
            json.dumps(
                {
                    "phone_number": phone_number,
                    "result_keys": result_keys,
                    "device_ids": device_ids,
                }
            ),
            ex=LOOKUP_RESULT_EXPIRY,
        )

        self.set_status(202)
        self.write(
            json.dumps(
                {
                    "request_id": request_id,
                    # todo: figure out how to get this right?
                    # /fhi/ prefix isn't available from APIM
                    # but it's wrong when not behind APIM
                    "result_url": f"https://{self.request.host}/fhi/lookup/{request_id}",
                    "result_expires": utils.isoformat(
                        utils.now_at_utc()
                        + datetime.timedelta(seconds=LOOKUP_RESULT_EXPIRY)
                    ),
                }
            )
        )


async def fetch_pin(phone_number):
    try:
        pin_code = await pin.fetch_or_generate_pin(phone_number=phone_number)
    except pyodbc.InterfaceError:
        app_log.exception("Connection error in pin.fetch_or_generate_pin")
        raise web.HTTPError(503, "Internal temporary server error - please try again")
    return pin_code


class LookupResultHandler(FHIHandler):
    @web.authenticated
    async def get(self, request_id):
        app_log.info(f"Looking up result for {request_id}")
        request_info = f"lookup:{request_id}:info"
        db = get_redis()
        item = db.get(request_info)
        if not item:
            raise web.HTTPError(404, "No such request")

        info = json.loads(item.decode("utf8"))
        device_ids = info["device_ids"]
        phone_number = info["phone_number"]

        # TODO: is it worth logging retrieval in audit log separately request?
        # without separate auth, this isn't useful
        mask_number = utils.mask_phone(phone_number)
        result_keys = info["result_keys"]
        num_ready = db.exists(*result_keys)
        progress = f"{num_ready}/{len(result_keys)}"
        if num_ready < len(info["result_keys"]):
            app_log.info(f"Lookup request {request_id} not ready yet: {progress}")
            self.set_status(202)
            self.write(
                json.dumps(
                    {"message": f"Not finished processing (completed {progress} tasks)"}
                )
            )
            return

        app_log.info(f"Lookup request {request_id} complete: {progress}")

        # we are done! Collect and return the report
        results = [json.loads(item.decode("utf8")) for item in db.mget(*result_keys)]
        contacts = []

        for result in results:
            if result["status"] != "success":
                app_log.error(
                    f"Error processing {result['device_id']}: {result['message']}"
                )
                raise web.HTTPError(
                    500,
                    "Error in analysis pipeline. Please report the input parameters to the analysis team.",
                )
            if not result["result"]:
                app_log.info(f"Empty result for {result['device_id']}")
                continue
            device_result = result["result"]
            contact = {}
            for device_id, contact_info in device_result.items():
                contact_number = await graph.phone_number_for_device_id(device_id)
                if contact_number:
                    if contact_number == phone_number:
                        app_log.warning(f"Omitting contact with self for {mask_number}")
                    else:
                        await self.audit_log(phone_numbers=[contact_number])
                        if pin.PIN_ENABLED:
                            pin_code = await fetch_pin(phone_number=contact_number)
                            contact_info["pin_code"] = pin_code
                        contact[contact_number] = contact_info
                else:
                    app_log.warning(
                        f"Omitting contact for {device_id} with no phone number"
                    )
            if contact:
                contacts.append(contact)

        app_log.info(f"Checking {len(device_ids)} devices for activity")
        last_activity = None
        for device_id in device_ids:
            # use get_device here, not get_devices
            # because get_devices doesn't report last activity accurately
            try:
                device = await devices.get_device(device_id)
            except Exception as e:
                if "not found" in str(e).lower():
                    app_log.warning(f"Device {device_id} not in IoTHub")
                    continue
                else:
                    raise
            device_last_activity = parse_date(device["lastActivityTime"])
            if device_last_activity < devices.before_times:
                app_log.info(f"Device {device['deviceId']} appears to have no activity")
                continue
            if last_activity is None or device_last_activity >= last_activity:
                last_activity = device_last_activity

        self.write(
            json.dumps(
                {
                    "phone_number": phone_number,
                    "found_in_system": True,
                    "last_activity": utils.isoformat(last_activity),
                    "contacts": contacts,
                }
            )
        )


class FHIAccessLogHandler(FHIHandler):
    """Access the access log

    FHI calls this endpoint on behalf of a user.
    """

    schema = {
        "phone_number": (str, True),
        "person_name": (str, True),
        "person_id": (str, False),
        "page_number": (int, False),
        "per_page": (int, False),
        "time_from": (datetime.datetime, False),
        "time_to": (datetime.datetime, False),
    }

    @web.authenticated
    async def post(self):
        body = self.get_json_body()
        phone_number = body.get("phone_number")

        _ = await self.lookup_user(phone_number=phone_number)

        response = await response_from_access_log(
            person_id=body.get("person_id", ""),
            phone_number=body.get("phone_number"),
            person_name=body.get("person_name"),
            organization=self.audit_fields["organization"],
            page_number=max(1, body.get("page_number", 1)),
            per_page=max(0, min(body.get("per_page", 30), 100)),
            caller="FHI",
        )

        self.write(json.dumps(response))


class FHIEgressHandler(FHIHandler):
    """Data egress of a single user

    FHI calls this endpoint on behalf of a user.
    """

    schema = {
        "phone_number": (str, True),
        "person_name": (str, True),
        "person_id": (str, False),
        "person_organization": (str, False),
        "legal_means": (str, True),
        "page_number": (int, False),
        "per_page": (int, False),
        "time_from": (datetime.datetime, False),
        "time_to": (datetime.datetime, False),
    }

    @web.authenticated
    async def post(self):
        body = self.get_json_body()
        phone_number = body.get("phone_number")
        person_name = body.get("person_name")
        legal_means = body.get("legal_means")
        bad_fields = []
        if person_name == "" or person_name is None:
            bad_fields.append("person_name")
        if legal_means == "" or legal_means is None:
            bad_fields.append("legal_means")
        if len(bad_fields) > 0:
            raise web.HTTPError(
                400, "Field(s): {} must be non-empty".format(", ".join(bad_fields))
            )

        user = await self.lookup_user(phone_number=phone_number)
        device_ids = await self.get_device_ids(user=user, phone_number=phone_number)

        await self.audit_log(
            phone_numbers=[phone_number],
            person_name=body.get("person_name"),
            legal_means=body.get("legal_means"),
        )

        response = await response_from_gps_events(
            device_ids=device_ids,
            phone_number=phone_number,
            page_number=max(1, body.get("page_number", 1)),
            per_page=max(0, min(body.get("per_page", 30), 100)),
            time_from=utils.isoformat(body.get("time_from")),
            time_to=utils.isoformat(body.get("time_to")),
            caller="FHI",
        )

        self.write(json.dumps(response))


class DeletionsHandler(FHIHandler):
    """Extract numbers that have been deleted"""

    schema = {
        "phone_numbers": list,
    }

    @web.authenticated
    async def post(self):
        body = self.get_json_body()
        numbers = body["phone_numbers"]

        app_log.info(f"Checking {len(numbers)} potentially deleted phone numbers")

        deleted_numbers = await graph.extract_deleted_numbers(numbers)

        await self.audit_log(
            phone_numbers=numbers,
            legal_means="Oppslag – har brukeren bedt om sletting av data?",
        )

        app_log.info(
            f"Found {len(deleted_numbers)} deleted numbers out of {len(numbers)}"
        )

        response = {
            "deleted_phone_numbers": deleted_numbers,
        }

        self.write(json.dumps(response))


class BirthYearHandler(FHIHandler):
    """Get the birth year of a user"""

    @web.authenticated
    async def get(self, phone_number):
        user = await handlers.find_user(phone_number=phone_number)

        device_id = None
        # We pick the first because it should be the same for
        # all devices associated with the user.
        async for _device_id in graph.device_ids_for_user(user):
            device_id = _device_id
            break

        if device_id is None:
            raise web.HTTPError(400, "No devices found")

        birth_year = await sql.get_birth_year(device_id=device_id)
        response = {"birthyear": birth_year}

        self.write(json.dumps(response))
