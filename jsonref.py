import json
import operator
import sys
import warnings

try:
    from collections import Mapping, MutableMapping, Sequence
except ImportError:
    from collections.abc import Mapping, MutableMapping, Sequence

PY3 = sys.version_info[0] >= 3

if PY3:
    from urllib import parse as urlparse
    from urllib.parse import unquote
    from urllib.request import urlopen
    unicode = str
    basestring = str
    iteritems = operator.methodcaller("items")
else:
    import urlparse
    from urllib import unquote
    from urllib2 import urlopen
    iteritems = operator.methodcaller("iteritems")

try:
    # If requests >=1.0 is available, we will use it
    import requests
    if not callable(requests.Response.json):
        requests = None
except ImportError:
    requests = None

from proxytypes import LazyProxy

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

    def __new__(cls, obj, **kwargs):
        """
        When a :class:`JsonRef` is instantiated with an `obj` which is not a
        JSON reference object, it returns a deep copy of `obj` with all
        contained JSON reference objects replaced with :class:`JsonRef`
        objects.

        """

        kwargs.setdefault('base_doc', obj)
        try:
            if kwargs.get("jsonschema") and isinstance(obj["id"], basestring):
                kwargs.update(
                    base_uri=urlparse.urljoin(
                        kwargs.get("base_uri", ""), obj["id"]
                    ),
                    base_doc=obj
                )
            if not isinstance(obj["$ref"], basestring):
                raise TypeError
        except (TypeError, LookupError):
            pass
        else:
            return super(JsonRef, cls).__new__(cls)

        # If our obj was not a json reference object, iterate through it,
        # replacing children with JsonRefs
        if isinstance(obj, Mapping):
            return type(obj)(
                (k, JsonRef(v, **kwargs)) for k, v in iteritems(obj)
            )
        elif isinstance(obj, Sequence) and not isinstance(obj, basestring):
            return type(obj)(JsonRef(i, **kwargs) for i in obj)
        # If obj was not a list or dict, just return it
        return obj

    def __init__(
            self, refobj, base_uri=None, loader=None, loader_kwargs=(),
            base_doc=None, jsonschema=False, load_on_repr=None, _stack=()
    ):
        """
        :param refobj: A `dict` representing the JSON Reference object
        :param base_uri: URI to resolve relative references against
        :param loader: Callable that takes a URI and returns the parsed JSON
        :param base_doc: Document at `base_uri` for local dereferencing
            (defaults to `obj`)
        :param jsonschema: Flag to turn on JSON Schema mode. 'id' keyword
            changes the `base_uri` for references contained within the object
        :param load_on_repr: If left unset (or None), a `repr` call will cause
            a reference to load only until a loop is detected. If set to
            True/False, `repr` will always or never cause a reference to load
            (defaults to None)

        """
        if not isinstance(refobj.get("$ref"), basestring):
            raise ValueError("Not a valid json reference object: %s" % refobj)
        self.__reference__ = refobj
        self.base_doc=base_doc
        self.base_uri = base_uri
        self.loader = loader or jsonloader
        self.loader_kwargs = dict(loader_kwargs)
        self.jsonschema = jsonschema
        self.load_on_repr = load_on_repr
        self.stack = list(_stack)
        # If we encounter a loop
        self._circular = self.full_uri in self.stack
        self.stack.append(self.full_uri)

    @property
    def _ref_kwargs(self):
        return dict(
            base_uri=self.base_uri, base_doc=self.base_doc, loader=self.loader,
            loader_kwargs=self.loader_kwargs, jsonschema=self.jsonschema,
            load_on_repr=self.load_on_repr, _stack=self.stack
        )

    @property
    def full_uri(self):
        return urlparse.urljoin(self.base_uri, self.__reference__["$ref"])

    def callback(self):
        uri, fragment = urlparse.urldefrag(self.full_uri)

        # Relative ref within the base document
        if not uri or uri == self.base_uri and self.base_doc:
            doc = self.resolve_pointer(self.base_doc, fragment)
            return JsonRef(doc, **self._ref_kwargs)

        # Remote ref
        base_doc = self.loader(uri, **self.loader_kwargs)
        doc = self.resolve_pointer(base_doc, fragment)
        kwargs = self._ref_kwargs
        kwargs.update(base_doc=base_doc, base_uri=uri)
        return JsonRef(doc, **kwargs)

    @staticmethod
    def resolve_pointer(document, pointer):
        """
        Resolve a json pointer ``pointer`` within the referenced ``document``.

        :argument document: the referent document
        :argument str pointer: a json pointer URI fragment to resolve within it

        """

        def fail():
            raise LookupError("Unresolvable JSON pointer: %r" % pointer)

        parts = unquote(pointer.lstrip("/")).split("/") if pointer else []

        for part in parts:
            part = part.replace("~1", "/").replace("~0", "~")
            if isinstance(document, Mapping):
                if part not in document:
                    fail()
            else:
                try:
                    part = int(part)
                except ValueError:
                    fail()
                if part >= len(document):
                    fail()
            document = document[part]
        return document

    def __repr__(self):
        load = self.load_on_repr
        if load is None:
            load = not self._circular
        if hasattr(self, "cache") or load:
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


