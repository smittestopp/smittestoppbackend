"""Dump csv for bulk deletion

Requires access to AD and corona_backend

Important notes:

- Bulk delete parser is sensitive to CRLF line endings.
  Must not use default LF!

Usage (run in corona image):

    cat test/todelete-csv.py | kubectl exec -it corona-prod-fhi-... -- python3 > bulk-delete.csv
"""

import asyncio
import sys

from tornado.log import enable_pretty_logging, app_log

from corona_backend.graph import list_users, extension_attr_name


async def collect_users():
    """yield all userPrincipalName fields for users

    Excluding:
    - test accounts
    - 'real' users who aren't phone numbers
    """

    async for user in list_users():
        if user.get(extension_attr_name("testCredentials")):
            # app_log.info(f"skipping {user['displayName']}")
            continue
        if not user["displayName"].startswith("+"):
            app_log.info(f"skipping {user['displayName']}")
            continue

        yield user["id"]


async def todelete_csv():
    """Print the upns"""
    async for uid in collect_users():
        sys.stdout.write(uid)
        sys.stdout.write("\r\n")


async def main():
    enable_pretty_logging()
    # write the required header from the template
    sys.stdout.write("version:v1.0\r\n")
    sys.stdout.write("User name [userPrincipalName] Required\r\n")
    await todelete_csv()

if __name__ == "__main__":
    asyncio.run(main())
