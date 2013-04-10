import json
import sys

try:
    from collections import MutableMapping
except ImportError:
    from collections.abc import MutableMapping

PY3 = sys.version_info[0] >= 3

if PY3:
    from urllib import parse as urlparse
    from urllib.parse import unquote
    from urllib.request import urlopen
    unicode = str
else:
    import urlparse
    from urllib import unquote
    from urllib2 import urlopen

try:
    import requests
except ImportError:
    requests = None

from lazyproxy import LazyProxy

__version__ = "0.1-dev"


def resolve_pointer(document, pointer):
    """
    Resolve a json pointer ``pointer`` within the referenced ``document``.

    :argument document: the referent document
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
    def __init__(self, store=(), cache_results=True):
        self.store = _URIDict(store)
        self.cache_results = cache_results

    def __call__(self, uri):
        if uri in self.store:
            return self.store[uri]
        else:
            result = self.get_remote_json(uri)
            if self.cache_results:
                self.store[uri] = result
            return result

    def get_remote_json(self, uri):
        scheme = urlparse.urlsplit(uri).scheme

        if (
            scheme in ["http", "https"] and
            requests and getattr(requests.Response, "json", None)
        ):
            # Prefer requests, it has better encoding detection
            if callable(requests.Response.json):
                result = requests.get(uri).json()
            else:
                result = requests.get(uri).json
        else:
            # Otherwise, pass off to urllib and assume utf-8
            result = json.loads(urlopen(uri).read().decode("utf-8"))

        return result

dereferencer = Dereferencer()


def load(json_file, *args, **kwargs):
    """
    Drop in replacement for :func:`json.load`, where JSON references are
    proxied to their referent data.

    :param json_file: The JSON file to load
    :param base_uri: URI to resolve relative references against
    :param dereferencer: Callable that takes a URI and returns the parsed JSON

    All other arguments will be passed to :func:`json.load`

    """

    base_uri = kwargs.pop('base_uri', None)
    dref = kwargs.pop('dereferencer', dereferencer)
    return loadp(
        json.load(json_file, *args, **kwargs),
        base_uri=base_uri, dereferencer=dref
    )


def loads(json_str, *args, **kwargs):
    """
    Drop in replacement for :func:`json.loads`, where JSON references are
    proxied to their referent data.

    :param json_str: The JSON string to load
    :param base_uri: URI to resolve relative references against
    :param dereferencer: Callable that takes a URI and returns the parsed JSON

    All other arguments will be passed to :func:`json.loads`

    """

    base_uri = kwargs.pop('base_uri', None)
    dref = kwargs.pop('dereferencer', dereferencer)
    return loadp(
        json.loads(json_str, *args, **kwargs),
        base_uri=base_uri, dereferencer=dref
    )


def loaduri(uri, dereferencer=dereferencer):
    """
    Load JSON data from ``uri`` with JSON references proxied to their referent
    data.

    :param uri: URI to fetch the JSON from
    :param dereferencer: Callable that takes a URI and returns the parsed JSON

    """

    return loadp(dereferencer(uri), base_uri=uri)


def loadp(obj, base_uri=None, dereferencer=dereferencer):
    """
    Replaces all JSON reference objects within a python object with proxies
    to the data pointed to by the reference.

    :param obj: Python data structure consisting of JSON primitive types
    :param base_uri: URI to resolve relative references against
    :param dereferencer: Callable that takes a URI and returns the parsed JSON

    """

    def inner(inner_obj):
        try:
            if isinstance(inner_obj["$ref"], (str, unicode)):
                full_uri = urlparse.urljoin(base_uri, inner_obj["$ref"])
                uri, fragment = urlparse.urldefrag(full_uri)
                if not uri or uri == base_uri:
                    return LazyProxy(
                        lambda: inner(resolve_pointer(obj, fragment))
                    )
                else:
                    return LazyProxy(
                        lambda: loadp(
                            resolve_pointer(dereferencer(uri), fragment),
                            base_uri=uri
                        )
                    )
        except (TypeError, KeyError):
            pass
        if isinstance(inner_obj, dict):
            return dict((k, inner(inner_obj[k])) for k in inner_obj)
        elif isinstance(inner_obj, list):
            return [inner(i) for i in inner_obj]
        return inner_obj

    return inner(obj)

