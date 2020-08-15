===============
Getting Started
===============

**starlette_jsonapi** is based on the `JSON:API`_ specification.
Its mission is to offer the tools for writing a compliant service (written in async Python),
while keeping the core data agnostic.

If you are here, you probably agree that the REST paradigm came with a lot of good things,
to name a few:

- intuitive interfaces
- separation of client-server concerns
- improved scalability

But without a standard for defining payloads and interactions, things can get messy pretty fast.
That's where `JSON:API`_ comes into play. You should go check it out if you haven't already, it's full of good
intentions.

In a few words, the specification includes a set of rules for exposing and consuming an API,
as well as instructions and recommendations for setting up powerful features, similar to those of GraphQL -
sparse fieldsets, compound documents - while keeping the overall complexity low.

Since `starlette`_ is handling the web parts, and `marshmallow`_ + `marshmallow-jsonapi`_ the serialization,
you are free to choose your own ORM, be it synchronous or asynchronous.

Installing
----------
It is recommended to install `starlette-jsonapi`_ from PyPI:

.. code-block:: bash

    $ pip install starlette-jsonapi

You should also pin its version in the requirements file:

.. code-block:: bash

    $ pip freeze | grep "starlette-jsonapi" >> requirements.txt

Reading materials
-----------------

- `JSON:API`_ -> specification
- `starlette`_ -> ASGI framework
- `marshmallow`_ -> serialization / deserialization
- `marshmallow-jsonapi`_ -> JSON:API serialization / deserialization

Examples
--------
Head over to GitHub and study the `examples`_ directory for full implementations.

You can fire up `Postman`_ and try the bundled `collection <https://github.com/vladmunteanu/starlette-jsonapi/blob/master/examples/starlette_jsonapi_client_example.postman_collection.json>`_
against the example services.

If you like the included examples and wish to add one for an ORM of your choice,
feel free to open a pull request.

.. _JSON:API: https://jsonapi.org/
.. _starlette: https://www.starlette.io/
.. _marshmallow: https://marshmallow.readthedocs.io/
.. _marshmallow-jsonapi: https://marshmallow-jsonapi.readthedocs.io/
.. _starlette-jsonapi: https://pypi.org/project/starlette-jsonapi/
.. _Postman: https://www.postman.com/
.. _examples: https://github.com/vladmunteanu/starlette-jsonapi/tree/master/examples
