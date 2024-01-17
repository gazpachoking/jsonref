import json
from unittest import mock
from jsonref import jsonloader


class TestJsonLoader(object):
    def test_it_retrieves_refs_via_requests(self):
        ref = "http://bar"
        data = {"baz": 12}

        with mock.patch("jsonref.requests") as requests:
            requests.get.return_value.json.return_value = data
            result = jsonloader(ref)
            assert result == data
        requests.get.assert_called_once_with("http://bar")

    def test_it_retrieves_refs_via_urlopen(self):
        ref = "http://bar"
        data = {"baz": 12}

        with mock.patch("jsonref.requests", None):
            with mock.patch("jsonref.urlopen") as urlopen:
                urlopen.return_value.__enter__.return_value.read.return_value = (
                    json.dumps(data).encode("utf8")
                )
                result = jsonloader(ref)
                assert result == data
        urlopen.assert_called_once_with("http://bar")
