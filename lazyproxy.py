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
    # Don't double wrap
    if getattr(method, "_wrapped", False):
        return method
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        notproxied = _oga(self, "__notproxied__")
        _osa(self, "__notproxied__", True)
        try:
            return method(self, *args, **kwargs)
        finally:
            _osa(self, "__notproxied__", notproxied)
    wrapper._wrapped = True
    return wrapper


class ProxyMetaClass(type):
    def __new__(mcs, name, bases, dct):
        newcls = type.__new__(mcs, name, bases, {})
        newcls.__notproxied__ = set(dct.pop("__notproxied__", ()))
        # Add all the non-proxied attributes from base classes
        for base in bases:
            if hasattr(base, "__notproxied__"):
                newcls.__notproxied__.update(base.__notproxied__)
        for key, val in dct.items():
            if key == "__dict__":
                continue
            setattr(newcls, key, val)
        return newcls

    def __setattr__(cls, key, value):
        if (
            len(cls.__bases__) == 1 and
            cls.__bases__[0].__name__ == "_ProxyBase"
        ):
            # Don't do any magic on the methods of the base class
            pass
        elif callable(value):
            if getattr(value, "__notproxied__", False):
                cls.__notproxied__ |= set([key])
            value = _no_proxy(value)
        elif isinstance(value, property):
            if getattr(value.fget, "__notproxied__", False):
                cls.__notproxied__ |= set([key])
            # Remake properties, with the underlying functions wrapped
            fset = _no_proxy(value.fset) if value.fset else value.fset
            fdel = _no_proxy(value.fdel) if value.fdel else value.fdel
            value = property(_no_proxy(value.fget), fset, fdel)
        type.__setattr__(cls, key, value)

# Since python 2 and 3 metaclass syntax aren't compatible, create an instance
# of our metaclass which our Proxy class can inherit from
_ProxyBase = ProxyMetaClass("_ProxyBase", (object,), {})


def _should_proxy(self, attr):
    if attr in type(self).__notproxied__:
        return False
    if _oga(self, "__notproxied__") is True:
        return False
    return True


class Proxy(_ProxyBase):
    """
    Proxy for any python object.

    """

    __notproxied__ = ("__subject__",)

    def __init__(self, subject):
        self.__subject__ = subject

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

    @staticmethod
    def notproxied(func):
        """
        Decorator for methods that should not be proxied

        """
        func.__notproxied__ = True
        return func


def proxy_func(func, arg_pos=0):
    @wraps(func)
    def proxied(p, *args, **kwargs):
        args = list(args)
        args.insert(arg_pos, p.__subject__)
        result = func(*args, **kwargs)
        return result
    return proxied


for func in MAGIC_FUNCS:
    setattr(Proxy, "__%s__" % func.__name__, proxy_func(func))

for op in OPERATORS + REFLECTED_OPERATORS:
    magic_meth = "__%s__" % op
    setattr(Proxy, magic_meth, proxy_func(getattr(operator, magic_meth)))

# Reflected operators
for op in REFLECTED_OPERATORS:
    setattr(
        Proxy, "__r%s__" % op,
        proxy_func(getattr(operator, "__%s__" % op), arg_pos=1)
    )

# One offs
# Only non-operator that needs a reflected version
Proxy.__rdivmod__ = proxy_func(divmod, arg_pos=1)
# For python 2.6
Proxy.__nonzero__ = Proxy.__bool__
# pypy is missing __index__ in operator module
Proxy.__index__ = proxy_func(operator.index)


class CallbackProxy(Proxy):
    """
    Proxy for a callback result. Callback is called on each access.

    """

    def __init__(self, callback):
        self.callback = callback

    @property
    def __subject__(self):
        return self.callback()


class LazyProxy(CallbackProxy):
    """
    Proxy for a callback result, that is cached on first use.

    """

    @property
    def __subject__(self):
        try:
            return self.cache
        except AttributeError:
            self.cache = super(LazyProxy, self).__subject__
            return self.cache

    @__subject__.setter
    def __subject__(self, value):
        self.cache = value
