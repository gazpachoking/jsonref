"""
Based on the implementation here:
https://pypi.python.org/pypi/ProxyTypes/0.9
"""

from functools import wraps
import operator
import sys


PY3 = sys.version_info[0] >= 3

OPERATORS = [
    # Unary
    "pos", "neg", "abs", "invert",
    # Comparison
    "eq", "ne", "lt", "gt", "le", "ge",
    # Container
    "getitem", "setitem", "delitem", "contains",
    # In-place operators
    "iadd", "isub", "imul", "ifloordiv", "itruediv", "imod", "ipow", "ilshift",
    "irshift", "iand", "ior", "ixor"
]
REFLECTED_OPERATORS = [
    "add", "sub", "mul", "floordiv", "truediv", "mod", "pow", "and", "or",
    "xor", "lshift", "rshift"
]
# These functions all have magic methods named after them
MAGIC_FUNCS = [
    divmod, round, repr, str, hash, len, abs, complex, bool, int, float, iter
]

if PY3:
    MAGIC_FUNCS += [bytes]
else:
    OPERATORS += ["getslice", "setslice", "delslice", "idiv"]
    REFLECTED_OPERATORS += ["div"]
    MAGIC_FUNCS += [long, unicode, cmp, coerce, oct, hex]


_oga = object.__getattribute__
_osa = object.__setattr__


def _do_proxy(method, proxy=False):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        notproxied = _oga(self, "__notproxied__")
        _osa(self, "__notproxied__", not proxy)
        try:
            return method(self, *args, **kwargs)
        finally:
            _osa(self, "__notproxied__", notproxied)
    return wrapper


class ProxyMetaClass(type):
    def __new__(mcs, name, bases, dct):
        notproxied = set(dct.pop("__notproxied__", ()))
        # Add all the non-proxied attributes from base classes
        for base in bases:
            if hasattr(base, "__notproxied__"):
                notproxied.update(base.__notproxied__)
        dct["__notproxied__"] = notproxied
        newcls = type.__new__(mcs, name, bases, {"__notproxied__": notproxied})
        for key, val in dct.items():
            setattr(newcls, key, val)
        return newcls

    def __setattr__(cls, key, value):
        if key == "__dict__":
            return
        do_proxy = False
        if len(cls.__bases__) == 1 and cls.__bases__[0].__name__ == "_ProxyBase":
            do_proxy = True
        if callable(value):
            if getattr(value, "__notproxied__", False):
                cls.__notproxied__ |= set([key])
            value = _do_proxy(value, do_proxy)
        elif isinstance(value, property):
            if getattr(value.fget, "__notproxied__", False):
                cls.__notproxied__ |= set([key])
            # Remake properties, with the getter method wrapped
            value = property(_do_proxy(value.fget, do_proxy), value.fset, value.fdel)
        type.__setattr__(cls, key, value)

_ProxyBase = ProxyMetaClass("_ProxyBase", (object,), {})

def _proxymetaclass(cls):
    """
    Class decorator to remake the class as a ProxyMetaClass in both
    python 2 and 3

    """
    return ProxyMetaClass(cls.__name__, cls.__bases__, dict(cls.__dict__))


def _should_proxy(self, attr):
    if attr in type(self).__notproxied__:
        return False
    if _oga(self, "__notproxied__") is True:
        return False
    return True



class LazyProxy(_ProxyBase):
    """
    Proxy for a lazily-obtained object, that is cached on first use.

    """

    __notproxied__ = ("__subject__",)

    def __init__(self, func):
        _osa(self, "__callback__", func)

    @staticmethod
    def notproxied(func):
        func.__notproxied__ = True
        return func

    @property
    def __subject__(self):
        try:
            return _oga(self, "__cache__")
        except AttributeError:
            _osa(self, "__cache__", _oga(self, "__callback__")())
            return _oga(self, "__cache__")

    @__subject__.setter
    def __subject__(self, value):
        _osa(self, "__cache__", value)

    def __getattribute__(self, attr):
        if _should_proxy(self, attr):
            return getattr(self.__subject__, attr)
        return _oga(self, attr)

    def __setattr__(self, attr, val):
        if _should_proxy(self, attr):
            setattr(self.__subject__, attr, val)
        _osa(self, attr, val)

    def __delattr__(self, attr):
        if _should_proxy(self, attr):
            delattr(self.__subject__, attr)
        object.__delattr__(self, attr)

    def __call__(self, *args, **kw):
        return self.__subject__(*args, **kw)


def proxy_func(func, arg_pos=0):
    @wraps(func)
    def proxied(p, *args, **kwargs):
        args = list(args)
        args.insert(arg_pos, p.__subject__)
        result = func(*args, **kwargs)
        return result
    return proxied


for func in MAGIC_FUNCS:
    setattr(LazyProxy, "__%s__" % func.__name__, proxy_func(func))

for op in OPERATORS + REFLECTED_OPERATORS:
    magic_meth = "__%s__" % op
    setattr(LazyProxy, magic_meth, proxy_func(getattr(operator, magic_meth)))

# Reflected operators
for op in REFLECTED_OPERATORS:
    setattr(
        LazyProxy, "__r%s__" % op,
        proxy_func(getattr(operator, "__%s__" % op), arg_pos=1)
    )

# One offs
# Only non-operator that needs a reflected version
LazyProxy.__rdivmod__ = proxy_func(divmod, arg_pos=1)
# For python 2.6
LazyProxy.__nonzero__ = LazyProxy.__bool__
# pypy is missing __index__ in operator module
LazyProxy.__index__ = proxy_func(operator.index)
