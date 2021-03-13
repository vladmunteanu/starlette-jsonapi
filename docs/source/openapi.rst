OpenAPI
=======
OpenAPI schema generation, based on `apispec`_.
Please check the `sample-plain`_ example for an actual implementation.

.. note:: Please note this is an `experimental` integration and it's functionality can change without notice.

For the rest of this document, we will use the resources implemented in the Tutorial section.

1. Adding information on a resource
-----------------------------------
By default, resource classes include a basic description pointing to the JSON:API documentation
relevant to the corresponding operation, as well as a default response for 500 errors.

To overwrite the default information, or to add other fields,
an ``openapi_info`` dictionary can be specified on the resource class,
allowing information to be added for each specific handler.

Example:

.. code-block:: python

    from starlette.responses import Response
    from starlette_jsonapi.resource import BaseResource

    class ArticlesResource(BaseResource):
        type_ = 'articles'
        schema = ArticleSchema

        openapi_info = {
            'handlers': {
                'get': {
                    'description': 'Get an article by its ID'
                },
                'get_many': {
                    'description': 'Get a list of articles',
                    'summary': 'Short description for a list of articles',
                },
            }
        }

2. Adding information on a handler
----------------------------------
Additionally, an endpoint can be decorated with :meth:`starlette_jsonapi.openapi.with_openapi_info` to complement
details given on the class level.

Example:

.. code-block:: python

    from starlette.responses import Response
    from starlette_jsonapi.exceptions import ResourceNotFound
    from starlette_jsonapi.openapi import with_openapi_info
    from starlette_jsonapi.resource import BaseResource

    class ArticlesResource(BaseResource):
        type_ = 'articles'
        schema = ArticleSchema

        @with_openapi_info(responses={'200': ArticleSchema, '404': })
        async def get(self, id: Any, *args, **kwargs) -> Response:
            ...

        @with_openapi_info(
            responses={'200': ArticleSchema},
            request_body=ArticleSchema,
        )
        async def patch(self, id: Any, *args, **kwargs) -> Response:
            ...

3. Adding response body for a relationship resource
---------------------------------------------------
To add a response schema for a relationships endpoint,
the :meth:`starlette_jsonapi.openapi.response_for_relationship` utility can be used.

Example:

.. code-block:: python

    from starlette_jsonapi.openapi import with_openapi_info, response_for_relationship
    from starlette_jsonapi.resource import BaseRelationshipResource

    class ArticlesAuthorResource(BaseRelationshipResource):
        parent_resource = ArticlesResource
        relationship_name = 'author'

        @with_openapi_info(
            responses={
                '200': response_for_relationship(ArticlesResource.schema, relationship_name),
            },
        )
        async def get(self, parent_id: int, *args, **kwargs) -> Response:
            ...

4. Adding request body for a relationship resource
--------------------------------------------------
To add a request schema for a relationships endpoint,
the :meth:`starlette_jsonapi.openapi.request_for_relationship` utility can be used.

Example:

.. code-block:: python

    from starlette_jsonapi.openapi import with_openapi_info, request_for_relationship
    from starlette_jsonapi.resource import BaseRelationshipResource

    class ArticlesAuthorResource(BaseRelationshipResource):
        parent_resource = ArticlesResource
        relationship_name = 'author'

        @with_openapi_info(
            request_body=request_for_relationship(
                ArticlesResource.schema, relationship_name
            ),
        )
        async def patch(self, parent_id: int, *args, **kwargs) -> Response:
            ...

.. _apispec: https://apispec.readthedocs.io/
.. _sample-plain: https://github.com/vladmunteanu/starlette-jsonapi/tree/master/examples/sample-plain