class JsonLoader(object):
    """
    Provides a callable which takes a URI, and returns the loaded JSON referred
    to by that URI.

    """
    def __init__(self, store=(), cache_results=True):
        """
        :param store: A pre-populated dictionary matching URIs to loaded JSON
            documents
        :param cache_results: If this is set to false, the internal cache of
            loaded JSON documents is not used

        """
        self.store = _URIDict(store)
        self.cache_results = cache_results

    def __call__(self, uri, **kwargs):
        """
        Return the loaded JSON referred to by `uri`

        :param uri: The URI of the JSON document to load
        :param kwargs: Keyword arguments passed to :func:`json.loads`

        """
        if uri in self.store:
            return self.store[uri]
        else:
            result = self.get_remote_json(uri, **kwargs)
            if self.cache_results:
                self.store[uri] = result
            return result

    def get_remote_json(self, uri, **kwargs):
        scheme = urlparse.urlsplit(uri).scheme

        if scheme in ["http", "https"] and requests:
            # Prefer requests, it has better encoding detection
            try:
                result = requests.get(uri).json(**kwargs)
            except TypeError:
                warnings.warn(
                    "requests >=1.2 required for custom kwargs to json.loads"
                )
                result = requests.get(uri).json()
        else:
            # Otherwise, pass off to urllib and assume utf-8
            result = json.loads(urlopen(uri).read().decode("utf-8"), **kwargs)

        return result

jsonloader = JsonLoader()


def load(json_file, ref_kwargs=(), **kwargs):
    """
    Drop in replacement for :func:`json.load`, where JSON references are
    proxied to their referent data.

    :param ref_kwargs: A dict of keyword arguments to pass to :class:`JsonRef`

    All other keyword arguments will be passed to :func:`json.load`

    """

    ref_kwargs = dict(ref_kwargs)
    ref_kwargs.setdefault("loader_kwargs", kwargs)
    return JsonRef(json.load(json_file, **kwargs), **ref_kwargs)


def loads(json_str, ref_kwargs=(), **kwargs):
    """
    Drop in replacement for :func:`json.loads`, where JSON references are
    proxied to their referent data.

    :param ref_kwargs: A dict of keyword arguments to pass to :class:`JsonRef`

    All other keyword arguments will be passed to :func:`json.loads`

    """

    ref_kwargs = dict(ref_kwargs)
    ref_kwargs.setdefault("loader_kwargs", kwargs)
    return JsonRef(json.loads(json_str, **kwargs), **ref_kwargs)


def load_uri(uri, ref_kwargs=(), **kwargs):
    """
    Load JSON data from ``uri`` with JSON references proxied to their referent
    data.

    :param uri: URI to fetch the JSON from
    :param loader: Callable that takes a URI and returns the parsed JSON

    """

    ref_kwargs = dict(ref_kwargs)
    ref_kwargs.setdefault("loader_kwargs", kwargs)
    ref_kwargs.setdefault("base_uri", uri)
    loader = ref_kwargs.pop("loader", jsonloader)
    return JsonRef(loader(uri, **kwargs), **ref_kwargs)


def dump(obj, fp, **kwargs):
    """
    Dump JSON for `obj` to `fp`, which may contain :class:`JsonRef` objects.
    `JsonRef` objects will be dumped as the original reference object they were
    created from.

    :param kwargs: Keyword arguments are the same as to :func:`json.dump`

    """
    # Strangely, json.dumps does not use the custom serialization from our
    # encoder on python 2.7+. Instead just write json.dumps output to a file.
    fp.write(dumps(obj, **kwargs))


def dumps(obj, **kwargs):
    """
    Dump JSON for `obj` to a string, which may contain :class:`JsonRef`
    objects. `JsonRef` objects will be dumped as the original reference object
    they were created from.

    :param kwargs: Keyword arguments are the same as to :func:`json.dumps`

    """
    kwargs["cls"] = _ref_encoder_factory(kwargs.get("cls", json.JSONEncoder))
    return json.dumps(obj, **kwargs)


def _ref_encoder_factory(cls):
    class JSONRefEncoder(cls):
        def default(self, o):
            if hasattr(o, "__reference__"):
                return o.__reference__
            return super(JSONRefEncoder, cls).default(o)
        # Python 2.6 doesn't work with the default method
        def _iterencode(self, o, *args, **kwargs):
            if hasattr(o, "__reference__"):
                o = o.__reference__
            return super(JSONRefEncoder, self)._iterencode(o, *args, **kwargs)
        # Pypy doesn't work with either of the other methods
        def _encode(self, o, *args, **kwargs):
            if hasattr(o, "__reference__"):
                o = o.__reference__
            return super(JSONRefEncoder, self)._encode(o, *args, **kwargs)
    return JSONRefEncoder
