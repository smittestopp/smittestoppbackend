import pytest

from corona_backend import utils


@pytest.mark.parametrize(
    "phone_nr, masked_phone_nr",
    [
        ("+4712345678", "+47XXXXX678"),
        ("+0000000000", "+00XXXXX000"),
        ("unknown", "unkXown"),
        ("004712345678", "004XXXXXX678"),
        ("000000000000", "000XXXXXX000"),
    ],
)
def test_mask_phone(phone_nr, masked_phone_nr):
    assert utils.mask_phone(phone_nr) == masked_phone_nr


def test_timer():
    # smoke test for timer method
    message_test = "testmessage"
    with utils.timer(message_test):
        pass
