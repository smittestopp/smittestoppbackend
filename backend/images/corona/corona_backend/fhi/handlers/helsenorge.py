""" Handlers for serving requests by FHI. """

import datetime
import json

from tornado import web

from corona_backend import graph
from corona_backend.handlers import RevokeConsentSuccessMixin, revoke_and_delete
from corona_backend.utils import isoformat

from . import base


class HelseNorgeHandler(base.ExternalRequestsHandler):
    audit_fields = dict(
        organization="Norsk Helsenett", legal_means="Innsynsoppslag fra helsenorge.no",
    )

    def get_current_user(self):
        if not base.check_api_key(self):
            raise web.HTTPError(403)
        return graph.get_user_token(
            self, claims={"iss": "sikkerhet.helsenorge.no", "scp": "innsynsmittestopp"}
        )

    def validate_claims(self):
        for sub_claim in [
            "sub",
            "sub_given_name",
            "sub_middle_name",
            "sub_family_name",
        ]:
            if sub_claim not in self.current_user:
                raise web.HTTPError(400, f"Missing required token claim '{sub_claim}'")


class AccessLogHandler(HelseNorgeHandler):
    """Access the access log"""

    schema = {
        "page_number": (int, False),
        "per_page": (int, False),
    }

    @web.authenticated
    async def post(self):
        body = self.get_json_body(allow_empty=True) or {}
        phone_number = self.current_user["_phonenumber"]

        _ = await self.lookup_user(phone_number=phone_number)

        self.validate_claims()

        person_name = "{sub_given_name} {sub_middle_name} {sub_family_name}".format(
            **self.current_user
        )

        response = await base.response_from_access_log(
            person_id=self.current_user["sub"],
            phone_number=phone_number,
            person_name=person_name,
            organization=self.audit_fields["organization"],
            page_number=max(1, body.get("page_number", 1)),
            per_page=max(0, min(body.get("per_page", 30), 100)),
            caller="HN",
        )

        self.write(json.dumps(response))


class EgressHandler(HelseNorgeHandler):
    """Data egress of a single user"""

    schema = {
        "page_number": (int, False),
        "per_page": (int, False),
        "time_from": (datetime.datetime, False),
        "time_to": (datetime.datetime, False),
    }

    @web.authenticated
    async def post(self):
        body = self.get_json_body(allow_empty=True) or {}
        phone_number = self.current_user["_phonenumber"]
        user = await self.lookup_user(phone_number=phone_number)
        device_ids = await self.get_device_ids(user=user, phone_number=phone_number)

        self.validate_claims()

        await self.audit_log(
            phone_numbers=[phone_number],
            person_name="{sub_given_name} {sub_middle_name} {sub_family_name}".format(
                **self.current_user
            ),
            person_id=self.current_user["sub"],
            person_organization="",
        )

        response = await base.response_from_gps_events(
            device_ids=device_ids,
            phone_number=phone_number,
            page_number=max(1, body.get("page_number", 1)),
            per_page=max(0, min(body.get("per_page", 30), 100)),
            time_from=isoformat(body.get("time_from")),
            time_to=isoformat(body.get("time_to")),
            caller="HN",
        )

        self.write(json.dumps(response))


class RevokeConsentHandler(HelseNorgeHandler, RevokeConsentSuccessMixin):
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

    Similar to corona_backend.onboarding.app.RevokeConsentHandler but without
    test user functionality.
    """

    @web.authenticated
    async def post(self):
        phone_number = self.current_user["_phonenumber"]
        await revoke_and_delete(phone_number)
        self.write_success()
