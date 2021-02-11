"""Dump development deployment phone numbers to .csv

Requires development-environment environment variables
to access AD and corona_backend

Usage (run in corona image):

    make build/corona
    cat test/phoneNumbers-csv.py | docker run --rm -i --env-file secrets/dev/env-file $(make tag/corona) python3 > phonenumbers.csv
"""

import asyncio

from tornado.log import enable_pretty_logging

from corona_backend.graph import list_users, extension_attr_name


async def collect_users():
    """yield all phone number, device group pairs"""

    async for user in list_users():
        if user.get(extension_attr_name("testCredentials")):
            continue
        yield user["displayName"]


async def phonenumbers_csv():
    """Print the phonenumbersl
    """
    async for phone in collect_users():
        print(f"{phone[1:]}")


async def main():
    enable_pretty_logging()
    await phonenumbers_csv()

if __name__ == "__main__":
    asyncio.run(main())
