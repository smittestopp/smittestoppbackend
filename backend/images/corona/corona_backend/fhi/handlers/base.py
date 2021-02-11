"""Function and classes shared by the different handler modules"""

import datetime
import json
import os

import pyodbc
from dateutil.parser import parse as parse_date
from tornado import web
from tornado.log import app_log

from corona_backend import graph, sql, utils
from corona_backend.handlers import BaseHandler

API_KEY = os.environ["API_KEY"]


def check_api_key(handler, header_name="Api-Key"):
    """Check the API-Key header

    used to authenticate requests from the API Gateway

    Not Authorization, since tokens go there
    """

    auth_header = handler.request.headers.get(header_name)
    if auth_header is None:
        app_log.error(f"{header_name} header missing")
        return None
    if auth_header.strip() == API_KEY:
        return "api-gateway"

    app_log.error(f"API Key not recognized: {auth_header.strip()}")
    return None


type_map = {
    str: "text",
    int: "integer",
    list: "list",
    float: "number",
    datetime.datetime: "ISO8601 date string",
}


def make_sample_schema(schema):
    """Return a sample schema for nice error messages"""

    fields = []
    for field, field_type in schema.items():
        if isinstance(field_type, tuple):
            field_type, required = field_type
        else:
            required = True
        fields.append((field, type_map.get(field_type, field_type.__name__), required))
    return "{%s}" % (
        ", ".join(
            f"'{field}': {field_type_name} ({'required' if required else 'optional'})"
            for field, field_type_name, required in fields
        )
    )


async def response_from_access_log(
    person_id, phone_number, person_name, organization, page_number, per_page, caller
):
    app_log.info(
        f"Request from {caller}, retrieving access log for {utils.mask_phone(phone_number)} per_page={per_page}, page_no={page_number}"
    )

    events, total = await sql.get_access_log(
        phone_number=phone_number,
        person_name=person_name,
        person_id=person_id,
        person_organization="",
        organization=organization,
        page_number=page_number,
        per_page=per_page,
    )

    app_log.info(
        f"Request from {caller}, returning {len(events)} of {total} access events starting from {per_page * (page_number - 1)}"
    )

    response = {
        "phone_number": phone_number,
        "found_in_system": True,
        "events": events,
        "total": total,
        "per_page": per_page,
        "page_number": page_number,
    }
    if (page_number * per_page) < total:
        response["next"] = {
            "page_number": page_number + 1,
            "per_page": per_page,
        }

    return response


async def response_from_gps_events(
    device_ids, phone_number, page_number, per_page, time_from, time_to, caller
):
    app_log.info(
        f"Request from {caller}, retrieving gps events for {len(device_ids)} devices for {utils.mask_phone(phone_number)} from={time_from}, to={time_to}, per_page={per_page}, page_no={page_number}"
    )
    events, total = await sql.get_gps_events(
        device_ids=device_ids,
        page_number=page_number,
        per_page=per_page,
        time_from=time_from,
        time_to=time_to,
    )

    app_log.info(
        f"Request from {caller}, returning {len(events)} of {total} gps events starting from {per_page * (page_number - 1)}"
    )

    response = {
        "phone_number": phone_number,
        "found_in_system": True,
        "events": events,
        "total": total,
        "per_page": per_page,
        "page_number": page_number,
    }
    if (page_number * per_page) < total:
        response["next"] = next_params = {
            "page_number": page_number + 1,
            "per_page": per_page,
        }
        if time_from:
            next_params["time_from"] = time_from
        if time_to:
            next_params["time_to"] = time_to

    return response


class ExternalRequestsHandler(BaseHandler):
    audit_fields = dict()
    schema = {"phone_number": str}

    def prepare(self):
        super().prepare()

        for h in ("Certificate-Issuer", "Certificate-Name"):
            app_log.info(f"{h}: {self.request.headers.get(h)}")

        certificate_subject_name = self.request.headers.get("Certificate-Name")
        if not certificate_subject_name:
            app_log.warning("Missing Certificate-Name header")
            return
        subj = {}
        for key_value in certificate_subject_name.split(","):
            if "=" not in key_value:
                continue
            key, value = key_value.strip().split("=", 1)
            subj[key.strip()] = value.strip()

        if subj.get("O", "").lower().startswith("simula"):
            # simula cert is used for testing on dev
            self.audit_fields = dict(
                person_name="Administrator",
                person_id="",
                person_organization="Simula Research Laboratory",
                organization="Simula Research Laboratory",
                legal_means="Vedlikehold",
            )

    async def audit_log(
        self,
        phone_numbers,
        person_name=None,
        person_id=None,
        person_organization=None,
        organization=None,
        legal_means=None,
    ):
        """Store an entry in the audit log"""
        timestamp = utils.now_at_utc()

        if person_name is None:
            person_name = self.audit_fields["person_name"]
        if person_id is None:
            person_id = self.audit_fields["person_id"]
        if person_organization is None:
            person_organization = self.audit_fields["person_organization"]
        if organization is None:
            organization = self.audit_fields["organization"]
        if legal_means is None:
            legal_means = self.audit_fields["legal_means"]
        if not organization:
            raise ValueError("organization required!")
        if not legal_means:
            raise ValueError("legal_means required!")

        try:
            await sql.log_access(
                timestamp=timestamp,
                phone_numbers=phone_numbers,
                person_name=person_name,
                person_id=person_id,
                person_organization=person_organization,
                organization=organization,
                legal_means=legal_means,
            )
        except pyodbc.InterfaceError as e:
            app_log.exception("Connection error in sql.log_access")
            raise web.HTTPError(
                503, "Internal temporary server error - please try again"
            )

    def get_json_body(self, allow_empty=False):
        """Retrieve and validate a JSON request body"""
        try:
            return self._json_body
        except AttributeError:
            pass

        if allow_empty and not self.request.body:
            body = self._json_body = {}
            return body

        try:
            body = self._json_body = json.loads(
                self.request.body.decode("utf8", "replace")
            )
            if not isinstance(body, dict):
                raise ValueError("json body is not a dict")
        except ValueError:
            raise web.HTTPError(
                400,
                f"Request body must be a json dict of the form {make_sample_schema(self.schema)}",
            )

        schema = self.schema

        for field, field_type in schema.items():
            if isinstance(field_type, tuple):
                field_type, required = field_type
            else:
                required = True
            value = body.get(field)
            if value and field_type is datetime.datetime:
                try:
                    value = body[field] = parse_date(body[field])
                except Exception as e:
                    app_log.warning(f"Error parsing date: {body[field]}")

            if (field in body and not isinstance(value, field_type)) or (
                required and field not in body
            ):
                sample_schema = make_sample_schema(schema)
                raise web.HTTPError(
                    400,
                    f"Field {field} must be {type_map.get(field_type, field_type.__name__)}. A request body should look like: {sample_schema}",
                )

        return body

    async def lookup_user(self, phone_number):
        user = await graph.find_user_by_phone(phone_number)
        if user is None:
            self.set_status(404)
            self.write(
                json.dumps({"phone_number": phone_number, "found_in_system": False,})
            )
            raise web.Finish()
        return user

    async def get_device_ids(self, user, phone_number):
        device_ids = []
        async for device_id in graph.device_ids_for_user(user):
            device_ids.append(device_id)

        if not device_ids:
            # no devices, so we have no info to return
            # treat the same as not found at all
            self.set_status(404)
            self.write(
                json.dumps({"phone_number": phone_number, "found_in_system": False})
            )
            raise web.Finish()

        return device_ids
