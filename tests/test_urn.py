import jsonref
import pytest


class TestURN(object):

    def test_basic_urn_ref(self):
        """A basic test that has a starting file that references a second file by URN"""

        start = {
            "$id": "urn:start",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"address": {"$ref": "urn:address"}},
        }

        def _jsonref_loader(uri):
            if uri == "urn:address":
                return {
                    "$id": "urn:address",
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "type": "object",
                    "properties": {
                        "address": {"type": "string"},
                        "country": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}},
                        },
                    },
                }
            return jsonref.jsonloader(uri)

        out = jsonref.JsonRef.replace_refs(start, loader=_jsonref_loader)

        assert out["properties"]["address"]["type"] == "object"
        assert out["properties"]["address"]["properties"]["address"]["type"] == "string"
        assert out["properties"]["address"]["properties"]["country"]["type"] == "object"
        assert (
            out["properties"]["address"]["properties"]["country"]["properties"]["code"][
                "type"
            ]
            == "string"
        )

    @pytest.mark.parametrize("include_urn_lib_the_second_time", [(True), (False)])
    def test_two_refs_deep(self, include_urn_lib_the_second_time):
        """
        A test that has a starting file that references part of a library file by URN.
        In this library file, there is a bit of code that references another part of the library file.
        """

        start = {
            "$id": "urn:start",
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"address": {"$ref": "urn:lib#/$defs/address"}},
        }

        def _jsonref_loader(uri):
            if uri == "urn:lib":
                return {
                    "$id": "urn:lib",
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "$defs": {
                        "address": {
                            "type": "object",
                            "properties": {
                                "address": {"type": "string"},
                                "country": {
                                    "$ref": (
                                        "urn:lib#/$defs/country"
                                        if include_urn_lib_the_second_time
                                        else "#/$defs/country"
                                    )
                                },
                            },
                        },
                        "country": {
                            "type": "object",
                            "properties": {"code": {"type": "string"}},
                        },
                    },
                }
            return jsonref.jsonloader(uri)

        out = jsonref.JsonRef.replace_refs(start, loader=_jsonref_loader)

        assert out["properties"]["address"]["type"] == "object"
        assert out["properties"]["address"]["properties"]["address"]["type"] == "string"
        assert out["properties"]["address"]["properties"]["country"]["type"] == "object"
        assert (
            out["properties"]["address"]["properties"]["country"]["properties"]["code"][
                "type"
            ]
            == "string"
        )
