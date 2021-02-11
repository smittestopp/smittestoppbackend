import json
from datetime import timedelta
from unittest.mock import call, patch

import pytest
import tornado.web

from corona_backend import pin, sql, testsql, utils
from corona_backend.fhi.handlers.base import API_KEY
from corona_backend.fhi.handlers.endpoints import endpoints

CONSECUTIVE_FAILURE_LIMIT = 2


fhi_post_req = dict(
    method="POST", headers={"Api-Key": API_KEY, "Certificate-Name": "Foo"}
)

fhi_get_req = dict(
    method="GET", headers={"Api-Key": API_KEY, "Certificate-Name": "Foo"}
)

helsenorge_post_req = dict(
    body="{}",
    method="POST",
    headers={
        "Authorization": f"Bearer secret",
        "Api-Key": API_KEY,
        "Certificate-Name": "Foo",
    },
)


insert_test_dluserdatastaging_qry = """
INSERT INTO dbo.dluserdatastaging(uuid) VALUES ('device_id1'),('device_id2')
"""

insert_test_uuid_id_qry = """
INSERT INTO dbo.uuid_id(uuid) values ('device_id1'),('device_id2')
"""

insert_test_gps_event_qry = """
INSERT INTO dbo.gpsevents(
    id,
    timefrom,
    timeto,
    latitude,
    longitude,
    accuracy,
    speed,
    speedaccuracy,
    altitude,
    altitudeaccuracy,
    daypart
) VALUES (
    1,
    '2018-03-12T10:12:45Z',
    '2018-03-12T10:12:46Z',
    '59.890597',
    '10.533402',
    1,
    100,
    1,
    3,
    1,
    1
),(
    1,
    '2018-03-12T10:12:55Z',
    '2018-03-12T10:12:56Z',
    '59.890597',
    '10.533403',
    1,
    100,
    1,
    3,
    1,
    1
)
"""


async def insert_test_gps_event():
    @testsql.with_db()
    def _insert(db):
        db.execute(insert_test_dluserdatastaging_qry).commit()
        db.execute(insert_test_uuid_id_qry).commit()
        db.execute(insert_test_gps_event_qry).commit()

    with testsql.set_db_user("SA"):
        await _insert()


async def insert_pin_test_data():
    with testsql.set_db_user(testsql.DB_USER_SERVICE_API):
        # Pin created more than a week ago - not reusable.
        await pin.store_pin_code(
            phone_number="+0012341234",
            pin_code="testdbpinX",
            timestamp=utils.now_at_utc() - timedelta(days=17),
        )

        # Pin created less than a week ago - reusable.
        await pin.store_pin_code(
            phone_number="+0012341234",
            pin_code="testdbpin1",
            timestamp=utils.now_at_utc() - timedelta(days=6, minutes=1),
        )

        # Pin created more than a week ago - not reusable.
        await pin.store_pin_code(
            phone_number="+0012341236",
            pin_code="testdbpin2",
            timestamp=utils.now_at_utc() - timedelta(days=7, minutes=1),
        )


async def insert_test_applog():
    await sql.log_access(
        timestamp=utils.now_at_utc(),
        phone_numbers=["+0012341234"],
        person_name="For Etternavn",
        person_organization="Some Organization",
        person_id="",
        organization="Norsk Helsenett",
        legal_means="Some legal means",
    )

    await sql.log_access(
        timestamp=utils.now_at_utc(),
        phone_numbers=["+0012341234"],
        person_name="",
        person_organization="Some Other Organization",
        person_id="",
        organization="Norsk Helsenett",
        legal_means="Some legal means",
    )


@pytest.fixture(scope="module", autouse=True)
async def testsetup(setup_testdb, now_at_utc_mock):
    """Setup for fhi handlers

    Creates testdb and tears it down when the tests have completed."""


@pytest.fixture
def app():
    return tornado.web.Application(
        endpoints(),
        consecutive_failures=0,
        consecutive_failure_limit=CONSECUTIVE_FAILURE_LIMIT,
    )


