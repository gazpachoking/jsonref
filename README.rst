jsonref
=======


.. image:: https://travis-ci.org/gazpachoking/jsonref.png?branch=master
    :target: https://travis-ci.org/gazpachoking/jsonref

``jsonref`` is an implementation of
`JSON Reference <http://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
for Python (supporting 2.6+ including Python 3).

.. code-block:: python
    >>> from pprint import pprint
    >>> import jsonref

    >>> # An example json document
    >>> json_str = """{"a": 12345, "b": {"$ref": "#/a"}}"""
    >>> pprint(jsonref.loads(json_str))
    {'a': 12345, 'b': 12345}
