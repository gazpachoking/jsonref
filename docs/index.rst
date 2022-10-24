=======
jsonref
=======


.. module:: jsonref


``jsonref`` is a library for automatic dereferencing of
`JSON Reference <https://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
objects for Python (supporting Python 3.3+).

.. testcode::

    from pprint import pprint
    from jsonref import replace_refs

    # Sample JSON data, like from json.load
    document = {
        "data": ["a", "b", "c"],
        "reference": {"$ref": "#/data/1"}
    }

    # The :func:`replace_refs` function will return a copy of the document
    # with refs replaced by :class:`JsonRef` objects
    pprint(replace_refs(document))

.. testoutput::

    {'data': ['a', 'b', 'c'], 'reference': 'b'}


The :func:`replace_refs` function
=================================

The primary interface to use jsonref is with the function :func:`replace_refs`.
It will return a copy of an object you pass it, with all JSON references contained
replaced by :class:`JsonRef` objects. There are several other options you can pass,
seen below.

.. autofunction:: replace_refs

The different modes
-------------------

``proxies``
^^^^^^^^^^^

The default mode (``proxies=True``) uses :class:`JsonRef` proxy objects to replace the
reference objects in the document. For most purposes, they proxy everything to the
referenced document. This can be useful for a few reasons:

- The original reference object is still available with the
  :attr:`JsonRef.__reference__` attribute.
- :func:`dump` and :func:`dumps` can be used to output the document again, with the
  references still intact. (Including changes made.)

If you are using a tool that does not play nicely with the :class:`JsonRef` proxy
objects, they can be turned off completely using ``proxies=False``. This is needed e.g.
if you want to pass the data back to the stdlib :func:`json.dump` function.

``lazy_load`` and ``load_on_repr``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, the references will not actually be resolved until the data is accessed
(``lazy_load=True``.) This can be useful to limit the upfront processing of deeply
nested, or otherwise complicated reference trees. To limit the lookups even more, the
``load_on_repr`` argument can be set to ``False``, so that printing the document will
not cause the references to load (this can be especially useful when debugging.) The
downside of this mode is that exceptions when a reference cannot be loaded might be
issued from more places when using the loaded document. Turning off lazy loading can
make catching errors much easier.

``merge_props``
^^^^^^^^^^^^^^^

When using this mode, extra properties from the reference object will be merged into
the referenced document. e.g.::

    >>> json = {
        "a": {"$ref": "#/b", "extra": "blah"},
        "b": {"real": "b"}
    }
    >>> print(replace_refs(json, merge_props=True))
    {
        "a": {"real": "b", "extra": "blah"},
        "b": {"real": "b"}
    }
    >>> print(replace_refs(json))
    {
        "a": {"real": "b"},
        "b": {"real": "b"}
    }

This is against the JSON reference spec, but some other JSON reference libraries also
implement this behavior. It can be useful to e.g. extend common JSON schemas with extra
properties. This behavior should not be used if you want your JSON documents to be
usable with the widest possible array of tools.

A note on ``base_uri``
--------------------

A common question is how to reference other documents from the local filesystem. This is
easy if you provide the correct ``base_uri`` to the :func:`replace_refs` function (or
the other utility functions.) For example, if you have several files in a folder like
this::

    file-a.json
    file-b.json

If ``file-a.json`` has a reference like ``{"$ref": "file-b.json"}`` you could load them
like this::

    from pathlib import Path
    import jsonref

    file_a_path = Path("file-a.json").absolute()

    with file_a_path.open() as file_a:
        result = jsonref.load(file_a, base_uri=file_a_path.as_uri())


:class:`JsonRef` Objects
========================

:class:`JsonRef` objects are used to replace the JSON reference objects within
the data structure. They act as proxies to whatever data the reference is
pointing to, but only look up that data the first time they are accessed. Once
JSON reference objects have been substituted in your data structure, you can
use the data as if it does not contain references at all.

.. autoclass:: JsonRef(refobj, base_uri=None, loader=None, jsonschema=False, load_on_repr=True)

    :class:`JsonRef` instances proxy almost all operators and attributes to the
    referent data, which will be loaded when first accessed. The following
    attributes are not proxied:

    .. attribute:: __subject__

        Contains the referent data. Accessing this will cause the data to be
        loaded if it has not already been.

    .. attribute:: __reference__

        Contains the original JSON Reference object. Accessing this attribute
        will not cause the referent data to be loaded.


Loading a document at a given URI
=================================

In order to actually get and parse the JSON at a given URI, :class:`JsonRef`
objects pass the URI to a callable, set with the keyword argument ``loader``.
This callable must take the URI as an argument, and return the parsed JSON
referred to by that URI.

The :class:`JsonLoader` class is provided to fill this role, and a default
instance of it will be used for all refs unless a custom one is specified.

.. autoclass:: JsonLoader
    :members: __call__

Custom Loaders
----------

If you want to support custom references, you can define your own loader. For example
here is a complete script to load `env:XXX` URIs from environment variables::

    import os

    import jsonref


    def loader(uri):
        if uri.startswith("env:"):
            return os.environ[uri[4:]]
        # Fall back to the default loader:
        return jsonref.jsonloader(uri)

    json_w_refs = {
        "a": {"$ref": "env:MYENVVAR"}
    }

    result = jsonref.replace_refs(json, loader=loader)


:mod:`json` module drop in replacement functions
================================================

Several functions are provided as drop in replacements to functions from the
:mod:`json` module.

load
----

:func:`load` and :func:`loads` work just like their
:mod:`json` counterparts, except for references will already be replaced in the
return values.

.. autofunction:: load

.. autofunction:: loads

There is also a convenience function provided to load and process references on
a document at a given uri using the specified ``loader``

.. autofunction:: load_uri

dump
----

:func:`dump` and :func:`dumps` work just like their :mod:`json` counterparts,
except they output the original reference objects when encountering
:class:`JsonRef` instances.

.. autofunction:: dump

.. autofunction:: dumps


When things go wrong
====================
If there is a failure when resolving a JSON reference, a :class:`JsonRefError` will be raised with the details.

.. autoclass:: JsonRefError

    .. attribute:: message

    .. attribute:: reference

        Contains the original JSON reference object.

    .. attribute:: uri

        The uri that was trying to be resolved in the JSON reference object.

    .. attribute:: base_uri

        If the uri was relative, or a fragment, this is the base uri it was being resolved against.

    .. attribute:: path

        This is the path within the JSON document the reference was found. This can be useful when the reference was
        deeply nested within the document.

    .. attribute:: cause

        The exception that caused the resolution to fail.
