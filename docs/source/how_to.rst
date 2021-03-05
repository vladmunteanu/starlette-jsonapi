How to
======

Accessing the request
---------------------
While handling a request inside a resource, you can use ``self.request`` to access the `starlette Request`_ object.

.. _starlette Request: https://www.starlette.io/requests/

Accessing the deserialized body
-------------------------------
You can deserialize the body and raise validation errors by calling ``self.deserialize_body``.

Validation errors will result in 400 HTTP responses.

Formatting exceptions
---------------------
Exceptions that are raised inside handlers, are serialized as `JSON:API errors`_.
In some situations though, the handlers might not be called because the
exception is handled before the framework has a chance to catch it.
For this reason, registering application level exception handlers might be needed:

.. code-block:: python

    from starlette.applications import Starlette
    from starlette_jsonapi.utils import register_jsonapi_exception_handlers

    app = Starlette()
    register_jsonapi_exception_handlers(app)

.. _JSON:API errors: https://jsonapi.org/format/#errors

Absolute links
--------------
Links are relative by default, but you can add a static prefix to the generated
links url by adding an ``url_prefix`` attribute to your app instance.

.. code-block:: python

    from starlette.applications import Starlette

    app = Starlette()
    app.url_prefix = 'https://example.com'

Will produce the following links:

.. code-block:: python

    {
        'data': {
            'id': 'foo',
            'type': 'test-resource',
            'links': {
                'self': 'https://example.com/test-resource/foo',
            },
        },
        'links': {
            'self': 'https://example.com/test-resource/foo',
        },
    }

Client generated IDs
--------------------
The JSON:API spec mentions:

    A server MAY accept a client-generated ID along with a request to create a resource.

To enable client generated IDS, specify the Schema's ``id`` field without the usual ``dump_only``
attribute that has been presented in this documentation.
Doing this will make ``marshmallow`` read the ``id`` field when ``deserialize_body`` is called.

Note: Validation of the client generated ID is not provided by this framework, but the specification
mentions:

    An ID MUST be specified with an id key, the value of which MUST be a universally unique identifier.

If you intend to use ``uuid`` IDs, set ``id_mask = 'uuid'`` when defining the Resource class, and some validation
will be handled by Starlette.

Requests with malformed IDs will likely result in 404 errors.

Top level meta objects
----------------------
To include a ``meta`` object (`documentation <https://jsonapi.org/format/#document-meta>`_) in the top level
json:api response, you can pass a dictionary ``meta`` argument when calling
:meth:`starlette_jsonapi.resource.BaseResource.to_response`,
or :meth:`starlette_jsonapi.resource.BaseRelationshipResource.to_response`:

.. code-block:: python

    await self.to_response({'id': 123, ....}, meta={'copyright': 'FooBar'})

Versioning
----------
Versioning can be implemented by specifying ``register_as`` on the resource class.

.. code-block:: python

    from marshmallow import fields
    from starlette.applications import Starlette
    from starlette_jsonapi.resource import BaseResource
    from starlette_jsonapi.schema import JSONAPISchema

    class ExampleSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

    class ExampleResourceV1(BaseResource):
        type_ = 'examples'
        schema = ExampleSchema
        register_as = 'v1-examples'

    class ExampleResourceV2(BaseResource):
        type_ = 'examples'
        schema = ExampleSchema
        register_as = 'v2-examples'

    app = Starlette()
    ExampleResourceV1.register_routes(app, base_path='/v1/')
    ExampleResourceV2.register_routes(app, base_path='/v2/')

    # both resources are now accessible without conflicts:
    assert app.url_path_for('v1-examples:get_many') == '/v1/examples/'
    assert app.url_path_for('v2-examples:get_many') == '/v2/examples/'
