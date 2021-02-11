import json

from tornado import web

from corona_backend import middleware as mw
from corona_backend.graph import phone_number_for_device_id
from corona_backend.handlers import BaseHandler
from corona_backend.pin import get_pin_codes


class PinHandler(BaseHandler):
    """ Retrieve pin codes for a given device id

    All text messages sent from FHI should include a pin code and the
    respective pin code(s) should be visible for the end user in the app.
    """

    @mw.hmac_authentication
    async def get(self):
        device_id = self.request.headers["SMST-ID"]
        phone_number = await phone_number_for_device_id(device_id=device_id)
        if phone_number:
            pin_codes = await get_pin_codes(phone_number=phone_number)
            self.write(json.dumps({"pin_codes": pin_codes}))
        else:
            raise web.HTTPError(
                404, "No phone number matched to the device",
            )
