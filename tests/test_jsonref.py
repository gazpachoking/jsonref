import functools
import itertools
from unittest import mock
import pytest

from jsonref import (
    JsonRef,
    JsonRefError,
    _walk_refs,
    replace_refs,
)


def cmp(a, b):
    return (a > b) - (a < b)


@pytest.fixture(
    params=[{"lazy_load": True}, {"lazy_load": False}, {"proxies": False}],
    ids=["lazy_load", "no lazy_load", "no proxies"],
)
def parametrized_replace_refs(request):
    return functools.partial(replace_refs, **request.param)


class TestJsonRef(object):
    def test_non_ref_object_throws_error(self):
        with pytest.raises(ValueError):
            JsonRef({"ref": "aoeu"})

    def test_non_string_is_not_ref(self, parametrized_replace_refs):
        json = {"$ref": [1]}
        assert parametrized_replace_refs(json) == json

    def test_local_object_ref(self, parametrized_replace_refs):
        json = {"a": 5, "b": {"$ref": "#/a"}}
        assert parametrized_replace_refs(json)["b"] == json["a"]

    def test_local_array_ref(self, parametrized_replace_refs):
        json = [10, {"$ref": "#/0"}]
        assert parametrized_replace_refs(json)[1] == json[0]

    def test_local_mixed_ref(self, parametrized_replace_refs):
        json = {"a": [5, 15], "b": {"$ref": "#/a/1"}}
        assert parametrized_replace_refs(json)["b"] == json["a"][1]

    def test_local_escaped_ref(self, parametrized_replace_refs):
        json = {"a/~a": ["resolved"], "b": {"$ref": "#/a~1~0a"}}
        assert parametrized_replace_refs(json)["b"] == json["a/~a"]

    def test_local_nonexistent_ref(self):
        json = {
            "data": [1, 2],
            "a": {"$ref": "#/x"},
            "b": {"$ref": "#/0"},
            "c": {"$ref": "#/data/3"},
            "d": {"$ref": "#/data/b"},
        }
        result = replace_refs(json)
        for key in "abcd":
            with pytest.raises(JsonRefError):
                result[key].__subject__

    def test_actual_references_not_copies(self):
        json = {
            "a": ["foobar"],
            "b": {"$ref": "#/a"},
            "c": {"$ref": "#/a"},
            "d": {"$ref": "#/c"},
        }
        result = replace_refs(json)
        assert result["b"].__subject__ is result["a"]
        assert result["c"].__subject__ is result["a"]
        assert result["d"].__subject__ is result["a"]

    def test_merge_extra_flag(self, parametrized_replace_refs):
        json = {
            "a": {"main": 1},
            "b": {"$ref": "#/a", "extra": 2},
        }
        no_extra = parametrized_replace_refs(json, merge_props=False)
        assert no_extra == {"a": {"main": 1}, "b": {"main": 1}}
        extra = parametrized_replace_refs(json, merge_props=True)
        assert extra == {"a": {"main": 1}, "b": {"main": 1, "extra": 2}}

    def test_extra_ref_attributes(self, parametrized_replace_refs):
        json = {
            "a": {"type": "object", "properties": {"foo": {"type": "string"}}},
            "b": {"extra": "foobar", "$ref": "#/a"},
            "c": {"extra": {"more": "bar", "$ref": "#/a"}},
        }
        result = parametrized_replace_refs(json, load_on_repr=False, merge_props=True)
        assert result["b"] == {
            "extra": "foobar",
            "type": "object",
            "properties": {"foo": {"type": "string"}},
        }
        assert result["c"] == {
            "extra": {
                "more": "bar",
                "type": "object",
                "properties": {"foo": {"type": "string"}},
            }
        }

    def test_refs_inside_extra_props(self, parametrized_replace_refs):
        """This seems really dubious per the spec... but OpenAPI 3.1 spec does it."""
        docs = {
            "a.json": {
                "file": "a",
                "b": {"$ref": "b.json#/ba", "extra": {"$ref": "b.json#/bb"}},
            },
            "b.json": {"ba": {"a": 1}, "bb": {"b": 2}},
        }
        result = parametrized_replace_refs(
            docs["a.json"], loader=docs.get, merge_props=True
        )
        assert result == {"file": "a", "b": {"a": 1, "extra": {"b": 2}}}

    def test_recursive_extra(self, parametrized_replace_refs):
        json = {"a": {"$ref": "#", "extra": "foo"}}
        result = parametrized_replace_refs(json, merge_props=True)
        assert result["a"]["a"]["extra"] == "foo"
        assert result["a"]["a"] is result["a"]["a"]["a"]

    def test_extra_sibling_attributes_list_ref(self, parametrized_replace_refs):
        json = {
            "a": ["target"],
            "b": {"extra": "foobar", "$ref": "#/a"},
        }
        result = parametrized_replace_refs(json, merge_props=True)
        assert result["b"] == result["a"]

    def test_separate_extras(self, parametrized_replace_refs):
        json = {
            "a": {"main": 1234},
            "x": {"$ref": "#/a", "extrax": "x"},
            "y": {"$ref": "#/a", "extray": "y"},
            "z": {"$ref": "#/y", "extraz": "z"},
        }
        result = parametrized_replace_refs(json, merge_props=True)
        assert result == {
            "a": {"main": 1234},
            "x": {"main": 1234, "extrax": "x"},
            "y": {"main": 1234, "extray": "y"},
            "z": {"main": 1234, "extraz": "z", "extray": "y"},
        }

    def test_lazy_load(self):
        json = {
            "a": {"$ref": "#/fake"},
        }
        # No errors should be raised when we replace the references
        result = replace_refs(json, lazy_load=True)
        assert result["a"].__reference__ == json["a"]
        # The error should happen when we access the attribute
        with pytest.raises(JsonRefError):
            result["a"].__subject__

    def test_no_lazy_load(self):
        json = {
            "a": {"$ref": "#/fake"},
        }
        # Error should raise straight away without lazy loading
        with pytest.raises(JsonRefError):
            replace_refs(json, lazy_load=False)

    def test_no_lazy_load_recursive(self):
        json = {
            "a": {"1": {"$ref": "#/b"}},
            "b": {"$ref": "#/a"},
        }
        # If resolution happens too early, the recursion won't work
        # Make sure we don't break recursion when we aren't being lazy
        replace_refs(json, lazy_load=False)

    def test_proxies(self):
        json = {
            "a": [1],
            "b": {"$ref": "#/a"},
        }
        result = replace_refs(json, proxies=True)
        assert result["b"].__reference__
        assert result["b"].__subject__ is result["a"]

    def test_no_proxies(self):
        json = {
            "a": [1],
            "b": {"$ref": "#/a"},
        }
        result = replace_refs(json, proxies=False)
        assert result["b"] is result["a"]

    def test_walk_refs(self):
        docs = {
            "a.json": {"file": "a", "b": {"$ref": "b.json"}},
            "b.json": {"file": "b", "c": {"$ref": "c.json"}},
            "c.json": {"file": "c"},
        }
        test_func = mock.Mock()
        res = replace_refs(docs["a.json"], loader=docs.get)
        _walk_refs(res, test_func)
        # Make sure it followed the refs through documents
        assert test_func.call_count == 2

    def test_multi_doc_no_proxies(self):
        docs = {
            "a.json": {"file": "a", "b": {"$ref": "b.json"}},
            "b.json": {"file": "b", "c": {"$ref": "c.json"}},
            "c.json": {"file": "c"},
        }
        test_func = mock.Mock()
        res = replace_refs(docs["a.json"], loader=docs.get, proxies=False)
        _walk_refs(res, test_func)
        # Make sure there aren't any JsonRefs left
        assert test_func.call_count == 0
        assert res == {"file": "a", "b": {"file": "b", "c": {"file": "c"}}}

    def test_recursive_data_structures_local(self):
        json = {"a": "foobar", "b": {"$ref": "#"}}
        result = replace_refs(json)
        assert result["b"].__subject__ is result

    def test_recursive_data_structures_remote(self):
        json1 = {"a": {"$ref": "/json2"}}
        json2 = {"b": {"$ref": "/json1"}}
        loader = lambda uri: {"/json1": json1, "/json2": json2}[uri]
        result = replace_refs(
            json1, base_uri="/json1", loader=loader, load_on_repr=False
        )
        assert result["a"]["b"].__subject__ is result
        assert result["a"].__subject__ is result["a"]["b"]["a"].__subject__

    def test_recursive_data_structures_remote_fragment(self):
        json1 = {"a": {"$ref": "/json2#/b"}}
        json2 = {"b": {"$ref": "/json1"}}
        loader = mock.Mock(return_value=json2)
        result = replace_refs(json1, base_uri="/json1", loader=loader)
        assert result["a"].__subject__ is result

    def test_self_referent_reference(self, parametrized_replace_refs):
        json = {"$ref": "#/sub", "sub": [1, 2]}
        result = parametrized_replace_refs(json)
        assert result == json["sub"]

    def test_self_referent_reference_w_merge(self, parametrized_replace_refs):
        json = {"$ref": "#/sub", "extra": "aoeu", "sub": {"main": "aoeu"}}
        result = parametrized_replace_refs(json, merge_props=True)
        assert result == {"main": "aoeu", "extra": "aoeu", "sub": {"main": "aoeu"}}

    def test_custom_loader(self):
        data = {"$ref": "foo"}
        loader = mock.Mock(return_value=42)
        result = replace_refs(data, loader=loader)
        # Loading should not occur until we do something with result
        assert loader.call_count == 0
        # Make sure we got the right result
        assert result == 42
        # Do several more things with result
        result + 3
        repr(result)
        result *= 2
        # Make sure we only called the loader once
        loader.assert_called_once_with("foo")

    def test_base_uri_resolution(self, parametrized_replace_refs):
        json = {"$ref": "foo"}
        loader = mock.Mock(return_value=17)
        result = parametrized_replace_refs(
            json, base_uri="http://bar.com", loader=loader
        )
        assert result == 17
        loader.assert_called_once_with("http://bar.com/foo")

    def test_repr_does_not_loop(self):
        json = {"a": ["aoeu", {"$ref": "#/a"}]}
        # By default, python repr recursion detection should handle it
        assert repr(replace_refs(json)) == "{'a': ['aoeu', [...]]}"
        # If we turn of load_on_repr we should get a different representation
        assert (
            repr(replace_refs(json, load_on_repr=False))
            == "{'a': ['aoeu', JsonRef({'$ref': '#/a'})]}"
        )

    def test_repr_expands_deep_refs_by_default(self):
        json = {
            "a": "string",
            "b": {"$ref": "#/a"},
            "c": {"$ref": "#/b"},
            "d": {"$ref": "#/c"},
            "e": {"$ref": "#/d"},
            "f": {"$ref": "#/e"},
        }
        assert (
            repr(sorted(replace_refs(json).items()))
            == "[('a', 'string'), ('b', 'string'), ('c', 'string'), "
            "('d', 'string'), ('e', 'string'), ('f', 'string')]"
        )
        # Should not expand when set to False explicitly
        result = replace_refs(json, load_on_repr=False)
        assert (
            repr(sorted(result.items()))
            == "[('a', 'string'), ('b', JsonRef({'$ref': '#/a'})), "
            "('c', JsonRef({'$ref': '#/b'})), ('d', JsonRef({'$ref': '#/c'})), "
            "('e', JsonRef({'$ref': '#/d'})), ('f', JsonRef({'$ref': '#/e'}))]"
        )

    def test_jsonschema_mode_local(self, parametrized_replace_refs):
        json = {
            "a": {
                "id": "http://foo.com/schema",
                "b": "aoeu",
                # Reference should now be relative to this inner object, rather
                # than the whole document
                "c": {"$ref": "#/b"},
            }
        }
        result = parametrized_replace_refs(json, jsonschema=True)
        assert result["a"]["c"] == json["a"]["b"]

    def test_jsonschema_mode_remote(self):
        base_uri = "http://foo.com/schema"
        json = {
            "a": {"$ref": "otherSchema"},
            "b": {
                "id": "http://bar.com/a/schema",
                "c": {"$ref": "otherSchema"},
                "d": {"$ref": "/otherSchema"},
                "e": {"id": "/b/schema", "$ref": "otherSchema"},
            },
        }
        counter = itertools.count()
        loader = mock.Mock(side_effect=lambda uri: next(counter))
        result = replace_refs(json, loader=loader, base_uri=base_uri, jsonschema=True)
        assert result["a"] == 0
        loader.assert_called_once_with("http://foo.com/otherSchema")
        loader.reset_mock()
        assert result["b"]["c"] == 1
        loader.assert_called_once_with("http://bar.com/a/otherSchema")
        loader.reset_mock()
        assert result["b"]["d"] == 2
        loader.assert_called_once_with("http://bar.com/otherSchema")
        loader.reset_mock()
        assert result["b"]["e"] == 3
        loader.assert_called_once_with("http://bar.com/b/otherSchema")

    def test_jsonref_mode_non_string_is_not_id(self, parametrized_replace_refs):
        base_uri = "http://foo.com/json"
        json = {"id": [1], "$ref": "other"}
        loader = mock.Mock(return_value="aoeu")
        result = parametrized_replace_refs(json, base_uri=base_uri, loader=loader)
        assert result == "aoeu"
        loader.assert_called_once_with("http://foo.com/other")

    def test_cache_loader_results(self, parametrized_replace_refs):
        loader = mock.Mock()
        loader.return_value = 1234
        json = {"a": {"$ref": "mock://aoeu"}, "b": {"$ref": "mock://aoeu"}}

        result = parametrized_replace_refs(json, loader=loader)
        assert result == {"a": 1234, "b": 1234}
        loader.assert_called_once_with("mock://aoeu")
