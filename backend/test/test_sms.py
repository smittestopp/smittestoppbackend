"""
Script to make a request against the sms verify service

DEPRECATED: We will not use this! We will use Azure AD B2C instead.
"""

import datetime
import os
import json
import time


import requests

run_service_url = "https://sms-verify-pndkffozja-ew.a.run.app"


def main():
    # request a Bearer token for the given service account and endpoint
    phone_number = input("your phone number with +country code (e.g. +47...): ")

    # make an authenticated request to start verification
    # request is JSON: {"number": "+47..."}
    r = requests.post(
        run_service_url + "/verify-start",
        data=json.dumps({"number": phone_number}),
    )
    # response is JSON: {"number": "+47...", "status": "pending"} on success
    print(r.text)
    r.raise_for_status()

    code = input("6 digit auth code received via SMS: ")
    # request is JSON: {"number": "+47...", "code": "123456"} on success
    r = requests.post(
        run_service_url + "/verify-end",
        data=json.dumps({"number": phone_number, "code": code}),
    )
    # response is JSON: {"status": "approved"} on success
    print(r.text)
    r.raise_for_status()


if __name__ == '__main__':
    main()
