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

    # The JsonRef constructor will replace JSON references within the document
    pprint(JsonRef(document))

.. testoutput::

    {'data': ['a', 'b', 'c'], 'reference': 'b'}


.. autoclass:: JsonRef(obj, base_uri=None, loader=None, loader_kwargs=(), jsonschema=False, load_on_repr=None, base_doc=None)
