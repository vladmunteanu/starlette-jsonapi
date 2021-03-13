starlette-jsonapi
=================

A microframework created to help write `JSON:API`_ compliant services, in async Python,
on top of `starlette`_ and `marshmallow-jsonapi`_.

**starlette-jsonapi** does not come with a data layer implementation, so you should be able to pick
any available ORM (sync or async).
This also means that you are going to get a simple interface for writing `JSON:API`_ compliant resources,
with some helpers to make it easier.

Data access is on you, the default implementation will otherwise return 405 errors.

Features
--------

- 100% tests coverage
- basic `JSON:API`_ serialization and deserialization
- compound documents
- starlette friendly route generation
- exception handlers to serialize as `JSON:API`_ errors
- relationship resources
- related resources
- sparse fields
- support for client generated IDs
- support top level meta objects
- `pagination helpers <https://jsonapi.org/format/#fetching-pagination>`_

Todo
----

- `sorting helpers <https://jsonapi.org/format/#fetching-sorting>`_
- `support jsonapi objects <https://jsonapi.org/format/#document-jsonapi-object>`_
- `enforce member name validation <https://jsonapi.org/format/#document-member-names>`_
- `optionally enforce query name validation <https://jsonapi.org/format/#query-parameters>`_
- examples for other ORMs

.. _starlette: https://www.starlette.io/
.. _JSON:API: https://jsonapi.org/
.. _marshmallow-jsonapi: https://marshmallow-jsonapi.readthedocs.io/

.. toctree::
   :maxdepth: 1
   :hidden:

   getting_started
   tutorial
   how_to
   openapi
   API Reference <api_reference/modules>
