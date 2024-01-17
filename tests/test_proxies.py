import functools
import operator
from copy import deepcopy

import pytest

from jsonref import replace_refs
from jsonref.proxytypes import CallbackProxy, LazyProxy, Proxy, notproxied  # noqa


def cmp(a, b):
    return (a > b) - (a < b)


@pytest.fixture(
    params=[{"lazy_load": True}, {"lazy_load": False}, {"proxies": False}],
    ids=["lazy_load", "no lazy_load", "no proxies"],
)
def parametrized_replace_refs(request):
    return functools.partial(replace_refs, **request.param)


_unset = object()


class TestProxies(object):
    @pytest.fixture(
        scope="class", autouse=True, params=["Proxy", "CallbackProxy", "LazyProxy"]
    )
    def make_proxify(self, request):
        param = request.param

        def proxify(self, val):
            c = deepcopy(val)
            if param == "Proxy":
                return Proxy(c)
            globals().get(param)
            return globals().get(param)(lambda: c)

        request.cls.proxify = proxify

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
            operator.and_,
            operator.or_,
            operator.xor,
            operator.iand,
            operator.ior,
            operator.ixor,
        ):
            self.check_func(op, v, 0b10101)
        for op in (
            operator.lshift,
            operator.rshift,
            operator.ilshift,
            operator.irshift,
        ):
            self.check_func(op, v, 3)
        for op in (operator.invert, hex, oct):
            self.check_func(op, v)

        self.check_numeric(v)

    def check_numeric(self, v):
        for op in (operator.pos, operator.neg, abs, int, float, hash, complex):
            self.check_func(op, v)

        for other in (5, 13.7):  # Check against both an int and a float
            for op in (
                # Math
                operator.mul,
                operator.pow,
                operator.add,
                operator.sub,
                operator.truediv,
                operator.floordiv,
                operator.mod,
                divmod,
                # In-place
                operator.imul,
                operator.ipow,
                operator.iadd,
                operator.isub,
                operator.itruediv,
                operator.ifloordiv,
                operator.imod,
                # Comparison
                operator.lt,
                operator.le,
                operator.gt,
                operator.ge,
                operator.eq,
                operator.ne,
                cmp,
            ):
                self.check_func(op, v, other)

        self.check_basics(v)

    def check_list(self, v):
        for i in range(len(v)):
            for arg in (i, slice(i), slice(None, i), slice(i, None, -1)):
                self.check_func(operator.getitem, v, arg)
        self.check_container(v)

        p = self.proxify(v)
        c = list(v)

        p[1:1] = [23]
        c[1:1] = [23]
        assert p == c

        p.insert(1, 0)
        c.insert(1, 0)
        assert p == c

        p += [4]
        c += [4]
        assert p == c

        del p[::2]
        del c[::2]
        assert p == c

    def check_container(self, v):
        for op in (list, set, len, sorted, lambda x: list(iter(x))):
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
        for l in [1, 2], [3, 42, 59], [99, 23, 55], ["a", "b", 1.4, 17.3, -3, 42]:
            self.check_list(l)

    def test_dicts(self):
        for d in ({"a": 3, 4: 2, 1.5: "b"}, {}, {"": ""}):
            for op in (
                sorted,
                set,
                len,
                lambda x: sorted(iter(x)),
                operator.methodcaller("get", "a"),
            ):
                self.check_func(op, d)

            p = self.proxify(d)
            # Use sets to make sure order doesn't matter
            assert set(p.items()) == set(d.items())
            assert set(p.keys()) == set(d.keys())
            assert set(p.values()) == set(d.values())

            self.check_basics(d)

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
                self.attribute = "value"

        v = C()
        p = self.proxify(v)
        p.attribute = "aoeu"
        v.attribute = "aoeu"
        assert p.__subject__.attribute == v.attribute
        del p.attribute
        del v.attribute
        assert not hasattr(v, "attribute")
        assert not hasattr(p, "attribute")

    def test_call(self):
        func = lambda a: a * 2
        p = self.proxify(func)
        assert p(5) == func(5)

    def test_subject_attribute(self):
        # Test getting subject
        v = ["aoeu"]
        p = LazyProxy(lambda: v)
        assert p.__subject__ is v
        # Test setting subject
        v2 = "aoeu"
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

            @notproxied
            def decorated(self):
                return 2.0

            @property
            @notproxied
            def decorated_prop(self):
                return 3.0

        C.getter2 = notproxied(lambda self: self.attr)

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
