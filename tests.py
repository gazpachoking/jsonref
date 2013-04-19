from copy import deepcopy
import operator
import json

try:
    from unittest import mock
except ImportError:
    import mock

import pytest

from jsonref import PY3, replace_json_refs, loads, load, Dereferencer
from lazyproxy import Proxy, CallbackProxy, LazyProxy

if PY3:
    long = int
    div = operator.truediv
    idiv = operator.itruediv
    def cmp(a, b):
        return (a > b) - (a < b)
else:
    div = operator.div
    idiv = operator.idiv


class TestRefLoading(object):

    def test_local_ref(self):
        json = {"a": 5, "b": {"$ref": "#/a"}}
        assert replace_json_refs(json)["b"] == json["a"]

    def test_custom_dereferencer(self):
        data = {"$ref": "foo"}
        dereferencer = mock.Mock(return_value=42)
        result = replace_json_refs(data, deref=dereferencer)
        # Dereferencing should not occur until we do something with result
        assert dereferencer.call_count == 0
        # Make sure we got the right result
        assert result == 42
        # Do several things with result
        result + 3
        repr(result)
        result *= 2
        # Make sure we only called the dereferencer once
        dereferencer.assert_called_once_with("foo")

    def test_loads(self):
        json = """{"a": 1, "b": {"$ref": "#/a"}}"""
        assert loads(json) == {"a": 1, "b": 1}

    def test_load(self, tmpdir):
        json = """{"a": 1, "b": {"$ref": "#/a"}}"""
        tmpdir.join("out.json").write(json)
        assert load(tmpdir.join("out.json")) == {"a": 1, "b": 1}

    def test_base_uri_resolution(self):
        json = {"$ref": "foo"}
        dereferencer = mock.Mock(return_value=17)
        result = replace_json_refs(
            json, base_uri="http://bar.com", deref=dereferencer
        )
        assert result == 17
        dereferencer.assert_called_once_with("http://bar.com/foo")

    def test_repr_does_not_loop_by_default(self):
        json = {"a": ["aoeu", {"$ref": "#/a"}]}
        assert (
            repr(replace_json_refs(json)) ==
            "{'a': ['aoeu', ['aoeu', JsonRef{'$ref': '#/a'}]]}"
        )

    def test_repr_expands_deep_refs_by_default(self):
        json = {
            "a": "string", "b": {"$ref": "#/a"}, "c": {"$ref": "#/b"},
            "d": {"$ref": "#/c"}, "e": {"$ref": "#/d"}, "f": {"$ref": "#/e"}
        }
        assert (
            repr(sorted(replace_json_refs(json).items())) ==
            "[('a', 'string'), ('b', 'string'), ('c', 'string'), "
            "('d', 'string'), ('e', 'string'), ('f', 'string')]"
        )
        # Should not expand when set to False explicitly
        result = replace_json_refs(json, load_on_repr=False)
        assert (
            repr(sorted(result.items())) ==
            "[('a', 'string'), ('b', JsonRef{'$ref': '#/a'}), "
            "('c', JsonRef{'$ref': '#/b'}), ('d', JsonRef{'$ref': '#/c'}), "
            "('e', JsonRef{'$ref': '#/d'}), ('f', JsonRef{'$ref': '#/e'})]"
        )