async def test_lookup_happy(
    http_client,
    base_url,
    db_user_serviceapi,
    now_at_utc_mock,
    redis_lookup_mock,
    request_id_mock,
    find_user_mock,
    device_ids_mock,
    trucate_tables_after_test,
):
    trucate_tables_after_test(["dbo.applog"])

    fhi_post_req["body"] = '{"phone_number": "+0012341234"}'

    expected_resp_body = {
        "request_id": "1234",
        "result_url": "https{}/fhi/lookup/1234".format(base_url[4:]),
        "result_expires": "2018-03-12T14:12:45Z",
    }

    expected_events = [
        {
            "timestamp": "2018-03-12",
            "phone_number": "+0012341234",
            "person_name": "Varslingsystem",
            "person_organization": "Folkehelseinstituttet",
            "person_id": "",
            "technical_organization": "Folkehelseinstituttet",
            "legal_means": "Oppslag i nærkontakter for varsling",
            "count": 1,
        }
    ]

    resp = await http_client.fetch(f"{base_url}/lookup", **fhi_post_req)
    assert resp.code == 202
    assert json.loads(resp.body) == expected_resp_body

    events, count = await sql.get_access_log(phone_number="+0012341234",)
    assert count == 1
    assert events == expected_events

    find_user_mock.assert_called_with("+0012341234")
    device_ids_mock.assert_called_with(
        {"displayName": "+0012341234", "logName": "Foo Name"}
    )


async def test_lookup_invalid_audit_log(
    http_client, base_url, find_user_mock,
):
    fhi_post_req["body"] = '{"phone_number": "+0012345678"}'

    invalid_audit_fields_missing_org = dict(
        person_name="Varslingsystem",
        person_id="",
        person_organization="Folkehelseinstituttet",
        organization="",
        legal_means="Oppslag i nærkontakter for varsling",
    )

    invalid_audit_fields_missing_legal_means = dict(
        person_name="Varslingsystem",
        person_id="",
        person_organization="Folkehelseinstituttet",
        organization="Folkehelseinstituttet",
        legal_means="",
    )

    for invalid_audit_fields in [
        invalid_audit_fields_missing_org,
        invalid_audit_fields_missing_legal_means,
    ]:
        with patch(
            "corona_backend.fhi.handlers.fhi.FHIHandler.audit_fields",
            new=invalid_audit_fields,
        ):
            with pytest.raises(tornado.httpclient.HTTPClientError) as e:
                await http_client.fetch(f"{base_url}/lookup", **fhi_post_req)
            assert e.value.code == 500


async def test_lookup_audit_log_connection_error(
    http_client, base_url, find_user_mock, sql_log_access_connection_error,
):
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/lookup", **fhi_post_req)
    assert e.value.code == 503
    assert (
        e.value.response.body
        == b'{"status": 503, "message": "Internal temporary server error - please try again"}'
    )


async def test_lookup_exception_audit_log(
    http_client, base_url, find_user_mock, sql_log_access_exception,
):
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/lookup", **fhi_post_req)
    assert e.value.code == 500
    assert json.loads(e.value.response.body)


async def test_lookup_no_user_found(
    http_client, base_url, find_user_none_mock,
):
    fhi_post_req["body"] = '{"phone_number": "+0012345678"}'

    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/lookup", **fhi_post_req)
    assert e.value.code == 404
    assert json.loads(e.value.response.body) == {
        "phone_number": "+0012345678",
        "found_in_system": False,
    }

    find_user_none_mock.assert_called_with("+0012345678")


async def test_lookup_no_device_id_for_user(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    now_at_utc_mock,
    redis_lookup_mock,
    find_user_mock,
    device_ids_empty_mock,
):
    trucate_tables_after_test(["dbo.applog"])

    fhi_post_req["body"] = '{"phone_number": "+0012341234"}'

    expected_events = [
        {
            "timestamp": "2018-03-12",
            "phone_number": "+0012341234",
            "person_name": "Varslingsystem",
            "person_organization": "Folkehelseinstituttet",
            "person_id": "",
            "technical_organization": "Folkehelseinstituttet",
            "legal_means": "Oppslag i nærkontakter for varsling",
            "count": 1,
        }
    ]

    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/lookup", **fhi_post_req)
    assert e.value.code == 404
    assert json.loads(e.value.response.body) == {
        "phone_number": "+0012341234",
        "found_in_system": False,
    }

    events, count = await sql.get_access_log(phone_number="+0012341234",)
    assert count == 1
    assert events == expected_events

    find_user_mock.assert_called_with("+0012341234")
    device_ids_empty_mock.assert_called_with(
        {"displayName": "+0012341234", "logName": "Foo Name"}
    )


