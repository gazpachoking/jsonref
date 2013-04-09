from functools import partial
import sys

try:
    from collections import MutableMapping
except ImportError:
    from collections.abc import MutableMapping

try:
    import simplejson as json
except ImportError:
    try:
        import json
    except ImportError:
        try:
            # Google Appengine offers simplejson via django
            from django.utils import simplejson as json
        except ImportError:
            json = None

PY3 = sys.version_info[0] >= 3

if PY3:
    from urllib import parse as urlparse
    from urllib.parse import unquote
else:
    import urlparse
    from urllib import unquote

try:
    import requests
except ImportError:
    requests = None

from lazyproxy import LazyProxy

__version__ = "0.1-dev"


class _URIDict(MutableMapping):
    """
    Dictionary which uses normalized URIs as keys.

    """

    def normalize(self, uri):
        return urlparse.urlsplit(uri).geturl()

    def __init__(self, *args, **kwargs):
        self.store = dict()
        self.store.update(*args, **kwargs)

    def __getitem__(self, uri):
        return self.store[self.normalize(uri)]

    def __setitem__(self, uri, value):
        self.store[self.normalize(uri)] = value

    def __delitem__(self, uri):
        del self.store[self.normalize(uri)]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __repr__(self):
        return repr(self.store)


class Dereferencer(object):
    def __init__(self, store=()):
        self.store = _URIDict(store)

    def __call__(self, full_uri):
        uri, fragment = urlparse.urldefrag(full_uri)
        if uri in self.store:
            document = self.store[uri]
        else:
            document = self.remote(uri)

        return self.resolve_pointer(document, fragment)

    def remote(self, uri):
        result = requests.get(uri).json()
        self.store[uri] = result
        return result

    def resolve_pointer(self, document, pointer):
        """
        Resolve a json pointer ``pointer`` within the referenced ``document``.

        :argument document: the referrant document
        :argument str pointer: a json pointer URI fragment to resolve within it

        """

        parts = unquote(pointer.lstrip("/")).split("/") if pointer else []

        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")

            if part not in document:
                raise LookupError(
                    "Unresolvable JSON pointer: %r" % pointer
                )

            document = document[part]

        return document


dereferencer = Dereferencer()


def _as_ref_object(dct):
    if "$ref" in dct:
        return LazyProxy(partial(dereferencer, dct["$ref"]))
    return dct


load = partial(json.load, object_hook=_as_ref_object)
loads = partial(json.loads, object_hook=_as_ref_object)


def loadp(obj):
    """
    Loads a python object (e.g. already parsed json) with json reference support.

    """
    try:
        return LazyProxy(partial(dereferencer, obj["$ref"]))
    except (TypeError, KeyError):
        pass
    if isinstance(obj, dict):
        return dict((k, loadp(obj[k])) for k in obj)
    elif isinstance(obj, list):
        return [loadp(i) for i in obj]
    return obj


