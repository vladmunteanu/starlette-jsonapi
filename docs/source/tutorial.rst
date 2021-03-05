Tutorial
========
For the rest of this section, let's imagine we're running a newspaper and we need to expose an API for its resources.
We are not going to bother with an actual ORM right now, so let's start by defining some simple classes for our models:

.. code-block:: python

    class Author:
        id: int
        name: str

    class Article:
        id: int
        title: str
        content: str
        author: Author
        comments: Optional[List['Comment']]  # this would be populated dynamically by an ORM

    class Comment:
        id: int
        message: str
        author: Author
        article: Article


1. Defining serialization / deserialization
-------------------------------------------
We then define how our resources should serialize / deserialize,
by subclassing :class:`starlette_jsonapi.schema.JSONAPISchema`,
which is an extended version of a `marshmallow-jsonapi`_ Schema,
with support for `starlette`_ route generation.

Let's take Article as an example:

.. code-block:: python

    from marshmallow_jsonapi import fields
    from starlette_jsonapi.schema import JSONAPISchema
    from starlette_jsonapi.relationship import JSONAPIRelationship

    class ArticleSchema(JSONAPISchema):
        class Meta:
            type_ = 'articles'

        # The `id` field is required, and in this case we don't
        # allow client generated IDs, so we're marking it as dump_only.
        # Other arguments are available too, check the `marshmallow` documentation.
        id = fields.Str(dump_only=True)

        # Marking fields as required, will result in 400 errors
        # if the client will not specify those fields when creating new articles.
        title = fields.Str(required=True)
        content = fields.Str(required=True)

        # Relationships are incredibly powerful in JSON:API.
        # They unlock compound documents and make traversing an API easier.
        author = JSONAPIRelationship(
           type_='authors',
           schema='AuthorSchema',
           required=True,
        )

        comments = JSONAPIRelationship(
            type_='comments',
            schema='CommentSchema',
            many=True,
        )

And serializing ``Article(id=1, title='Foo', content='Bar', author=Author(id=11, name=''))`` would look like this:

.. code-block:: javascript

    {
        "data": {
            "id": "1",
            "type": "articles",
            "attributes": {
                "title": "Foo",
                "content": "Bar"
            },
            "relationships": {
                "author": {
                    "data": {
                        "id": "11",
                        "type": "authors"
                    }
                }
            }
        }
    }

2. Implementing resource handlers
---------------------------------
We haven't exposed anything through the API yet, so we will look at that next.
We'll stick with Article and create the ``articles`` resource,
by subclassing :class:`starlette_jsonapi.resource.BaseResource`.

.. code-block:: python

    from starlette.responses import Response
    from starlette_jsonapi.resource import BaseResource

    class ArticlesResource(BaseResource):
        type_ = 'articles'
        schema = ArticleSchema

        # The route parameter should be a valid integer. We did not need to specify this,
        # the default being string, but we'd like automatic conversion to `int` in handlers.
        # More options available, consult the `starlette` routing documentation.
        id_mask = 'int'

        async def get(self, id: int, *args, **kwargs) -> Response:
            """ Will handle GET /articles/<id> """
            article = get_article_by_id(id)  # type: Article
            serialized_article = await self.serialize(data=article)
            return await self.to_response(serialized_article)

        async def patch(self, id: int, *args, **kwargs) -> Response:
            """ Will handle PATCH /articles/<id> """
            ...

        async def delete(self, id: int, *args, **kwargs) -> Response:
            """ Will handle DELETE /articles/<id> """
            ...

        async def post(self, *args, **kwargs) -> Response:
            """ Will handle POST /articles/ """
            ...

        async def get_many(self, *args, **kwargs) -> Response:
            """ Will handle GET /articles/ """
            ...

This is a basic implementation of a resource, without support for
compound documents or related resource.

3. Registering resource routes
------------------------------
Before we jump to more advanced features, let's look at how we register
the above resource in the Starlette routing mechanism.

.. code-block:: python

    from starlette.applications import Starlette

    app = Starlette()

    ArticlesResource.register_routes(app=app, base_path='/api/')

This will register the following routes:

- GET /api/articles/
- POST /api/articles/
- GET /api/articles/{id:int}
- PATCH /api/articles/{id:int}
- DELETE /api/articles/{id:int}

4. Related resources
--------------------
But as promised, JSON:API relationships are smart, so with a bit of work we can get compound documents,
and related resources too.

Let's go back to the ``ArticleSchema`` defined above and see how we can get more out of it.
First, we'll add links by using the route generation available in Starlette

.. code-block:: python

    class ArticleSchema(JSONAPISchema):
        class Meta:
            ....

            # We specify the link where this resource can be fetched.
            # `articles:get` is the `ArticlesResource.get` handler from above.
            self_route = 'articles:get'

            # The GET by ID url contains a path parameter for the ID, so we need
            # to specify where to get that field from.
            # The key is `id`, which is the name of path parameter as expected by Starlette.
            # The value is `<id>`, which is parsed to extract the field name that is available
            # on an actual article. (`article.id`)
            self_route_kwargs = {'id': '<id>'}

            # We also indicate the GET /articles/ route,
            # which is rendered as a link when fetching multiple articles.
            # `articles:get_many` is the `ArticlesResource.get_many` handler from above.
            self_route_many = 'articles:get_many'

        ....

        author = JSONAPIRelationship(
           ....
           # We indicate the related resource, which is not yet defined here,
           # but let's pretend it is for the sake of simplicity.
           # Notice that we're using a string, this is to help prevent circular imports
           # between resources by using the class name.
           related_resource='AuthorsResource',

           # The related route is used to generate the relationship's `related` link
           related_route='articles:author',

           # The related route looks like this /articles/1/author
           # so we need to indicate the URL path parameters.
           related_route_kwargs={'id': '<id>'},
        )

