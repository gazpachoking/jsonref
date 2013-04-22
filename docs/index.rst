=======
jsonref
=======


.. module:: jsonref


``jsonref`` is a library for automatic dereferencing of
`JSON Reference <http://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
objects for Python (supporting 2.6+ including Python 3).

.. testcode::

    from pprint import pprint
    from jsonref import JsonRef

    # Sample JSON data, like from json.load
    document = {
        "data": ["a", "b", "c"],
        "reference": {"$ref": "#/data/1"}
    }

    # The JsonRef.replace class method will replace JSON references within the
    # document
    pprint(JsonRef.replace(document))

.. testoutput::

    {'data': ['a', 'b', 'c'], 'reference': 'b'}


:class:`JsonRef` Objects
========================

:class:`JsonRef` objects are the backbone of the library, and used to replace
the JSON reference objects within the data structure. They act as proxies to
whatever data the reference is pointing to, but only look up that data the
first time they are accessed. Once JSON reference objects have been replaced
within your data structure, you can use the data as if it does not contain
references at all.

The class method :meth:`JsonRef.replace` will replace all references is
whatever object you pass it. There are several other options you can pass, seen
below.

.. autoclass:: JsonRef(refobj, base_uri=None, loader=None, loader_kwargs=(), jsonschema=False, load_on_repr=None, base_doc=None)

    .. automethod:: replace(obj, base_uri=None, loader=None, loader_kwargs=(), jsonschema=False, load_on_repr=None, base_doc=None)

    :class:`JsonRef` instances proxy almost all operators and attributes to the
    referent data, which will be loaded when first accessed. The following
    attributes are not proxied:

    .. attribute:: __subject__

        Contains the referent data. Accessing this will cause the data to be
        loaded if it has not already been.

    .. attribute:: __reference__

        Contains the original JSON Reference object. Accessing this attribute
        will not cause the referent data to be loaded.


:mod:`json` module drop in replacement functions
================================================

load
----

Several functions are provided as drop in replacements to functions from the
:mod:`json` module. :func:`load` and :func:`loads` work just like their
:mod:`json` counterparts, except for references will already be replaced in the
return values. If you need to pass in custom parameters to :class:`JsonRef`,
keyword arguments can be provided by the `ref_kwargs` argument.

.. autofunction:: load

.. autofunction:: loads

dump
----

:func:`dump` and :func:`dumps` work just like their :mod:`json` counterparts,
except they output the original reference objects when encountering
:class:`JsonRef` instances.

.. autofunction:: dump

.. autofunction:: dumps
