#!/usr/bin/env python3
"""
Microsoft graph / Active Directory API calls
"""

import asyncio
import datetime
import json
import os
import time
from functools import lru_cache, partial
from urllib.parse import urlencode

import jwt
from tornado import ioloop, web
from tornado.httpclient import HTTPClientError, HTTPRequest
from tornado.httputil import url_concat
from tornado.log import app_log

from .utils import fetch, mask_phone

# AAD-related
tenant_id = os.environ["AAD_TENANT_ID"]
tenant_name = os.environ.get("AAD_TENANT_NAME") or "devsmittestopp"
client_id = os.environ["AAD_CLIENT_ID"]
client_secret = os.environ["AAD_CLIENT_SECRET"]
policy_name = os.environ.get("AAD_POLICY_NAME") or "b2c_1a_phone_susi"
scope = os.environ.get("AAD_SCOPE") or "Device.Write"
audience = os.environ.get("JWT_AUDIENCE") or client_id

# name of custom fields in AD
custom_attributes = [
    {"name": "deviceId", "dataType": "String", "targetObjects": ["User"]},
    {"name": "consentRevoked", "dataType": "Boolean", "targetObjects": ["User"]},
    {"name": "consentRevokedDate", "dataType": "DateTime", "targetObjects": ["User"]},
    {"name": "dataRequested", "dataType": "Boolean", "targetObjects": ["User"]},
    {"name": "dataRequestedDate", "dataType": "DateTime", "targetObjects": ["User"]},
    {"name": "testCredentials", "dataType": "Boolean", "targetObjects": ["User"]},
    {"name": "toDelete", "dataType": "Boolean", "targetObjects": ["Group"]},
    {"name": "toDeleteDate", "dataType": "DateTime", "targetObjects": ["Group"]},
    {"name": "iotDeletedDate", "dataType": "DateTime", "targetObjects": ["Group"]},
    {"name": "sqlDeletedDate", "dataType": "DateTime", "targetObjects": ["Group"]},
    {"name": "lakeDeletedDate", "dataType": "DateTime", "targetObjects": ["Group"]},
]

PHONE_NUMBER_BLACKLIST_FILE = os.environ.get(
    "PHONE_NUMBER_BLACKLIST_FILE", "/etc/corona/blacklist.json"
)


@lru_cache()
def get_blacklist(path=PHONE_NUMBER_BLACKLIST_FILE):
    """Cached read of the phone number blacklist file, if it exists"""
    blacklist = set()
    if os.path.isfile(path):
        app_log.info(f"Loading blacklist from {path}")
        with open(path) as f:
            blacklist = set(json.load(f))
        app_log.info(f"Loaded {len(blacklist)} blacklisted numbers")
    else:
        app_log.info(f"No blacklist found in {path}")

    return blacklist


@lru_cache()
def extension_attr_name(attr_name):
    """Return the app-owned extension attribute name

    creating an attribute "deviceId" *actually* creates
    an attribute extension_$clientid_deviceId.
    """
    return "extension_{}_{}".format(client_id.replace("-", ""), attr_name)


# url for updating the public keys used to sign json web tokens
jwks_url = os.environ.get(
    "JWKS_URL",
    f"https://{tenant_name}.b2clogin.com/{tenant_name}.onmicrosoft.com/discovery/v2.0/keys?p={policy_name}",
)

jwks_file = os.environ.get("JWKS_FILE", "/etc/corona/jwks.json")


_PUBLIC_KEYS = {}


async def update_jwt_keys(public_keys=None):
    """update jwt public keys from jwks url"""
    if public_keys is None:
        public_keys = {}
    if os.path.isfile(jwks_file):
        app_log.info(f"Loading jwt keys from {jwks_file}")
        with open(jwks_file) as f:
            jwks = json.load(f)
    else:
        app_log.info(f"Loading jwt keys from {jwks_url}")
        resp = await fetch(jwks_url)
        jwks = json.loads(resp.body.decode("utf8", "replace"))

    old_kids = set(public_keys)
    new_kids = set()
    for jwk in jwks["keys"]:
        kid = jwk["kid"]
        new_kids.add(kid)
        if kid in old_kids:
            # already have this key
            continue
        else:
            app_log.info(f"Loading new public key {kid}")
            # load new public key
            public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
    # drop old keys no longer in list
    for old_kid in old_kids.difference(new_kids):
        app_log.info(f"Dropping old public key {old_kid}")
        public_keys.pop(old_kid)
    return public_keys


