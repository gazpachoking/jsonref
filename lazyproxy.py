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


def _no_proxy(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        notproxied = _oga(self, "__notproxied__")
        _osa(self, "__notproxied__", True)
        try:
            return method(self, *args, **kwargs)
        finally:
            _osa(self, "__notproxied__", notproxied)
    return wrapper


class ProxyMetaClass(type):
    def __new__(cls, name, bases, dct):
        if bases != (object,):
            notproxied = set(dct.get("__notproxied__", ()))
            # In subclasses, wrap method and property calls so that
            # proxying is turned off during them
            for key, val in dct.items():
                if callable(val):
                    if getattr(val, "__notproxied__", False):
                        notproxied.add(key)
                    dct[key] = _no_proxy(val)
                elif isinstance(val, property):
                    if getattr(val.fget, "__notproxied__", False):
                        notproxied.add(key)
                    # Remake properties, with the getter method wrapped
                    dct[key] = property(
                        _no_proxy(val.fget), val.fset, val.fdel
                    )
            # Add all the non-proxied attributes from base classes
            for base in bases:
                if hasattr(base, "__notproxied__"):
                    notproxied.update(base.__notproxied__)
            dct["__notproxied__"] = notproxied
        return type.__new__(cls, name, bases, dct)

def _should_proxy(self, attr):
    notproxied = _oga(self, "__notproxied__")
    if notproxied is True:
        # TODO: Not quite sure if this is right yet, more tests needed
        if type(self) is not LazyProxy:
            return False
    elif attr in notproxied:
        return False
    return True

class LazyProxy(object):
    """
    Proxy for a lazily-obtained object, that is cached on first use.

    """

    __metaclass__ = ProxyMetaClass
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
        # notproxied = _oga(self, "__notproxied__")
        # if notproxied is True or attr in notproxied:
        #     return _oga(self, attr)
        if _should_proxy(self, attr):
            return getattr(self.__subject__, attr)
        return _oga(self, attr)

    def __setattr__(self, attr, val):
        if _oga(self, "__notproxied__") is True or attr in _oga(self, "__notproxied__"):
            _osa(self, attr, val)
        else:
            setattr(self.__subject__, attr, val)

    def __delattr__(self, attr):
        if _oga(self, "__notproxied__") is True or attr in _oga(self, "__notproxied__"):
            object.__delattr__(self, attr)
        else:
            delattr(self.__subject__, attr)

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