Once the ``author`` relationship is configured with
``related_resource``, ``related_route`` and ``related_route_kwargs``,
we can implement the :meth:`starlette_jsonapi.resource.BaseResource.get_related` handler on ``ArticlesResource``:

.. code-block:: python

    from starlette.exceptions import HTTPException

    class ArticlesResource(BaseResource):
        ....
        ....
        ....

        async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
            """ Will handle GET /articles/<id>/author """
            article = get_article_by_id(id)

            if relationship == 'author':
                serialized_author = await self.serialize_related(article.author)
                return await self.to_response(serialized_author)

            raise HTTPException(status_code=404)


5. Compound documents
---------------------
The previous chapter takes care of related resources, but what about compound documents through ``?include=`` requests?
`starlette-jsonapi` offers :meth:`starlette_jsonapi.resource.BaseResource.include_relations`, which subclasses can override to support compound document requests.
The default implementation will return a 400 Bad Request error, per json:api specifications.

For our example, we just need to override the default implementation of ``include_relations`` to allow include requests.
That's because the related objects are already populated on the resource in this example, so no additional database operations are required.
However, async ORMs generally can't implement lazy evaluation, so this method should be implemented to fetch the
related resources and make them available during serialization.

.. code-block:: python

    class ArticlesResource(BaseResource):
        ....
        ....
        ....

        async def include_relations(self, obj: Article, relations: List[str]):
            """
            For our tutorial's Article implementation, we don't need to fetch anything.
            We override the base implementation to support compound documents.
            """
            return None

6. Relationship resources
-------------------------
`JSON:API`_ also covers relationship resources, that handle URLs such as ``/articles/1/relationships/author``.
Although they can be considered optional if the relationship ``self`` URL isn't rendered, ``starlette-jsonapi`` defines
a base resource for writing relationship resources.

.. code-block:: python

    from starlette_jsonapi.resource import BaseRelationshipResource

    class ArticlesAuthorResource(BaseRelationshipResource):
        parent_resource = ArticlesResource
        relationship_name = 'author'

        # Just like we saw in the primary resource implementation,
        # we have `get`, `patch`, `delete` and `post` handlers that we can override.
        async def get(self, parent_id: int, *args, **kwargs) -> Response:
            """ Will handle GET /articles/<parent_id>/relationships/author """
            article = get_article_by_id(parent_id)
            return await self.to_response(await self.serialize(data=article))

        async def patch(self, parent_id: int, *args, **kwargs) -> Response:
            """ Will handle PATCH /articles/<parent_id>/relationships/author """
            ....

        async def delete(self, parent_id: int, *args, **kwargs) -> Response:
            """ Will handle DELETE /articles/<parent_id>/relationships/author """
            ....

        async def post(self, parent_id: int, *args, **kwargs) -> Response:
            """ Will handle POST /articles/<parent_id>/relationships/author """
            ....

We can also render the link associated to the above relationship resource by passing
``self_route`` and ``self_route_kwargs`` to the :class:`starlette_jsonapi.fields.JSONAPIRelationship` constructor.

.. code-block:: python

    class ArticleSchema(JSONAPISchema):
        ....

        author = JSONAPIRelationship(
           ....

           # The self route is used to generate the relationship's `self` link.
           self_route='articles:relationships-author',

           # The self route looks like this /articles/<parent_id>/relationships/author
           # so we need to indicate the URL path parameters.
           self_route_kwargs={'parent_id': '<id>'}
        )

Just as we did with primary resources, we need to register a relationship resource too:

.. code-block:: python

    from starlette.applications import Starlette

    app = Starlette()

    ArticlesResource.register_routes(app=app, base_path='/api/')
    ArticlesAuthorResource.register_routes(app=app)

In the end, our app will have the following routes registered:

- primary resource:

    - GET /api/articles/
    - POST /api/articles/
    - GET /api/articles/{id:int}
    - PATCH /api/articles/{id:int}
    - DELETE /api/articles/{id:int}

- related resources:

    - GET /api/articles/{id:int}/author

- relationship resources:

    - GET /api/articles/{parent_id:int}/relationships/author
    - PATCH /api/articles/{parent_id:int}/relationships/author
    - DELETE /api/articles/{parent_id:int}/relationships/author
    - POST /api/articles/{parent_id:int}/relationships/author

.. _starlette: https://www.starlette.io/
.. _JSON:API: https://jsonapi.org/
.. _marshmallow-jsonapi: https://marshmallow-jsonapi.readthedocs.io/
.. _marshmallow: https://marshmallow.readthedocs.io/
.. _starlette-jsonapi: https://pypi.org/project/starlette-jsonapi/