def keep_jwt_keys_updated(interval_seconds=3600, run_first=True):
    """keep public keys up-to-date

    If run_first (default): load initial value before scheduling update
    """
    if run_first:
        # initialize public keys
        ioloop.IOLoop.current().run_sync(partial(update_jwt_keys, _PUBLIC_KEYS))
    # update jwt keys every hour (callback_time is in milliseconds)
    pc = ioloop.PeriodicCallback(
        lambda: update_jwt_keys(_PUBLIC_KEYS), callback_time=1000 * interval_seconds
    )
    pc.start()
    return pc


_token_cache = {}

_expiry_buffer = 600  # number of seconds before expiry to request a new token


async def request_graph_token(
    tenant_id,
    client_id,
    client_secret,
    scope="https://graph.microsoft.com/.default",
    clear_cache=False,
):
    """Request an access token for the ms graph API

    Cache the result to re-use tokens until they are close to expiring
    """
    cache_key = (tenant_id, client_id, scope)

    if clear_cache:
        _token_cache.pop(cache_key, None)

    cached = _token_cache.get(cache_key)
    if cached:
        expiry = cached["expiry"]
        # don't re-use tokens that are within 10 minutes of expiring
        seconds_remaining = expiry - time.time()
        if seconds_remaining >= _expiry_buffer:
            app_log.debug("Reusing cached token")
            return cached["token"]
        else:
            app_log.info(
                f"Cached token for {cache_key} is expiring in {int(seconds_remaining)}s, not using it"
            )
            _token_cache.pop(cache_key, None)

    app_log.info(f"Requesting new token for {scope}")
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    body_data = dict(
        client_id=client_id,
        client_secret=client_secret,
        grant_type="client_credentials",
        scope=scope,
    )

    req = HTTPRequest(
        method="POST",
        url=token_url,
        body=urlencode(body_data),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp = await fetch(req)
    resp_json = json.loads(resp.body.decode("utf-8"))
    token = resp_json["access_token"]
    payload = jwt.decode(token, verify=False)

    # store in expiring cache
    _token_cache[cache_key] = {"token": token, "expiry": payload["exp"]}
    seconds = payload["exp"] - time.time() - _expiry_buffer
    app_log.info(f"Token acquired, using for {seconds:.0f} seconds")
    return token


async def graph_request(
    path, *, params=None, body=None, method="GET", headers=None, unpack_value=True
):
    """Make a request to the graph API

    Returns the parsed json response if there was one
    """
    token = await request_graph_token(tenant_id, client_id, client_secret)
    if "://" in path:
        # full url, e.g. nextLink
        url = path
    else:
        url = f"https://graph.microsoft.com/v1.0{path}"
        if params:
            url = url_concat(url, params)
    req_headers = {"Authorization": f"Bearer {token}"}
    if body:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)

    req = HTTPRequest(url, method=method, body=body, headers=req_headers)
    resp = await fetch(req)
    if not resp.body:
        return
    resp_text = resp.body.decode("utf-8", "replace")
    try:
        resp_content = json.loads(resp_text)
    except ValueError:
        # not json, return text
        return resp_text

    if unpack_value and "value" in resp_content:
        return resp_content["value"]
    else:
        return resp_content


async def paged_graph_request(path, **kwargs):
    """Handle pagination in graph results (e.g. full user lists)"""
    params = kwargs.setdefault("params", {})
    kwargs["unpack_value"] = False
    next_url = path
    while next_url:
        resp = await graph_request(next_url, **kwargs)
        next_url = resp.get("@odata.nextLink")
        for item in resp["value"]:
            yield item


