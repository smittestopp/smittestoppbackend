class LookupHandlerRedisMock(object):

    expected_rpush_args = [
        (
            "analysis-jobs",
            b"""{"request_id": "1234", "device_id": "device_id1", "result_key": "lookup:1234:result:device_id1", "time_from": null, "time_to": null, "expiry": 14400}""",
        ),
        (
            "analysis-jobs",
            b'{"request_id": "1234", "device_id": "device_id2", "result_key": "lookup:1234:result:device_id2", "time_from": null, "time_to": null, "expiry": 14400}',
        ),
    ]
    expected_set_args = [
        (
            "lookup:1234:info",
            '{"phone_number": "+0012341234", "result_keys": ["lookup:1234:result:device_id1", "lookup:1234:result:device_id2"], "device_ids": ["device_id1", "device_id2"]}',
        )
    ]
    expected_set_kwargs = [{"ex": 14400}]

    def __init__(self):
        self._n_rpush_calls = 0
        self._n_set_calls = 0

    def rpush(self, *args, **kwargs):
        assert args == self.expected_rpush_args[self._n_rpush_calls]
        assert kwargs == {}
        self._n_rpush_calls += 1

    def set(self, *args, **kwargs):
        assert args == self.expected_set_args[self._n_set_calls]
        assert kwargs == self.expected_set_kwargs[self._n_set_calls]


class LookupResultsHandlerRedisMock(object):

    expected_exists_args = [
        ("result_key_1", "result_key_2", "result_key_3"),
    ]
    expected_mget_args = [
        ("result_key_1", "result_key_2", "result_key_3"),
    ]
    expected_get_args = [
        ("lookup:1234:info",),
    ]

    exits_return_values = [
        3,
    ]
    get_return_values = [
        b"""
        {
            "device_ids":[
                "device_id_1",
                "device_id_2", 
                "device_id_3"
            ], 
            "phone_number":"+4712341234", 
            "result_keys":[
                "result_key_1",
                "result_key_2",
                "result_key_3"
            ]
        }"""
    ]
    mget_return_values = [
        [
            b"""
            {
                "status": "success", 
                "device_id": "1337", 
                "request_id": "42", 
                "result": {
                    "result_key_1": {"foo":"bar"}, 
                    "result_key_2": {"foo":"baz"}, 
                    "result_key_3": {"foo":"lol"}
                }
            }"""
        ]
    ]

    def __init__(self):
        self._n_exists_calls = 0
        self._n_mget_calls = 0
        self._n_get_calls = 0

    def exists(self, *args, **kwargs):
        assert args == self.expected_exists_args[self._n_exists_calls]
        assert kwargs == {}
        output = self.exits_return_values[self._n_exists_calls]
        self._n_exists_calls += 1
        return output

    def get(self, *args, **kwargs):
        assert args == self.expected_get_args[self._n_get_calls]
        assert kwargs == {}
        output = self.get_return_values[self._n_get_calls]
        self._n_get_calls += 1
        return output

    def mget(self, *args, **kwargs):
        assert args == self.expected_mget_args[self._n_mget_calls]
        assert kwargs == {}
        output = self.mget_return_values[self._n_mget_calls]
        self._n_mget_calls += 1
        return output


class LookupResultsHandlerRedisNoResultMock(object):
    def __init__(self):
        pass

    def get(self, *args, **kwargs):
        return None


class LookupResultsHandlerRedisAnalyisInProgressMock(object):
    def __init__(self):
        pass

    def get(self, *args, **kwargs):
        return b"""
        {
            "device_ids":[
                "device_id_1",
                "device_id_2"
            ], 
            "phone_number":"+4712341234", 
            "result_keys":[
                "result_key_1",
                "result_key_2"
            ]
        }"""

    def exists(self, *args, **kwargs):
        return 1


class LookupResultsHandlerRedisAnalyisErrorMock(object):
    def __init__(self):
        pass

    def get(self, *args, **kwargs):
        return b"""
        {
            "device_ids":[
                "device_id_1",
                "device_id_2"
            ],
            "phone_number":"+4712341234", 
            "result_keys":[
                "result_key_1",
                "result_key_2"
            ]
        }"""

    def exists(self, *args, **kwargs):
        return 2

    def mget(self, *args, **kwargs):
        return [
            b"""{
                "status": "error", 
                "message": "it failed", 
                "device_id": "1337", 
                "request_id": "42", 
                "result": {
                    "result_key_1": {"foo":"bar"}, 
                    "result_key_2": {"foo":"baz"}
                }
            }"""
        ]
