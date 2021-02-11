"""
sample for registering a device with the onboarding service
and requesting contactids with hmac-authenticated requests

Required $B2C_TOKEN (prompts if missing)

Note: test number functionality will only work for numbers pre-registered as approved testers,
(TESTER_NUMBERS in helm/secrets/dev.yaml)
otherwise the device will be associated with your real phone number
"""
import base64
import hmac
import os
import pprint
import random
import sys
import time

import requests
from tornado.httputil import url_concat

release = os.environ.get("RELEASE", "dev")
if release == "prod":
    b2c_tenant = "smittestopp"
    b2c_client_id = ""
else:
    b2c_tenant = "devsmittestopp"
    b2c_client_id = ""

scope = ""
onboarding_host = f"https://pubapi.{release}.corona.nntb.no"
# onboarding_host = "http://127.0.0.1:8080"

b2c_token_url = url_concat(
    f"https://{b2c_tenant}.b2clogin.com/{b2c_tenant}.onmicrosoft.com/oauth2/v2.0/authorize",
    dict(
        p="B2C_1A_phone_SUSI",
        client_id=b2c_client_id,
        nonce="defaultNonce",
        redirect_uri="https://jwt.ms",
        scope=f"https://{b2c_tenant}.onmicrosoft.com/backend/Device.Write",
        response_type="token",
        prompt="login",
    ),
)

try:
    token = os.environ["B2C_TOKEN"]
except KeyError:
    print("Visit this URL to get a token and store it in $B2C_TOKEN")
    print(f"  {b2c_token_url}")
    sys.exit(1)

test_number = f"+00{random.randint(1,9999):06}"

# make a request on behalf of a test user
tic = time.perf_counter()

s = requests.Session()
s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36"

r = s.post(
    onboarding_host + "/onboarding/register-device",
    headers={
        "Authorization": f"Bearer {token}",
        "Test-Number": test_number,
    },
)
toc = time.perf_counter()
duration = toc - tic
try:
    r.raise_for_status()
except Exception:
    print(r.text)
    raise

# display info about device we just registered
device_info = r.json()
print(
    f"registered device for {device_info['PhoneNumber']} with id={device_info['DeviceId']} in {duration:.3f}s"
)
device_id = device_info['DeviceId']

# send a request for contact ids

timestamp = str(int(time.time()))
key = base64.b64decode(device_info["SharedAccessKey"])

message = f"{device_info['DeviceId']}|{timestamp}|POST|/contactids".encode("utf8")
signature = hmac.new(key=key, msg=message, digestmod="sha256").digest()
b64_signature = base64.b64encode(signature).decode("ascii")

r = s.post(
    onboarding_host + "/app/contactids",
    headers={
        "Authorization": f"SMST-HMAC-SHA256 {device_id};{timestamp};{b64_signature}",
    },
)
try:
    r.raise_for_status()
except Exception:
    print(r.text)
    raise

print("Received contactids response:")
pprint.pprint(r.json())