async def ensure_custom_attrs_exist():
    """First-run function to ensure our extension attributes are defined

    First, checks for its existence.
    If it doesn't exist, create it.
    """
    # get the application *object* id, given our application id (not the same)
    application = (
        await graph_request(
            "/applications",
            params={"$select": "id,displayName", "$filter": f"appId eq '{client_id}'"},
        )
    )[0]

    # check extension properties for existence:
    extension_properties_path = f"/applications/{application['id']}/extensionProperties"
    extensions = await graph_request(extension_properties_path)
    already_have = set()
    # dict by extension name
    extensions = {ext["name"]: ext for ext in extensions}
    app_log.debug("Custom attributes defined: {}".format(", ".join(extensions.keys())))

    for ext_attr in custom_attributes:
        ext_attr_name = extension_attr_name(ext_attr["name"])
        existing = extensions.get(ext_attr_name)
        if existing:
            app_log.debug(f"Have custom attr {ext_attr['name']}")
            if existing["dataType"] != ext_attr["dataType"]:
                app_log.warning(
                    f"Deleting custom attr {ext_attr['name']} with wrong dataType"
                    f" {existing['dataType']} != {ext_attr['dataType']}"
                )
                await graph_request(
                    f"{extension_properties_path}/{existing['id']}", method="DELETE"
                )
            else:
                continue
        app_log.info(f"Creating extension attribute {ext_attr['name']}")
        try:
            await graph_request(
                extension_properties_path,
                method="POST",
                body=json.dumps(ext_attr),
                headers={"Content-Type": "application/json"},
            )
        except HTTPClientError as e:
            if e.response.status_code == 409:
                # ignore conflicts, maybe there was a race to creating the resource
                app_log.warning(f"Ignoring 409 conflict registering {ext_attr['name']}")
                pass
            else:
                raise


def wrap_user(user):
    """Wrap a user dict, adding logName field"""
    user.setdefault("logName", mask_phone(user.get("displayName", "unknown")))
    return user


async def find_user_by_phone(phone_number, select=None):
    """Return the user (dict) associated with the given phone number"""
    if select is None:
        ext_attr_names = ",".join(
            extension_attr_name(attr)
            for attr in (
                "deviceId",
                "consentRevoked",
                "consentRevokedDate",
                "testCredentials",
            )
        )
        select = f"id,identities,displayName,{ext_attr_names}"
    if "displayName" not in select:
        select = f"{select},displayName"
    users = await graph_request(
        "/users",
        params={"$select": select, "$filter": (f"displayName eq '{phone_number}'"),},
    )
    if not users:
        return None
    elif len(users) > 1:
        raise RuntimeError(f"More than one user with phone number {phone_number}!!!!")
    return wrap_user(users[0])


async def find_users_by_phone(phone_numbers, select=None, concurrency=10):
    """Return a list of users (dict) associated with the given phone numbers

    Numbers that do not belong to any users will be skipped.
    """

    users = []
    sem = asyncio.Semaphore(concurrency)

    async def do_one(number):
        async with sem:
            user_resp = await find_user_by_phone(number, select)
            if user_resp:
                users.append(user_resp)

    pending = set()
    for number in phone_numbers:
        pending.add(asyncio.ensure_future(do_one(number)))

    await asyncio.gather(*pending)

    return users


async def extract_deleted_numbers(phone_numbers, concurrency=10):
    """Extract phone numbers from the input that belongs to deleted susers"""

    existing_users = await find_users_by_phone(
        phone_numbers, select="displayName", concurrency=concurrency
    )

    existing_phone_numbers = set(user["displayName"] for user in existing_users)

    deleted_numbers = [
        number for number in phone_numbers if number not in existing_phone_numbers
    ]

    return deleted_numbers


