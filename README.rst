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
    >>> pprint(jsonref.loads(json_str))
    {'a': 12345, 'b': 12345}