@pytest.mark.parametrize("pin_enabled", (True, False))
async def test_lookup_result_happy(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    redis_lookup_result_mock,
    request_id_mock,
    user_for_device_mock,
    get_device_mock,
    generate_pin_mock,
    pin_enabled,
):
    """Emulates a scenario where the analysis produces 3 contacts.

    Two of the contacted people do already have one or more pin codes
    associated with their phone numbers. The person with phone number +0012341234
    are associated with 2 pin codes, but one of them has expired. The person
    with phone number +0012341236 does only have an expired phone number.
    For the latter person we expect a new pin code to be generated and stored.

    The last person (+0012341235) is not associated with a pin code.

    (See testsetup for pre-test db inserts)
    """

    await insert_pin_test_data()

    trucate_tables_after_test(["dbo.applog", "dbo.pincodes"])

    fhi_post_req["body"] = json.dumps({"phone_number": "+0012345678"})

    expected_resp_body = {
        "phone_number": "+4712341234",
        "found_in_system": True,
        "last_activity": "2020-04-11T11:12:36Z",
        "contacts": [
            {
                "+0012341234": {"foo": "bar", "pin_code": "testdbpin1"},
                "+0012341235": {"foo": "baz", "pin_code": "pin_code_1"},
                "+0012341236": {"foo": "lol", "pin_code": "pin_code_2"},
            },
        ],
    }
    if not pin_enabled:
        for contact in expected_resp_body["contacts"]:
            for contact_dict in contact.values():
                contact_dict.pop("pin_code")

    with patch.object(pin, "PIN_ENABLED", pin_enabled):
        resp = await http_client.fetch(f"{base_url}/lookup/1234", **fhi_get_req)

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    user_for_device_mock.assert_has_calls([call("result_key_1"), call("result_key_2")])
    get_device_mock.assert_has_calls([call("device_id_1"), call("device_id_2")])

    if pin_enabled:
        expected_pins_person_1 = [
            {"pin_code": "testdbpinX", "created_at": "2018-02-23T10:12:45Z"},
            {"pin_code": "testdbpin1", "created_at": "2018-03-06T10:11:45Z"},
        ]
        expected_pins_person_2 = [
            {"pin_code": "pin_code_1", "created_at": "2018-03-12T10:12:45Z"},
        ]
        expected_pins_person_3 = [
            {"pin_code": "testdbpin2", "created_at": "2018-03-05T10:11:45Z"},
            {"pin_code": "pin_code_2", "created_at": "2018-03-12T10:12:45Z"},
        ]

        for phone_number, expected_pins in {
            "+0012341234": expected_pins_person_1,
            "+0012341235": expected_pins_person_2,
            "+0012341236": expected_pins_person_3,
        }.items():
            pin_codes = await pin.get_pin_codes(phone_number=phone_number)
            assert pin_codes == expected_pins


async def test_lookup_result_handler_no_request_found(
    http_client, base_url, redis_lookup_no_result_mock,
):
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/lookup/1234", **fhi_get_req)
    assert e.value.code == 404
    assert e.value.response.body == b'{"status": 404, "message": "No such request"}'


async def test_lookup_result_handler_analysis_in_progress(
    http_client, base_url, redis_lookup_no_result_analysis_in_progress_mock
):
    fhi_post_req["body"] = '{"phone_number": "+0012345678"}'

    resp = await http_client.fetch(f"{base_url}/lookup/1234", **fhi_get_req)

    assert resp.code == 202
    assert json.loads(resp.body) == {
        "message": "Not finished processing (completed 1/2 tasks)"
    }


async def test_lookup_result_handler_analysis_error(
    http_client, base_url, redis_lookup_result_analysis_error_mock,
):
    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/lookup/1234", **fhi_get_req)
    assert e.value.code == 500
    assert json.loads(e.value.response.body) == {
        "status": 500,
        "message": "Error in analysis pipeline. Please report the input parameters to the analysis team.",
    }