class TestDereferencer(object):

    base_uri = ""
    stored_uri = "foo://stored"
    stored_schema = {"stored": "schema"}

    @pytest.fixture(scope="function", autouse=True)
    def deferencer(self):
        self.store = {self.stored_uri: self.stored_schema}
        self.dereferencer = Dereferencer(store=self.store)

    def test_it_retrieves_stored_refs(self):
        result = self.dereferencer(self.stored_uri)
        assert result is self.stored_schema

    def test_it_retrieves_unstored_refs_via_requests(self):
        ref = "http://bar"
        data = {"baz" : 12}

        with mock.patch("jsonref.requests") as requests:
            requests.get.return_value.json.return_value = data
            result = self.dereferencer(ref)
            assert result == data
        requests.get.assert_called_once_with("http://bar")

    def test_it_retrieves_unstored_refs_via_urlopen(self):
        ref = "http://bar"
        data = {"baz" : 12}

        with mock.patch("jsonref.requests", None):
            with mock.patch("jsonref.urlopen") as urlopen:
                urlopen.return_value.read.return_value = (
                    json.dumps(data).encode("utf8")
                )
                result = self.dereferencer(ref)
                assert result == data
        urlopen.assert_called_once_with("http://bar")

    def test_cache_results_on(self):
        ref = "http://bar"
        data = {"baz" : 12}

        with mock.patch("jsonref.requests") as requests:
            requests.get.return_value.json.return_value = data
            dereferencer = Dereferencer(cache_results=True)
            dereferencer(ref)
            dereferencer(ref)
        requests.get.assert_called_once_with(ref)

    def test_cache_results_off(self):
        ref = "http://bar"
        data = {"baz" : 12}

        with mock.patch("jsonref.requests") as requests:
            requests.get.return_value.json.return_value = data
            dereferencer = Dereferencer(cache_results=False)
            dereferencer(ref)
            dereferencer(ref)
        assert requests.get.call_count == 2



_unset = object()


