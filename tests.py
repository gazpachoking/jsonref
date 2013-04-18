from copy import deepcopy
import operator
import json
import sys
import unittest

if sys.version_info[:2] < (2, 7):
    import unittest2 as unittest
else:
    import unittest

try:
    from unittest import mock
except ImportError:
    import mock

from jsonref import PY3, loadp, loads, Dereferencer
from lazyproxy import LazyProxy

if PY3:
    long = int
    div = operator.truediv
    idiv = operator.itruediv
    def cmp(a, b):
        return (a > b) - (a < b)
else:
    div = operator.div
    idiv = operator.idiv


class TestRefLoading(unittest.TestCase):

    def test_local_ref(self):
        json = {"a": 5, "b": {"$ref": "#/a"}}
        self.assertEqual(loadp(json)["b"], json["a"])

    def test_custom_dereferencer(self):
        data = {"$ref": "foo"}
        dereferencer = mock.Mock(return_value=42)
        result = loadp(data, dereferencer=dereferencer)
        # Dereferencing should not occur until we do something with result
        self.assertEqual(dereferencer.call_count, 0)
        # Make sure we got the right result
        self.assertEqual(result, 42)
        # Do several things with result
        result + 3
        repr(result)
        result *= 2
        # Make sure we only called the dereferencer once
        dereferencer.assert_called_once_with("foo")

    def test_loads(self):
        json = """{"a": 1, "b": {"$ref": "#/a"}}"""
        self.assertEqual(loads(json), {"a": 1, "b": 1})

    def test_base_uri_resolution(self):
        json = {"$ref": "foo"}
        dereferencer = mock.Mock(return_value=None)
        result = loadp(
            json, base_uri="http://bar.com", dereferencer=dereferencer
        )
        self.assertEqual(result, None)
        dereferencer.assert_called_once_with("http://bar.com/foo")


class TestDereferencer(unittest.TestCase):

    base_uri = ""
    stored_uri = "foo://stored"
    stored_schema = {"stored" : "schema"}

    def setUp(self):
        self.store = {self.stored_uri : self.stored_schema}
        self.dereferencer = Dereferencer(store=self.store)

    def test_it_retrieves_stored_refs(self):
        result = self.dereferencer(self.stored_uri)
        self.assertIs(result, self.stored_schema)

    def test_it_retrieves_unstored_refs_via_requests(self):
        ref = "http://bar"
        data = {"baz" : 12}

        with mock.patch("jsonref.requests") as requests:
            requests.get.return_value.json.return_value = data
            result = self.dereferencer(ref)
            self.assertEqual(result, data)
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
                self.assertEqual(result, data)
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
        self.assertEqual(requests.get.call_count, 2)


_unset = object()


class TestLazyProxy(unittest.TestCase):
    def proxied(self, v):
        c = deepcopy(v)
        return LazyProxy(lambda: c)

    def check_func(self, func, value, other=_unset):
        """
        Checks func works the same with `value` as when `value` is proxied.

        """

        p = self.proxied(value)
        args = []
        if other is not _unset:
            args = [other]
        try:
            result = func(value, *args)
        except Exception as e:
            with self.assertRaises(type(e)):
                func(p, *args)
        else:
            self.assertEqual(func(p, *args), result)
        # If this func takes two arguments, try them reversed as well
        if other is not _unset:
            try:
                result = func(other, value)
            except Exception as e:
                with self.assertRaises(type(e)):
                    func(other, p)
            else:
                self.assertEqual(
                    func(other, p), result,
                    "func: %r, other: %r, p: %r" % (func, other, p)
                )

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
        p = self.proxied(v)
        for i in range(len(v)):
            for arg in (i, slice(i), slice(None, i), slice(i, None, -1)):
                self.check_func(operator.getitem, v, arg)
        self.check_container(v)

        c = list(v)
        del p[::2]
        del c[::2]
        self.assertEqual(p, c)

        p[1:1] = [23]
        c[1:1] = [23]
        self.assertEqual(p, c)

        p.insert(1, 0)
        c.insert(1, 0)
        self.assertEqual(p, c)

        p += [4]
        c += [4]
        self.assertEqual(p, c)

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
        a = self.proxied(3)
        b = a
        b += 3
        self.assertEqual(a, 3)
        self.assertEqual(b, 6)

    def test_mutable(self):
        a = self.proxied([0])
        b = a
        b += [1]
        self.assertEqual(a, [0, 1])
        self.assertEqual(b, [0, 1])

    def test_attributes(self):
        class C(object):
            def __init__(self):
                self.attribute = 'value'
        v = C()
        p = self.proxied(v)
        p.attribute = 'aoeu'
        v.attribute = 'aoeu'
        self.assertEqual(p.__subject__.attribute, v.attribute)
        del p.attribute
        del v.attribute
        self.assertFalse(hasattr(v, 'attribute'))
        self.assertFalse(hasattr(p, 'attribute'))

    def test_call(self):
        func = lambda a: a * 2
        p = self.proxied(func)
        self.assertEqual(p(5), func(5))

    def test_subject_attribute(self):
        # Test getting subject
        v = ['aoeu']
        p = LazyProxy(lambda: v)
        self.assertIs(p.__subject__, v)
        # Test setting subject
        v2 = 'aoeu'
        p.__subject__ = v2
        self.assertEqual(p, v2)

    def test_subclass_attributes(self):
        class C(LazyProxy):
            __notproxied__ = ("class_attr",)
            class_attr = "aoeu"
        c = C(lambda: 3)
        # Make sure proxy functionality still works
        self.assertEqual(c, 3)
        # Make sure subclass attr is accessible
        self.assertEqual(c.class_attr, "aoeu")
        # Make sure instance attribute is set on proxy
        c.class_attr = "htns"
        self.assertEqual(c.class_attr, "htns")
        self.assertFalse(hasattr(c.__subject__, "class_attr"))
        # Test instance attribute is deleted from proxy
        del c.class_attr
        self.assertEqual(c.class_attr, "aoeu")

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
        self.assertEqual(c, "proxied")
        # The instance properties and methods should be able to read and write
        # attributes to self without any proxying
        self.assertEqual(c.getter, 5)
        c.setter("aoeu")
        self.assertEqual(c.getter, "aoeu")
        # Even if they are added after the class is created
        self.assertEqual(c.getter2(), "aoeu")
        # The decorated methods and properties should automatically be added to
        # the __notproxied__ list
        self.assertIn("decorated", C.__notproxied__)
        self.assertEqual(c.decorated(), 2.0)
        self.assertIn("decorated_prop", C.__notproxied__)
        self.assertEqual(c.decorated_prop, 3.0)
        # Outside the methods it should still be proxied (str has no 'attr')
        with self.assertRaises(AttributeError):
            c.attr = 1
        with self.assertRaises(AttributeError):
            c.attr

