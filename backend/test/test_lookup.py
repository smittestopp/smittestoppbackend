#!/usr/bin/env python3
"""
test lookup endpoint

usage:

    python3 test_lookup.py +47....

"""

import json
import os
import pprint
import sys
import time

import requests

here = os.path.dirname(os.path.abspath(__file__))
backend = os.path.join(here, os.pardir)
ssl_dir = os.path.join(backend, "secrets/dev/ssl")
ssl_key = os.path.join(ssl_dir, "fhi.key")
ssl_cert = os.path.join(ssl_dir, "fhi.pem")

lookup_url = "https://api-smittestopp-dev.azure-api.net/fhi/lookup"


def main(phone_number):
    if not phone_number.startswith("+"):
        # guess they meant
        phone_number = f"+47{phone_number}"
        print(f"Phone number missing +, using {phone_number}", file=sys.stderr)

    s = requests.Session()
    s.cert = (ssl_cert, ssl_key)
    r = s.post(
        lookup_url,
        data=json.dumps(
            {"phone_number": phone_number, "time_to": "2020-04-16T12:00:00Z"}
        ),
    )
    try:
        r.raise_for_status()
    except Exception:
        print(r.text)
        raise
    response = r.json()
    pprint.pprint(response, sys.stderr)
    result_url = response["result_url"]

    while True:
        r = s.get(result_url)
        print(r.status_code)
        try:
            r.raise_for_status()
        except Exception:
            print(r.text)
            raise
        if r.status_code == 202:
            print(r.json()["message"], file=sys.stderr)
            time.sleep(30)
        elif r.status_code == 200:
            print(json.dumps(r.json(), sort_keys=True, indent=1))
            return


if __name__ == "__main__":
    main(sys.argv[1])
