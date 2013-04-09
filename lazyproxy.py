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
    "pos", "neg", "abs", "invert", "index",
    # Comparison
    "eq", "ne", "lt", "gt", "le", "ge",
    # Container
    "getitem", "setitem", "delitem", "contains",
]
REFLECTED_OPERATORS = [
    "add", "sub", "mul", "floordiv", "truediv", "mod", "pow", "and", "or",
    "xor", "lshift", "rshift"
]
INPLACE_OPERATORS = [
    "iadd", "isub", "imul", "ifloordiv", "itruediv", "imod", "ipow", "ilshift",
    "irshift", "iand", "ior", "ixor"
]
# These functions all have magic methods named after them
MAGIC_FUNCS = [
    divmod, round, repr, str, hash, len, abs, complex, bool, int, float, iter
]

if PY3:
    MAGIC_FUNCS += [bytes]
else:
    OPERATORS += ["getslice", "setslice", "delslice"]
    REFLECTED_OPERATORS += ["div"]
    INPLACE_OPERATORS += ["idiv"]
    MAGIC_FUNCS += [long, unicode, cmp, coerce, oct, hex]


class LazyProxy(object):
    """Proxy for a lazily-obtained object, that is cached on first use"""
    __slots__ = ("__callback__", "__cache__")

    def __init__(self, func):
        set_callback(self,func)

    @property
    def __subject__(self):
        try:
            return get_cache(self)
        except AttributeError:
            set_cache(self, get_callback(self)())
            return get_cache(self)

    @__subject__.setter
    def __subject__(self, value):
        set_cache(self, value)

    def __getattribute__(self, attr):
        subject = object.__getattribute__(self, '__subject__')
        if attr == '__subject__':
            return subject
        return getattr(subject,attr)

    def __setattr__(self, attr, val):
        if attr == '__subject__':
            object.__setattr__(self, attr, val)
        else:
            setattr(self.__subject__, attr, val)

    def __delattr__(self, attr):
        if attr == '__subject__':
            object.__delattr__(self, attr)
        else:
            delattr(self.__subject__, attr)

    def __call__(self, *args, **kw):
        return self.__subject__(*args, **kw)


set_callback = LazyProxy.__callback__.__set__
get_callback = LazyProxy.__callback__.__get__
get_cache = LazyProxy.__cache__.__get__
set_cache = LazyProxy.__cache__.__set__


def proxy_func(func, arg_pos=0, inplace=False):
    @wraps(func)
    def proxied(p, *args, **kwargs):
        args = list(args)
        args.insert(arg_pos, p.__subject__)
        result = func(*args, **kwargs)
        if inplace:
            p.__subject__ = result
            return p
        else:
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

for op in INPLACE_OPERATORS:
    magic_meth = "__%s__" % op
    setattr(
        LazyProxy, magic_meth,
        proxy_func(getattr(operator, magic_meth), inplace=True)
    )

# One offs
LazyProxy.__nonzero__ = LazyProxy.__bool__
LazyProxy.__rdivmod__ = proxy_func(divmod, arg_pos=1)
