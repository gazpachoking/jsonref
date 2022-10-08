=======
jsonref
=======


.. module:: jsonref


``jsonref`` is a library for automatic dereferencing of
`JSON Reference <https://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
objects for Python (supporting Python 2.6+ and Python 3.3+).

.. testcode::

    from pprint import pprint
    from jsonref import JsonRef

    # Sample JSON data, like from json.load
    document = {
        "data": ["a", "b", "c"],
        "reference": {"$ref": "#/data/1"}
    }

    # The JsonRef.replace_refs class method will return a copy of the document
    # with refs replaced by :class:`JsonRef` objects
    pprint(JsonRef.replace_refs(document))

.. testoutput::

    {'data': ['a', 'b', 'c'], 'reference': 'b'}


:class:`JsonRef` Objects
========================

:class:`JsonRef` objects are used to replace the JSON reference objects within
the data structure. They act as proxies to whatever data the reference is
pointing to, but only look up that data the first time they are accessed. Once
JSON reference objects have been substituted in your data structure, you can
use the data as if it does not contain references at all.

The primary interface to use :class:`JsonRef` objects is with the class method
:meth:`JsonRef.replace_refs`. It will return a copy of an object you pass it, with
all JSON references contained replaced by :class:`JsonRef` objects. There are
several other options you can pass, seen below.

.. autoclass:: JsonRef(refobj, base_uri=None, loader=None, jsonschema=False, load_on_repr=True)

    .. automethod:: replace_refs(obj, base_uri=None, loader=None, jsonschema=False, load_on_repr=True)

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
