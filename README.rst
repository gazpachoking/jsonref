jsonref
=======


.. image:: https://travis-ci.org/gazpachoking/jsonref.png?branch=master
    :target: https://travis-ci.org/gazpachoking/jsonref

``jsonref`` is an implementation of
`JSON Reference <http://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
for Python (supporting 2.6+ including Python 3).

This library effectively replaces all JSON reference objects with the referent
data. The references are evaluated lazily, so nothing is dereferenced until
it is used. This also means recursive references are supported, as long as you
do not try to iterate over the entire data structure.

.. code-block:: python

    >>> from pprint import pprint
    >>> import jsonref

    >>> # An example json document
    >>> json_str = """{"a": 12345, "b": {"$ref": "#/a"}}"""
    >>> data = jsonref.loads(json_str)
    >>> pprint(data)
    {'a': 12345, 'b': 12345}

The proxies are almost completely transparent, and support all operations on
the underlying data. (Please report if this is not the case, it should be fixed
or documented.)

.. code-block:: python

    >>> data["a"] == data["b"]
    True
    >>> data["b"] *= 2
    >>> pprint(data)
    {'a': 12345, 'b': 24690}
    >>> isinstance(data["b"], int)
    True
    >>> # You can tell it is a proxy by using the type function
    >>> type(data["b"])
    <class 'lazyproxy.LazyProxy'>