async def test_fhi_access_log_handler_happy(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    find_user_mock,
):
    trucate_tables_after_test(["dbo.applog"])
    await insert_test_applog()

    fhi_post_req["body"] = '{"phone_number": "+0012341234", "person_name": "Foo Name"}'

    expected_resp_body = {
        "phone_number": "+0012341234",
        "found_in_system": True,
        "events": [
            {
                "timestamp": "2018-03-12",
                "phone_number": "+0012341234",
                "person_name": "",
                "person_organization": "Some Other Organization",
                "person_id": "",
                "technical_organization": "Norsk Helsenett",
                "legal_means": "Some legal means",
                "count": 1,
            },
            {
                "timestamp": "2018-03-12",
                "phone_number": "+0012341234",
                "person_name": "For Etternavn",
                "person_organization": "Some Organization",
                "person_id": "",
                "technical_organization": "Norsk Helsenett",
                "legal_means": "Some legal means",
                "count": 1,
            },
        ],
        "total": 2,
        "per_page": 30,
        "page_number": 1,
    }

    resp = await http_client.fetch(f"{base_url}/fhi-access-log", **fhi_post_req)
    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    find_user_mock.assert_called_with("+0012341234")


async def test_fhi_egress_handler(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    now_at_utc_mock,
    find_user_mock,
    device_ids_mock,
):
    trucate_tables_after_test(
        ["dbo.applog", "dbo.uuid_id", "dbo.dluserdatastaging", "dbo.gpsevents"]
    )

    await insert_test_gps_event()

    fhi_post_req[
        "body"
    ] = '{"phone_number": "+0012341234", "person_name": "Foo Name", "legal_means": "foo"}'

    expected_resp_body = {
        "phone_number": "+0012341234",
        "found_in_system": True,
        "events": [
            {
                "time_from": "2018-03-12T10:12:55Z",
                "time_to": "2018-03-12T10:12:56Z",
                "latitude": 59.890597,
                "longitude": 10.533403,
                "accuracy": 1.0,
                "speed": 100.0,
                "speed_accuracy": 1.0,
                "altitude": 3.0,
                "altitude_accuracy": 1.0,
            },
            {
                "time_from": "2018-03-12T10:12:45Z",
                "time_to": "2018-03-12T10:12:46Z",
                "latitude": 59.890597,
                "longitude": 10.533402,
                "accuracy": 1.0,
                "speed": 100.0,
                "speed_accuracy": 1.0,
                "altitude": 3.0,
                "altitude_accuracy": 1.0,
            },
        ],
        "total": 2,
        "per_page": 30,
        "page_number": 1,
    }

    resp = await http_client.fetch(f"{base_url}/fhi-egress", **fhi_post_req)
    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    find_user_mock.assert_called_with("+0012341234")
    device_ids_mock.assert_called_with(
        {"displayName": "+0012341234", "logName": "Foo Name"}
    )


async def test_deletion(
    http_client, base_url, now_at_utc_mock, db_user_serviceapi, deleted_nums_mock,
):
    fhi_post_req["body"] = '{"phone_numbers":["+0012341234", "+0012341235"]}'

    expected_resp_body = {"deleted_phone_numbers": ["+0012341234"]}

    resp = await http_client.fetch(f"{base_url}/deletions", **fhi_post_req)

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    deleted_nums_mock.assert_called_with(["+0012341234", "+0012341235"])