class TestProxies(object):
    @pytest.fixture(
        scope="class", autouse=True,
        params=["Proxy", "CallbackProxy", "LazyProxy"]
    )
    def make_proxify(self, request):
        def proxify(val):
            c = deepcopy(val)
            if request.param == "Proxy":
                return Proxy(c)
            globals().get(request.param)
            return globals().get(request.param)(lambda: c)
        self.proxify = proxify
        return proxify

    def proxify(self, v):
        c = deepcopy(v)
        return LazyProxy(lambda: c)

    def check_func(self, func, value, other=_unset):
        """
        Checks func works the same with `value` as when `value` is proxied.

        """

        p = self.proxify(value)
        args = []
        if other is not _unset:
            args = [other]
        try:
            result = func(value, *args)
        except Exception as e:
            with pytest.raises(type(e)):
                func(p, *args)
        else:
            assert func(p, *args) == result
        # If this func takes two arguments, try them reversed as well
        if other is not _unset:
            try:
                result = func(other, value)
            except Exception as e:
                with pytest.raises(type(e)):
                    func(other, p)
            else:
                assert func(other, p) == result

    def check_integer(self, v):
        for op in (
            operator.and_, operator.or_, operator.xor,
            operator.iand, operator.ior, operator.ixor
        ):
            self.check_func(op, v, 0b10101)
        for op in (
            operator.lshift, operator.rshift,
            operator.ilshift, operator.irshift
        ):
            self.check_func(op, v, 3)
        for op in (operator.invert, hex, oct):
            self.check_func(op, v)

        self.check_numeric(v)

    def check_numeric(self, v):
        for op in (
            operator.pos, operator.neg, abs, int, long, float, hash, complex
        ):
            self.check_func(op, v)

        for other in (5, 13.7):  # Check against both an int and a float
            for op in(
                # Math
                operator.mul, operator.pow, operator.add, operator.sub, div,
                operator.truediv, operator.floordiv, operator.mod, divmod,
                # In-place
                operator.imul, operator.ipow, operator.iadd, operator.isub,
                idiv, operator.itruediv, operator.ifloordiv, operator.imod,
                # Comparison
                operator.lt, operator.le, operator.gt, operator.ge,
                operator.eq, operator.ne, cmp
            ):
                self.check_func(op, v, other)

        self.check_basics(v)

    def check_list(self, v):
        p = self.proxify(v)
        for i in range(len(v)):
            for arg in (i, slice(i), slice(None, i), slice(i, None, -1)):
                self.check_func(operator.getitem, v, arg)
        self.check_container(v)

        c = list(v)
        del p[::2]
        del c[::2]
        assert p == c

        p[1:1] = [23]
        c[1:1] = [23]
        assert p == c

        p.insert(1, 0)
        c.insert(1, 0)
        assert p == c

        p += [4]
        c += [4]
        assert p == c

    def check_container(self, v):
        for op in (list, set, len, lambda x: list(iter(x))):
            self.check_func(op, v)
        self.check_basics(v)

    def check_basics(self, v):
        for f in bool, repr, str:
            self.check_func(f, v)

    def test_numbers(self):
        for i in range(20):
            self.check_integer(i)

        f = -40
        while f <= 20.0:
            self.check_numeric(f)
            f += 2.25

    def test_lists(self):
        for l in [1,2], [3,42,59], [99,23,55], ["a", "b", 1.4, 17.3, -3, 42]:
            self.check_list(l)

    def test_dicts(self):
        for d in ({"a": 3, 4: 2, 1.5: "b"}, {}, {"": ""}):
            self.check_container(d)

    def test_immutable(self):
        a = self.proxify(3)
        b = a
        b += 3
        assert a == 3
        assert b == 6

    def test_mutable(self):
        a = self.proxify([0])
        b = a
        b += [1]
        assert a == [0, 1]
        assert b == [0, 1]

    def test_attributes(self):
        class C(object):
            def __init__(self):
                self.attribute = 'value'
        v = C()
        p = self.proxify(v)
        p.attribute = 'aoeu'
        v.attribute = 'aoeu'
        assert p.__subject__.attribute == v.attribute
        del p.attribute
        del v.attribute
        assert not hasattr(v, 'attribute')
        assert not hasattr(p, 'attribute')

    def test_call(self):
        func = lambda a: a * 2
        p = self.proxify(func)
        assert p(5) == func(5)

    def test_subject_attribute(self):
        # Test getting subject
        v = ['aoeu']
        p = LazyProxy(lambda: v)
        assert p.__subject__ is v
        # Test setting subject
        v2 = 'aoeu'
        p.__subject__ = v2
        assert p == v2

    def test_subclass_attributes(self):
        class C(LazyProxy):
            __notproxied__ = ("class_attr",)
            class_attr = "aoeu"
        c = C(lambda: 3)
        # Make sure proxy functionality still works
        assert c == 3
        # Make sure subclass attr is accessible
        assert c.class_attr == "aoeu"
        # Make sure instance attribute is set on proxy
        c.class_attr = "htns"
        assert c.class_attr == "htns"
        assert not hasattr(c.__subject__, "class_attr")
        # Test instance attribute is deleted from proxy
        del c.class_attr
        assert c.class_attr == "aoeu"

    def test_no_proxy_during_subclass_methods(self):
        class A(LazyProxy):
            def setter(self, value):
                self.attr = value

        class C(A):
            __notproxied__ = ("getter", "setter", "__eq__")
            def __init__(self, value):
                self.attr = 5
                super(C, self).__init__(lambda: value)
            def __equal__(self, other):
                return False
            @property
            def getter(self):
                return self.attr
            def setter(self, value):
                super(C, self).setter(value)
            @LazyProxy.notproxied
            def decorated(self):
                return 2.0
            @property
            @LazyProxy.notproxied
            def decorated_prop(self):
                return 3.0

        C.getter2 = C.notproxied(lambda self: self.attr)

        c = C("proxied")
        # Make sure super works
        assert c == "proxied"
        # The instance properties and methods should be able to read and write
        # attributes to self without any proxying
        assert c.getter == 5
        c.setter("aoeu")
        assert c.getter == "aoeu"
        # Even if they are added after the class is created
        assert c.getter2() == "aoeu"
        # The decorated methods and properties should automatically be added to
        # the __notproxied__ list
        assert "decorated" in C.__notproxied__
        assert c.decorated() == 2.0
        assert "decorated_prop" in C.__notproxied__
        assert c.decorated_prop == 3.0
        # Outside the methods it should still be proxied (str has no 'attr')
        with pytest.raises(AttributeError):
            c.attr = 1
        with pytest.raises(AttributeError):
            c.attr

