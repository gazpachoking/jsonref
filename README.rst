jsonref
=======

.. image:: https://travis-ci.org/gazpachoking/jsonref.png?branch=master
    :target: https://travis-ci.org/gazpachoking/jsonref

.. image:: https://coveralls.io/repos/gazpachoking/jsonref/badge.png?branch=master
    :target: https://coveralls.io/r/gazpachoking/jsonref


``jsonref`` is a library for automatic dereferencing of
`JSON Reference <http://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
objects for Python (supporting 2.6+ including Python 3).

This library lets you use a data structure with JSON reference objects, as if
the references had been replaced with the referent data.


.. code-block:: python

    >>> from pprint import pprint
    >>> import jsonref

    >>> # An example json document
    >>> json_str = """{"real": [1, 2, 3, 4], "ref": {"$ref": "#/real"}}"""
    >>> data = jsonref.loads(json_str)
    >>> pprint(data)  # Reference is not evaluated until here
    {'real': [1, 2, 3, 4], 'ref': [1, 2, 3, 4]}


Features
--------

* References are evaluated lazily. Nothing is dereferenced until it is used.

* Recursive references are supported, and create recursive python data
  structures.


References objects are actually replaced by lazy lookup proxy objects which are
almost completely transparent.

.. code-block:: python

    >>> data = jsonref.loads('{"real": [1, 2, 3, 4], "ref": {"$ref": "#/real"}}')
    >>> # You can tell it is a proxy by using the type function
    >>> type(data["real"]), type(data["ref"])
    (<class 'list'>, <class 'jsonref.JsonRef'>)
    >>> # You have direct access to the referent data with the __subject__
    >>> # attribute
    >>> type(data["ref"].__subject__)
    <class 'list'>
    >>> # If you need to get at the reference object
    >>> data["ref"].__reference__
    {'$ref': '#/real'}
    >>> # Other than that you can use the proxy just like the underlying object
    >>> ref = data["ref"]
    >>> isinstance(ref, list)
    True
    >>> data["real"] == ref
    True
    >>> ref.append(5)
    >>> del ref[0]
    >>> # Actions on the reference affect the real data (if it is mutable)
    >>> pprint(data)
    {'real': [2, 3, 4, 5], 'ref': [2, 3, 4, 5]}


.. image:: https://d2weczhvl823v0.cloudfront.net/gazpachoking/jsonref/trend.png
   :alt: Bitdeli badge
   :target: https://bitdeli.com/free

