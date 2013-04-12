jsonref
=======


.. image:: https://travis-ci.org/gazpachoking/jsonref.png?branch=master
    :target: https://travis-ci.org/gazpachoking/jsonref

``jsonref`` is an implementation of
`JSON Reference <http://tools.ietf.org/id/draft-pbryan-zyp-json-ref-03.html>`_
for Python (supporting 2.6+ including Python 3).

This library lets you use a data structure with JSON reference objects, as if
the references had been replaced with the referent data. The references are
evaluated lazily, so nothing is dereferenced until it is used. This also means
recursive references are supported, as long as you do not try to iterate over
the entire data structure.

.. code-block:: python

    >>> from pprint import pprint
    >>> import jsonref

    >>> # An example json document
    >>> json_str = """{"real": [1, 2, 3, 4], "ref": {"$ref": "#/real"}}"""
    >>> data = jsonref.loads(json_str)
    >>> pprint(data)  # Reference is not evaluated until here
    {'real': [1, 2, 3, 4], 'ref': [1, 2, 3, 4]}

References objects are replaced by lazy lookup proxy objects
(:class:`LazyProxy`.) The proxies are almost completely transparent,
and support almost all operations on the underlying data. They differ in
operation only with the built-in function :func:`type`, and with the
:attr:`LazyProxy.__subject__` attribute, which holds the actual object.

.. code-block:: python

    >>> # You can tell it is a proxy by using the type function
    >>> type(data["real"]), type(data["ref"])
    (<class 'list'>, <class 'lazyproxy.LazyProxy'>)
    >>> # You can access the underlying object with the __subject__ attribute
    >>> type(data["ref"].__subject__)
    <class 'list'>
    >>> # Other than that you can use the proxy just like the underlying object
    >>> ref = data["ref"]
    >>> isinstance(ref, list)
    True
    >>> data["real"] == ref
    True
    >>> ref.append(5)
    >>> del ref[0]
    >>> pprint(data)
    {'real': [1, 2, 3, 4], 'ref': [2, 3, 4, 5]}
