"""HMAC authentication middleware"""
import base64
import functools
import hmac
import os
import time
from urllib.parse import urlparse

from tornado import web
from tornado.log import app_log

from corona_backend import devices

AUTH_SCHEME = "SMST-HMAC-SHA256"
TIMESTAMP_WINDOW = int(os.environ.get("TIMESTAMP_WINDOW", 5400))


def create_signature(key, device_id, scope, timestamp):
    """Create a signature for a key, device id, and timestamp"""
    msg = f"{device_id}|{timestamp}|{scope}".encode("utf8")
    digest = hmac.new(key, msg, "sha256").digest()
    return digest


def create_signature_base64(key, device_id, timestamp, scope):
    """Create a base64-encoded signature"""
    digest = create_signature(
        key, device_id=device_id, timestamp=timestamp, scope=scope
    )
    return base64.b64encode(digest).decode("ascii")


def create_auth_header(key, device_id, path, method="GET", timestamp=None):
    """Create the Authorization header for a given request"""
    if timestamp is None:
        timestamp = str(int(time.time()))
    b64_digest = create_signature_base64(
        key=key,
        device_id=device_id,
        scope=f"{method.upper()}|{path}",
        timestamp=timestamp,
    )
    return f"{AUTH_SCHEME} {device_id};{timestamp};{b64_digest}"


def add_auth_header(request, key, device_id, timestamp=None):
    """Add Authorization header to an HTTPRequest object"""
    request.headers["Authorization"] = create_auth_header(
        key=key,
        device_id=device_id,
        method=request.method.upper(),
        path=urlparse(request.url).path,
        timestamp=timestamp,
    )


def check_signature(signature, key, device_id, timestamp, scope):
    """Check a signature, given a key, device id, and timestamp"""
    if isinstance(signature, str):
        # str is base64-encoded
        try:
            signature = base64.b64decode(signature)
        except ValueError:
            return False

    expected_signature = create_signature(
        key=key, device_id=device_id, timestamp=timestamp, scope=scope
    )
    return hmac.compare_digest(signature, expected_signature)


def check_timestamp(timestamp_str, window=TIMESTAMP_WINDOW):
    """Return whether a timestamp is within the"""
    try:
        timestamp = int(timestamp_str)
    except ValueError:
        return False
    now = time.time()
    return now - window < timestamp < now + window


async def check_hmac_auth(b64_digest, timestamp_str, device_id, scope):
    """Validate HMAC authentication for a given device id and timestamp"""

    try:
        timestamp = int(timestamp_str)
    except ValueError:
        raise web.HTTPError(
            400, f"Invalid timestamp: {timestamp_str}, expected unix timestamp"
        )

    if not check_timestamp(timestamp, window=TIMESTAMP_WINDOW):
        raise web.HTTPError(400, f"Timestamp {timestamp_str} out of bounds")

    # At this point the request parameters have been validated but authorization remains.
    # Any error should be considered a potential break in attempt.
    # Thus only 403 should be returned to the caller without any descriptive error message.

    keys = await devices.lookup_device_keys(device_id)
    if keys is None:
        app_log.warning(f"Invalid device id: {device_id}")
        raise web.HTTPError(403)

    try:
        app_digest = base64.b64decode(b64_digest)
    except ValueError:
        app_log.warning(f"Invalid base64 digest: {b64_digest}")
        raise web.HTTPError(403)

    # Accepting signatures signed with either the primary or secondary key.
    digests_are_equal = False
    for b64key in keys.values():
        key = base64.b64decode(b64key)
        if check_signature(
            signature=app_digest,
            key=key,
            device_id=device_id,
            timestamp=timestamp_str,
            scope=scope,
        ):
            break
    else:
        app_log.warning("Signature does not match")
        raise web.HTTPError(403)


def hmac_authentication(method):
    """Decorator for HMAC authentication

    HMAC signature is stored in the Authorization header,
    with auth type `SMST-HMAC-SHA256`

    Auth header should look like:

    Authorization: SMST-HMAC-SHA256 deviceId;timestamp;b64digest

    and the b64digest should be a hash of: "device_id|timestamp_str|HTTP VERB|/urlpath"
    The hash should be signed with iot hub device key corresponding to the given device_id.
    """

    @functools.wraps(method)
    async def wraps(self, *args, **kwargs):
        auth_header = self.request.headers.get("Authorization")
        if not auth_header:
            raise web.HTTPError(401)

        try:
            scheme, auth_value = auth_header.split(None, 1)
        except ValueError:
            app_log.warning(f"Malformed auth header: {auth_header[:10]}...")
            raise web.HTTPError(403)

        if scheme.lower() != "smst-hmac-sha256":
            app_log.warning(f"Unrecognized auth scheme: {scheme}")
            raise web.HTTPError(403)

        # parse auth fields, of the form deviceId;timestamp;digest
        # use partition, which always succeeds
        device_id, _, rest = auth_value.partition(";")
        timestamp_str, _, b64_digest = rest.partition(";")

        if not device_id or not timestamp_str or not b64_digest:
            app_log.warning(f"Malformed auth header: {scheme} {auth_value[:10]}...")
            raise web.HTTPError(403, "Malformed authorization header")

        await check_hmac_auth(
            b64_digest=b64_digest,
            timestamp_str=timestamp_str,
            device_id=device_id,
            scope=f"{self.request.method.upper()}|{self.request.path}",
        )
        self.current_user = device_id

        return await method(self, *args, **kwargs)

    return wraps
