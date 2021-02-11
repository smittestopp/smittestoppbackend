"""
Functions for generating, storing, and retrieving pin codes from the database.
"""

import os
import random
import string
from datetime import timedelta

from corona_backend import utils
from corona_backend.sql import with_db

ascii_letters_and_digits = string.ascii_letters + string.digits

# opt-in to pin codes via environment variable
PIN_ENABLED = os.environ.get("PIN_ENABLED", "0") == "1"


@with_db()
def store_pin_code(db, phone_number, pin_code, timestamp):
    db.execute(
        r"{CALL dbo.insertPinCode(?,?,?)}", (phone_number, pin_code, timestamp)
    ).commit()


@with_db()
def get_latest_pin_code_after_threshold(db, phone_number, threshold):
    row = db.execute(
        r"SELECT pin FROM dbo.getPinCodeNewestEntryByThreshold(?,?)",
        (phone_number, threshold),
    ).fetchone()
    if row:
        return row[0]


@with_db()
def get_pin_codes(db, phone_number):
    pin_codes = []
    for (pin_code, created_at,) in db.execute(
        r"SELECT pin, created_at FROM dbo.getPinCodesByPhoneNumber(?)", phone_number
    ).fetchall():
        pin_codes.append(
            {"pin_code": pin_code, "created_at": utils.isoformat(created_at)}
        )
    return pin_codes


def generate_pin(characters=ascii_letters_and_digits, pin_length=6):
    return "".join(random.choice(characters) for _ in range(pin_length))


async def generate_and_store_pin(phone_number):
    pin_code = generate_pin()
    timestamp = utils.now_at_utc()
    await store_pin_code(
        phone_number=phone_number, pin_code=pin_code, timestamp=timestamp,
    )
    return pin_code


async def fetch_or_generate_pin(phone_number, not_older_than=7):
    """ Fetch pin from database or generate now if too old

    If there are no pin codes associated with a phone number we create a new.
    If there are, but the latest is older than 'not_older_than', we also create a new.
    Otherwise we use the latest.
    """

    threshold = utils.now_at_utc() - timedelta(days=not_older_than)

    pin = await get_latest_pin_code_after_threshold(
        phone_number=phone_number, threshold=threshold
    )
    if pin is None:
        pin = await generate_and_store_pin(phone_number=phone_number)
    return pin
