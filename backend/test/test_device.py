"""
sample for registering a device with the onboarding service
and sending device telemetry messages

Requires azure-iot-device and $ONBOARDING_TOKEN
"""
import os
import time
import json
import random
import sys

from tornado.httputil import url_concat
from azure.iot.device import IoTHubDeviceClient, Message
import requests

release = os.environ.get("RELEASE", "dev")
if release == "prod":
    b2c_tenant = "smittestopp"
    b2c_client_id = ""
else:
    b2c_tenant = "devsmittestopp"
    b2c_client_id = ""

scope = ""
onboarding_host = f"https://pubapi.{release}.corona.nntb.no/onboarding"
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
r = requests.post(
    onboarding_host + "/register-device",
    headers={
        "Authorization": f"Bearer {token}",
        "Test-Number": test_number,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/57.0.2987.133 Safari/537.36",
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

# connect our new device
connection_string = device_info["ConnectionString"]
device_client = IoTHubDeviceClient.create_from_connection_string(connection_string)
device_client.connect()

# validate by sending some messages
n_msgs = 10
tic = time.perf_counter()
for i in range(n_msgs):
    print("sending message #" + str(i))
    msg = Message(
        json.dumps({"test": i}),
        content_encoding="utf-8",
        content_type="application/json",
    )
    msg.event_type = "test"
    device_client.send_message(msg)

toc = time.perf_counter()
duration = toc - tic
print(f"Sent {n_msgs} messages in {duration:.3f}s")
