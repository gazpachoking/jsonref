from functools import partial, wraps
import operator

comparison_operators = "eq ne lt gt le ge"
unary_operators = "pos neg abs invert round floor ceil truc"
binary_operators = "add sub mul floordiv div truediv mod divmod pow lshift rshift and or xor"
#reflected ops have r in front of binary op name
#augmented operators

class LazyProxy(object):
    """Delegates all operations (except ``.__subject__``) to another object"""
    __slots__ = ('__callback__', '__cache__')


    def __init__(self, func):
        set_callback(self,func)

    def __call__(self, *args, **kw):
        return self.__subject__(*args, **kw)

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

    def __getitem__(self, arg):
        return self.__subject__[arg]

    def __setitem__(self, arg, val):
        self.__subject__[arg] = val

    def __delitem__(self, arg):
        del self.__subject__[arg]

    def __getslice__(self, i, j):
        return self.__subject__[i:j]

    def __setslice__(self, i, j, val):
        self.__subject__[i:j] = val

    def __delslice__(self, i, j):
        del self.__subject__[i:j]

    def __contains__(self, ob):
        return ob in self.__subject__

    #for name in 'repr str hash len abs complex int long float iter oct hex'.split():
        #def func(self):
        #    name
        #locals()["__%s__" % name] = lambda self: globals()[name](self.__subject__)
        #exec "def __%s__(self): return %s(self.__subject__)" % (name,name)

    for name in 'cmp', 'coerce', 'divmod':
        exec "def __%s__(self,ob): return %s(self.__subject__,ob)" % (name,name)

"""    for name,op in [
        ('lt','<'), ('gt','>'), ('le','<='), ('ge','>='),
        ('eq','=='), ('ne','!=')
    ]:
        exec "def __%s__(self,ob): return self.__subject__ %s ob" % (name,op)

    for name,op in [('neg','-'), ('pos','+'), ('invert','~')]:
        exec "def __%s__(self): return %s self.__subject__" % (name,op)

    for name, op in [
        ('or','|'),  ('and','&'), ('xor','^'), ('lshift','<<'), ('rshift','>>'),
        ('add','+'), ('sub','-'), ('mul','*'), ('div','/'), ('mod','%'),
        ('truediv','/'), ('floordiv','//')
    ]:
        exec (
                 "def __%(name)s__(self,ob):\n"
                 "    return self.__subject__ %(op)s ob\n"
                 "\n"
                 "def __r%(name)s__(self,ob):\n"
                 "    return ob %(op)s self.__subject__\n"
                 "\n"
                 "def __i%(name)s__(self,ob):\n"
                 "    self.__subject__ %(op)s=ob\n"
                 "    return self\n"
             )  % locals()

    del name, op"""

    # Oddball signatures

"""    def __rdivmod__(self,ob):
        return divmod(ob, self.__subject__)

    def __pow__(self,*args):
        return pow(self.__subject__,*args)

    def __ipow__(self,ob):
        self.__subject__ **= ob
        return self

    def __rpow__(self,ob):
        return pow(ob, self.__subject__)"""


def proxy_func(func):
    #@wraps(func)
    def proxied(p, *args, **kwargs):
        subject = p.__subject__
        return func(subject, *args, **kwargs)
    return proxied


for func in [repr, str, hash, len, abs, complex, bool, int, long, float, iter, oct, hex]:
    setattr(LazyProxy, "__%s__" % func.__name__, proxy_func(func))

for func in dir(operator):
    if not func.startswith("__") or func == "__doc__":
        continue
    setattr(LazyProxy, func, proxy_func(getattr(operator, func)))


set_callback = LazyProxy.__callback__.__set__
get_callback = LazyProxy.__callback__.__get__
LazyProxy.__subject__ = property(lambda self, gc=get_callback: gc(self)())


get_cache = LazyProxy.__cache__.__get__
set_cache = LazyProxy.__cache__.__set__

def __subject__(self, get_cache=get_cache, set_cache=set_cache):
    try:
        return get_cache(self)
    except AttributeError:
        print('setting cache')
        set_cache(self, get_callback(self)())
        return get_cache(self)

LazyProxy.__subject__ = property(__subject__, set_cache)
del __subject__



