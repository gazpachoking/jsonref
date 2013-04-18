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


class JsonRef(LazyProxy):
    """
    A lazy loading proxy to the dereferenced data pointed to by a JSON
    Reference object.

    Proxies almost all operators and attributes to the dereferenced data, which
    will be loaded when first accessed. The following attributes are not
    proxied:

    :attribute __subject__: The referent data
    :attribute __reference__: The original JSON Reference object

    """

    __notproxied__ = ("__reference__",)

    def __init__(
            self, refobj, base_uri=None, deref=None, base_doc=None,
            jsonschema=False, load_on_repr=False
    ):
        """
        :param refobj: A `dict` representing the JSON Reference object
        :param base_uri: URI to resolve relative references against
        :param deref: Callable that takes a URI and returns the parsed JSON
        :param base_doc: Document at `base_uri` for local dereferencing
            (defaults to `obj`)
        :param jsonschema: Flag to turn on JSON Schema mode. 'id' keyword
            changes the `base_uri` for references contained within the object
        :param load_on_repr: If set to False, `repr` calls will not cause
            unloaded references to be loaded, allowing the repr of recursive
            refs. (defaults to False)

        """
        if not isinstance(refobj.get("$ref"), (str, unicode)):
            raise ValueError("Not a valid json reference object: %s" % refobj)
        self.__reference__ = refobj
        self.base_doc=base_doc
        self.base_uri = base_uri
        self.deref = deref or dereferencer
        self.jsonschema = jsonschema
        self.load_on_repr = load_on_repr

    @property
    def _ref_kwargs(self):
        return dict(
            base_uri=self.base_uri, base_doc=self.base_doc, deref=self.deref,
            jsonschema=self.jsonschema, proxy_repr=self.load_on_repr
        )

    def callback(self):
        full_uri = urlparse.urljoin(self.base_uri, self.__reference__["$ref"])
        uri, fragment = urlparse.urldefrag(full_uri)

        # Relative ref within the base document
        if not uri or uri == self.base_uri and self.base_doc:
            doc = resolve_pointer(self.base_doc, fragment)
            return replace_json_refs(doc, **self._ref_kwargs)

        # Remote ref
        base_doc = self.deref(uri)
        doc = resolve_pointer(base_doc, fragment)
        kwargs = self._ref_kwargs
        kwargs.update(base_doc=base_doc, base_uri=uri)
        return replace_json_refs(doc, **kwargs)

    def __repr__(self):
        if self.load_on_repr or hasattr(self, "cache"):
            return repr(self.__subject__)
        return "JsonRef%r" % self.__reference__


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


def replace_json_refs(obj, **kwargs):
    """
    Returns a deep copy of `obj` with all contained JSON reference objects
    replaced by :class:`JsonRef` objects.

    :param obj: Python data structure consisting of JSON primitive types

    The following arguments must all be specified as keywords.

    :param base_uri: URI to resolve relative references against
    :param deref: Callable that takes a URI and returns the parsed JSON
    :param base_doc: Document at `base_uri` for local dereferencing
        (defaults to `obj`)
    :param jsonschema: Flag to turn on JSON Schema mode. 'id' keyword changes
        the `base_uri` for references contained within the object
    :param load_on_repr: If set to False, `repr` calls will not cause unloaded
        references to be loaded, allowing the repr of recursive refs.
        (defaults to False)

    """

    kwargs.setdefault('base_doc', obj)
    def inner(inner_obj, **kwargs):
        if isinstance(inner_obj, dict):
            if isinstance(inner_obj.get("$ref"), (str, unicode)):
                return JsonRef(inner_obj, **kwargs)
            if (
                    kwargs.get("jsonschema") and
                    isinstance(inner_obj.get("id"), (str, unicode))
            ):
                kwargs.update(
                    base_uri=urlparse.urljoin(
                        kwargs.get("base_uri", ""), inner_obj["id"]
                    ),
                    base_doc=inner_obj)
            return dict((k, inner(inner_obj[k], **kwargs)) for k in inner_obj)
        elif isinstance(inner_obj, list):
            return [inner(i, **kwargs) for i in inner_obj]
        return inner_obj

    return inner(obj, **kwargs)


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
    dref = kwargs.pop('deref', dereferencer)
    load_on_repr = kwargs.pop('load_on_repr', False)
    return replace_json_refs(
        json.load(json_file, *args, **kwargs),
        base_uri=base_uri, deref=dref, load_on_repr=load_on_repr
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
    deref = kwargs.pop('deref', dereferencer)
    load_on_repr = kwargs.pop('load_on_repr', False)
    return replace_json_refs(
        json.loads(json_str, *args, **kwargs),
        base_uri=base_uri, deref=deref, load_on_repr=load_on_repr
    )


def loaduri(uri, deref=dereferencer, load_on_repr=False):
    """
    Load JSON data from ``uri`` with JSON references proxied to their referent
    data.

    :param uri: URI to fetch the JSON from
    :param dereferencer: Callable that takes a URI and returns the parsed JSON

    """

    return replace_json_refs(
        deref(uri), base_uri=uri, deref=deref, load_on_repr=load_on_repr
    )


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
