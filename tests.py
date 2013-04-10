import json
import sys
import unittest

import mock

from jsonref import loadp, loads, Dereferencer
from lazyproxy import LazyProxy

PY3 = sys.version_info[0] >= 3

if PY3:
    long = int
    def cmp(a, b):
        return (a > b) - (a < b)


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


class ProxyTestMixin:

    def checkInteger(self, v):
        p = self.proxied(v)
        self.assertEqual(p|0b010101, v|0b010101)
        self.assertEqual(p&0b010101, v&0b010101)
        self.assertEqual(p^0b010101, v^0b010101)
        self.assertEqual(~p, ~v)
        self.assertEqual(p<<3, v<<3)
        self.assertEqual(p>>2, v>>2)

        self.assertEqual(0b010101|p, 0b010101|v)
        self.assertEqual(0b010101&p, 0b010101&v)
        self.assertEqual(0b010101^p, 0b010101^v)
        self.assertEqual(3<<p, 3<<v)
        self.assertEqual(2>>p, 2>>v)
        for f in hex, oct:
            self.assertEqual(f(p), f(v))

        self.checkNumeric(v)

    def checkNumeric(self, v):
        p = self.proxied(v)
        self.assertEqual(p*2, v*2)
        self.assertEqual(2*p, 2*v)
        self.assertEqual(2**p, 2**v)
        self.assertEqual(p**2, v**2)
        self.assertEqual(-p, -v)
        self.assertEqual(+p, +v)
        for f in abs, int, long, float, hash, complex:
            self.assertEqual(f(p), f(v))
        self.assertEqual(p<22, v<22)
        self.assertEqual(p>=10, v>=10)
        self.assertEqual(p>9.0, v>9.0)
        self.assertEqual(p<=9.25, v<=9.25)
        self.assertEqual(p==7, v==7)
        self.assertEqual(p!=18, v!=18)

        self.assertEqual(16+p, 16+v)
        self.assertEqual(62-p, 62-v)
        self.assertEqual(p+16, v+16)
        self.assertEqual(p-62, v-62)
        self.assertEqual(p%7, v%7)
        self.assertEqual(p/6, v/6)

        self.assertEqual(22<p, 22<v)
        self.assertEqual(10>=p, 10>=v)
        self.assertEqual(9.0>p, 9.0>v)
        self.assertEqual(9.25<=p, 9.25<=v)
        self.assertEqual(7==p, 7==v)
        self.assertEqual(18!=p, 18!=v)

        self.assertEqual(cmp(p,14), cmp(v,14))
        self.assertEqual(cmp(14,p), cmp(14,v))

        self.assertEqual(divmod(p,3), divmod(v,3))

        if v:
            self.assertEqual(divmod(3,p), divmod(3,v))
            self.assertEqual(62//p, 62//v)
            self.assertEqual(7/p, 7/v)
            self.assertEqual(7%p, 7%v)

        self.checkBasics(v)

    def checkList(self, v):
        p = self.proxied(v)
        for i in range(len(v)):
            self.assertEqual(p[i], v[i])
            self.assertEqual(p[i:], v[i:])
            self.assertEqual(p[:i], v[:i])
            self.assertEqual(p[i::-1], v[i::-1])
        self.checkContainer(v)

        c = list(v)
        del p[::1]
        del c[::1]
        self.assertEqual(v, c)

        p[1:1] = [23]
        c[1:1] = [23]
        self.assertEqual(v, c)

    def checkContainer(self, v):
        p = self.proxied(v)
        self.assertEqual(list(p), list(v))
        self.assertEqual(list(iter(p)), list(iter(v)))
        self.assertEqual(len(p), len(v))
        self.assertEqual(42 in p, 42 in v)
        self.assertEqual(99 in p, 99 in v)
        self.checkBasics(v)

    def checkBasics(self, v):
        p = self.proxied(v)
        for f in bool, repr, str:
            self.assertEqual(f(p), f(v))

    def testNumbers(self):
        for i in range(20):
            self.checkInteger(i)

        f = -40
        while f<=20.0:
            self.checkNumeric(f)
            f += 2.25

    def testLists(self):
        for d in [1,2], [3,42,59], [99,23,55]:
            self.checkList(d)


class InPlaceMixin(ProxyTestMixin):

    def checkInteger(self, vv):
        mk = lambda: (self.proxied(vv), vv)
        p,v = mk()
        p|=0b010101; v|=0b010101
        self.assertEqual(p.__subject__, v)
        p,v = mk(); p&=0b010101; v&=0b010101; self.assertEqual(p.__subject__, v)
        p,v = mk(); p^=0b010101; v^=0b010101; self.assertEqual(p.__subject__, v)
        p,v = mk(); p<<=3; v<<=3; self.assertEqual(p.__subject__, v)
        p,v = mk(); p>>=3; v>>=3; self.assertEqual(p.__subject__, v)
        ProxyTestMixin.checkInteger(self, vv)

    def checkNumeric(self, vv):
        mk = lambda: (self.proxied(vv), vv)
        p,v = mk(); p+=17; v+=17; self.assertEqual(p.__subject__, v)
        p,v = mk(); p-=22; v-=22; self.assertEqual(p.__subject__, v)
        p,v = mk(); p*=15; v*=15; self.assertEqual(p.__subject__, v)
        p,v = mk(); p//=3; v//=3; self.assertEqual(p.__subject__, v)
        p,v = mk(); p**=2; v**=2; self.assertEqual(p.__subject__, v)
        p,v = mk(); p/=61; v/=61; self.assertEqual(p.__subject__, v)
        p,v = mk(); p%=19; v%=19; self.assertEqual(p.__subject__, v)
        ProxyTestMixin.checkNumeric(self, vv)


class TestLazyProxy(InPlaceMixin, unittest.TestCase):
    proxied = lambda self, v: LazyProxy(lambda:v)