async def store_device_id(user, device_id):
    """Store device_id in groups

    Group name == device id
    user group membership list == phone number device id history
    """
    user = wrap_user(user)
    app_log.info(f"Storing device id {device_id[:8]}... on user {user['logName']}")
    user_id = user["id"]

    # store 'latest' device id on custom attr
    await graph_request(
        f"/users/{user_id}",
        method="PATCH",
        body=json.dumps({extension_attr_name("deviceId"): device_id}),
        headers={"Content-Type": "application/json"},
    )

    # use groups to preserve device history
    groups = await graph_request(
        "/groups",
        params={
            "$select": "id,displayName",
            "$filter": (f"displayName eq '{device_id}'"),
        },
    )
    if groups:
        if len(groups) > 1:
            raise ValueError(
                f"Multiple groups matching device id {device_id}! Matches: {groups}"
            )
        app_log.info(
            f"Found matching group for {device_id[:8]}..., checking membership"
        )
        members = await graph_request(
            f"/groups/{groups[0]['id']}/members", params={"$select": "id,displayName"}
        )
        for member in members:
            if member["id"] == user_id:
                app_log.info(
                    f"{user['logName'][:5]}... already member of group {device_id}"
                )
                return
        if members:
            app_log.warning(
                f"Registering new owner of device {device_id} ({len(members)} past owners)"
            )
        app_log.info(f"Adding user {user['logName']} to group {device_id}")
        await graph_request(
            f"/groups/{groups[0]['id']}/members/$ref",
            method="POST",
            body=json.dumps(
                {"@odata.id": f"https://graph.microsoft.com/v1.0/users/{user['id']}"}
            ),
            headers={"Content-Type": "application/json"},
        )

        return

    app_log.info(f"Creating device group for {device_id}")
    return await graph_request(
        f"/groups",
        method="POST",
        body=json.dumps(
            {
                "groupTypes": [],
                "mailEnabled": False,
                "securityEnabled": True,
                "mailNickname": device_id,
                "displayName": device_id,
                "description": f"Group storing association for device {device_id}",
                "members@odata.bind": [
                    f"https://graph.microsoft.com/v1.0/users/{user['id']}"
                ],
            }
        ),
        headers={"Content-Type": "application/json"},
    )


def store_consent_revoked(user):
    """Store consent revoked in our extension attribute on user"""
    user = wrap_user(user)
    app_log.info(f"Storing revoked consent on user {user['logName']}")
    user_id = user["id"]
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    return graph_request(
        f"/users/{user_id}",
        method="PATCH",
        body=json.dumps(
            {
                extension_attr_name("consentRevoked"): True,
                extension_attr_name("consentRevokedDate"): timestamp,
                extension_attr_name("deviceId"): None,
            }
        ),
        headers={"Content-Type": "application/json"},
    )


def reset_consent(user):
    """Reset consent, e.g. on renewed request for tracking"""
    user = wrap_user(user)
    app_log.warning(f"Clearing revoked consent on user {user['logName']}")
    # First, ensure that device ids are dissociated from
    return graph_request(
        f"/users/{user['id']}",
        method="PATCH",
        body=json.dumps(
            {
                extension_attr_name("consentRevoked"): None,
                extension_attr_name("consentRevokedDate"): None,
            }
        ),
        headers={"Content-Type": "application/json"},
    )


async def mark_for_deletion(group, iot_deleted=False, timestamp=None):
    """Mark a group for deletion"""
    app_log.info(f"Marking device id group {group['displayName']} for deletion")
    if timestamp is None:
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    attrs = {
        extension_attr_name("toDelete"): True,
        extension_attr_name("toDeleteDate"): timestamp,
    }
    if iot_deleted:
        attrs[extension_attr_name("iotDeletedDate")] = timestamp
    await graph_request(
        f"/groups/{group['id']}",
        method="PATCH",
        body=json.dumps(attrs),
        headers={"Content-Type": "application/json"},
    )


async def mark_iot_deleted(group, timestamp=None):
    """Record that an iot device has been deleted

    so we don't try to delete it again
    """
    app_log.info(f"Marking iot device {group['displayName']} as deleted")
    if timestamp is None:
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    await graph_request(
        f"/groups/{group['id']}",
        method="PATCH",
        body=json.dumps({extension_attr_name("iotDeletedDate"): timestamp}),
        headers={"Content-Type": "application/json"},
    )


async def set_group_attr(group, **attrs):
    """Set one or more custom attributes on a group"""
    app_log.info(f"Setting attributes on {group['displayName']} {attrs}")
    await graph_request(
        f"/groups/{group['id']}",
        method="PATCH",
        body=json.dumps(
            {
                extension_attr_name(attr_name): value
                for attr_name, value in attrs.items()
            }
        ),
    )