async def test_helsenorge_egress_handler(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    current_user_mock,
    now_at_utc_mock,
    find_user_mock,
    device_ids_mock,
):
    trucate_tables_after_test(
        ["dbo.applog", "dbo.uuid_id", "dbo.dluserdatastaging", "dbo.gpsevents"]
    )

    await insert_test_gps_event()

    expected_resp_body = {
        "phone_number": "+0012341234",
        "found_in_system": True,
        "events": [
            {
                "time_from": "2018-03-12T10:12:55Z",
                "time_to": "2018-03-12T10:12:56Z",
                "latitude": 59.890597,
                "longitude": 10.533403,
                "accuracy": 1.0,
                "speed": 100.0,
                "speed_accuracy": 1.0,
                "altitude": 3.0,
                "altitude_accuracy": 1.0,
            },
            {
                "time_from": "2018-03-12T10:12:45Z",
                "time_to": "2018-03-12T10:12:46Z",
                "latitude": 59.890597,
                "longitude": 10.533402,
                "accuracy": 1.0,
                "speed": 100.0,
                "speed_accuracy": 1.0,
                "altitude": 3.0,
                "altitude_accuracy": 1.0,
            },
        ],
        "total": 2,
        "per_page": 30,
        "page_number": 1,
    }

    resp = await http_client.fetch(f"{base_url}/egress", **helsenorge_post_req)

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    find_user_mock.assert_called_with("+0012341234")
    device_ids_mock.assert_called_with(
        {"displayName": "+0012341234", "logName": "Foo Name"}
    )


async def test_helsenorge_access_log_handler(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    current_user_mock,
    find_user_mock,
):
    trucate_tables_after_test(["dbo.applog"])
    await insert_test_applog()

    expected_resp_body = {
        "phone_number": "+0012341234",
        "found_in_system": True,
        "events": [
            {
                "timestamp": "2018-03-12",
                "phone_number": "+0012341234",
                "person_name": "",
                "person_organization": "Some Other Organization",
                "person_id": "",
                "technical_organization": "Norsk Helsenett",
                "legal_means": "Some legal means",
                "count": 1,
            },
            {
                "timestamp": "2018-03-12",
                "phone_number": "+0012341234",
                "person_name": "For Etternavn",
                "person_organization": "Some Organization",
                "person_id": "",
                "technical_organization": "Norsk Helsenett",
                "legal_means": "Some legal means",
                "count": 1,
            },
        ],
        "total": 2,
        "per_page": 30,
        "page_number": 1,
    }

    resp = await http_client.fetch(f"{base_url}/access-log", **helsenorge_post_req)
    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    find_user_mock.assert_called_with("+0012341234")


async def test_revoke_consent_handler(
    http_client,
    base_url,
    current_user_mock,
    find_user_mock,
    store_consent_revoked_mock,
    user_deletion_mock,
):
    expected_resp_body = {
        "Status": "Success",
        "Message": (
            "Your phone number is no longer associated with any data."
            " The underlying anonymized data will be deleted shortly."
        ),
    }

    resp = await http_client.fetch(f"{base_url}/revoke-consent", **helsenorge_post_req)

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body

    find_user_mock.assert_called_with("+0012341234")
    store_consent_revoked_mock.assert_called_with(
        {"displayName": "+0012341234", "logName": "Foo Name"}
    )
    user_deletion_mock.assert_called_with(
        {"displayName": "+0012341234", "logName": "Foo Name"}
    )


async def test_birth_year_handler_happy(
    http_client,
    base_url,
    db_user_serviceapi,
    trucate_tables_after_test,
    find_user_mock,
    device_ids_mock,
):
    trucate_tables_after_test(["dbo.BirthYear"])

    with testsql.set_db_user(testsql.DB_USER_REGISTRATION):
        await sql.upsert_birth_year(values=[("device_id1", 1990)])

    expected_resp_body = {"birthyear": 1990}

    phone_number = "+0012345678"

    resp = await http_client.fetch(
        f"{base_url}/birthyear/{phone_number}", **fhi_get_req
    )

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body


async def test_birth_year_handler_happy_no_birth_year(
    http_client, base_url, db_user_serviceapi, find_user_mock, device_ids_mock,
):
    expected_resp_body = {"birthyear": None}

    phone_number = "+0012345678"

    resp = await http_client.fetch(
        f"{base_url}/birthyear/{phone_number}", **fhi_get_req
    )

    assert resp.code == 200
    assert json.loads(resp.body) == expected_resp_body


async def test_birth_year_handler_no_user(
    http_client,
    base_url,
    db_user_serviceapi,
    find_user_none_mock,
    device_ids_single_mock,
):
    phone_number = "+0012345678"

    with pytest.raises(tornado.httpclient.HTTPClientError) as e:
        await http_client.fetch(f"{base_url}/birthyear/{phone_number}", **fhi_get_req)
    assert e.value.code == 400