async def dissociate_user_devices(user, iot_deleted=False):
    """Dissociate the groups that represent a user's device id associations

    and mark them for deletion
    """
    user = wrap_user(user)
    app_log.info(f"Dissociating devices from {user['logName']}")
    timestamp = datetime.datetime.utcnow().isoformat() + "Z"
    count = 0

    async for group in device_groups_for_user(user):
        count += 1
        await mark_for_deletion(group, iot_deleted=iot_deleted, timestamp=timestamp)
        app_log.info(f"Dissociating device id {group['displayName']} from phone number")
        await graph_request(
            f"/groups/{group['id']}/members/{user['id']}/$ref", method="DELETE",
        )
    if count:
        app_log.info(f"Dissociated {count} devices from {user['logName']}")


async def delete_group(group):
    """Delete a device group"""
    app_log.info(f"Deleting device group {group['displayName']}")
    await graph_request(f"/groups/{group['id']}", method="DELETE")


async def delete_device_group(device_id):
    """Delete a device group by device_id"""
    group = await get_group(device_id)
    if group:
        return await delete_group(group)


async def delete_user(user):
    """Delete a user"""
    user = wrap_user(user)
    app_log.info(f"Deleting user {user['logName']}")
    await graph_request(f"/users/{user['id']}", method="DELETE")


async def delete_deleted_user(user):
    """Delete a user"""
    user = wrap_user(user)
    app_log.info(f"Permanently deleting user {user['logName']}")
    await graph_request(f"/directory/deletedItems/{user['id']}", method="DELETE")


async def device_groups_for_user(user, select=None):
    """yield device ids for a single user"""
    user = wrap_user(user)
    count = 0
    if select is None:
        attr_names = ",".join(
            extension_attr_name(attr["name"])
            for attr in custom_attributes
            if "Group" in attr["targetObjects"]
        )
        select = f"id,displayName,createdDateTime,{attr_names}"
    async for group in paged_graph_request(f"/users/{user['id']}/memberOf"):
        count += 1
        yield group
    if count:
        app_log.info(f"User {user['logName']} has {count} devices")


async def get_group(device_id, select=None):
    """Get a single device group"""
    if select is None:
        attr_names = ",".join(
            extension_attr_name(attr["name"])
            for attr in custom_attributes
            if "Group" in attr["targetObjects"]
        )
        select = f"id,displayName,createdDateTime,{attr_names}"
    groups = await graph_request(
        "/groups",
        params={"$filter": f"displayName eq '{device_id}'", "$select": select,},
    )
    if not groups:
        app_log.warning(f"No group for device {device_id}")
        return
    return groups[0]


async def device_ids_for_user(user):
    """Yield device ids instead of groups"""
    async for group in device_groups_for_user(user):
        yield group["displayName"]


async def user_for_device(device_id_or_group):
    """Return the user dict for a device

    device may be given as a group dict or a device id string
    """
    if isinstance(device_id_or_group, str):
        group = await get_group(device_id_or_group)
        if not group:
            return
    else:
        group = device_id_or_group
    device_id = group["displayName"]

    revoked = extension_attr_name("consentRevoked")
    members = await graph_request(
        f"/groups/{group['id']}/members",
        params={"$select": f"id,displayName,{revoked}"},
    )
    if not members:
        app_log.warning(f"No owner for device {device_id}")
        return
    user = members[0]
    if user.get(revoked):
        app_log.error(f"Refusing to return phone number with revoked consent")
        # This shouldn't happen, trigger delete?
        return
    return user


async def phone_number_for_device_id(device_id):
    """Return phone number, given a device id"""
    user = await user_for_device(device_id)
    if user:
        return user["displayName"]


async def process_user_deletion(user):
    """Process a user for deletion, including deletion of devices from IoTHub"""
    # local import because most graph operations don't require IOTHub access
    from . import devices

    # unregister in iothub
    device_ids = []
    async for device_id in device_ids_for_user(user):
        device_ids.append(device_id)

    if device_ids:
        for result in await devices.delete_devices(*device_ids, raise_on_error=False):
            # most likely failure is a 404,
            # which means it was already deleted from iothub
            # raise any *other* error, though
            if isinstance(result, Exception):
                if isinstance(result, HTTPClientError) and result.code == 404:
                    app_log.warning(f"Device already deleted")
                else:
                    app_log.error(f"Failed to delete device from IoTHub: {result}")

    # immediately dissociate device ids from user and mark for data deletion
    await dissociate_user_devices(user, iot_deleted=True)
    # delete the user itself so we no longer have a record of this phone number
    await delete_user(user)


async def list_users(select=None, filter=None):
    """yield a list of all users"""
    if select is None:
        attr_names = ",".join(
            extension_attr_name(attr["name"])
            for attr in custom_attributes
            if "User" in attr["targetObjects"]
        )
        select = f"id,identities,displayName,createdDateTime,{attr_names}"
    _filter = "startswith(displayName, '+')"
    if filter:
        _filter = f"{_filter} and {filter}"
    async for user in paged_graph_request(
        "/users", params={"$select": select, "$filter": _filter, "$top": "999"},
    ):
        yield wrap_user(user)


async def list_deleted_users(select=None, filter=None):
    """yield a list of all users"""
    if select is None:
        attr_names = ",".join(
            extension_attr_name(attr["name"])
            for attr in custom_attributes
            if "User" in attr["targetObjects"]
        )
        select = f"id,identities,displayName,createdDateTime,{attr_names}"
    _filter = "startswith(displayName, '+')"
    if filter:
        _filter = f"{_filter} and {filter}"
    async for user in paged_graph_request(
        "/directory/deletedItems/microsoft.graph.user",
        params={"$select": select, "$filter": _filter, "$top": "999"},
    ):
        yield wrap_user(user)


async def list_groups(select=None, filter=None):
    """yield a list of all groups"""
    if select is None:
        attr_names = ",".join(
            extension_attr_name(attr["name"])
            for attr in custom_attributes
            if "Group" in attr["targetObjects"]
        )
        select = f"id,displayName,createdDateTime,{attr_names}"
    params = {"$select": select, "$top": "999"}
    if filter:
        params["$filter"] = filter
    async for group in paged_graph_request(
        "/groups", params=params,
    ):
        yield group


phone_number_claims = ["signInNames.phoneNumber", "act_phone_number", "signinname"]


def get_user_token(handler, claims=None, phone_number_claim="sign", public_key=None):
    """B2C JWT-token authorization for tornado applications

    Use as .get_current_user on authenticated handlers
    """
    if claims is None:
        claims = {"scp": "Device.Write"}
    auth_header = handler.request.headers.get("Authorization")
    if not auth_header:
        raise web.HTTPError(401, "Authorization required")

    kind, *rest = auth_header.split(None, 1)
    if not rest or kind.lower() != "bearer":
        raise web.HTTPError(403, "Malformed auth header")
    token = rest[0]
    try:
        kid = jwt.get_unverified_header(token)["kid"]
        public_key = _PUBLIC_KEYS[kid]
        payload = jwt.decode(token, public_key, algorithms=["RS256"], audience=audience)
        for key, value in claims.items():
            if key not in payload:
                raise ValueError(f"Need claim {key}")
            if payload[key] != value:
                raise ValueError(f"Need claim {key}={value}, not {payload[key]}")
        for phone_number_claim in phone_number_claims:
            if phone_number_claim in payload:
                phone_number = payload.get(phone_number_claim)
                break
        else:
            phone_number = None
        payload["_phonenumber"] = phone_number
        if not phone_number or not phone_number.startswith("+"):
            app_log.warning(f"Missing phone number in: {payload}")
            raise web.HTTPError(
                400, f"Error validating phone number in token: {phone_number}"
            )

        if phone_number in get_blacklist():
            app_log.warning(
                f"Attempt to register with blacklisted phone number: {phone_number}"
            )
            # do not raise with informative error message for blacklisted requests
            raise web.HTTPError(403)

        app_log.info(f"Authenticated as {mask_phone(phone_number)}")
        # store token itself for checking signatures
        payload["_access_token"] = token
    except web.HTTPError:
        # cache failed auth to avoid calling multiple times
        handler.current_user = None
        # let HTTPErrors be raised
        raise
    except Exception:
        app_log.exception(f"Failed to decode jwt token: {token}")
        return None
    return payload
