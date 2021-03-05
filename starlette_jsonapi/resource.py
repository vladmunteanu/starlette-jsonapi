import functools
import logging
from typing import Type, Any, List, Optional, Union, Sequence, Dict

from marshmallow.exceptions import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route, Mount

from starlette_jsonapi.exceptions import JSONAPIException, HTTPException
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.meta import RegisteredResourceMeta
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema
from starlette_jsonapi.pagination import BasePagination, Pagination
from starlette_jsonapi.utils import (
    parse_included_params, serialize_error, process_sparse_fields, parse_sparse_fields_params,
)

logger = logging.getLogger(__name__)


class _BaseResourceHandler:
    """
    Base implementation of common json:api resource handler logic.
    You should look at BaseResource or BaseRelationshipResource instead.
    """

    #: High level filter for HTTP requests.
    #: If you specify a smaller subset, any request with a method
    #: not listed here will result in a 405 error.
    allowed_methods = {'GET', 'PATCH', 'POST', 'DELETE'}

    def __init__(self, request: Request, request_context: dict, *args, **kwargs) -> None:
        """
        A Resource instance is created for each HTTP request,
        and the :class:`starlette.requests.Request`
        is passed, as well as the context, which can be used to store information
        without altering the request object.
        """
        #: Instance attribute representing the current HTTP request.
        self.request: Request = request
        #: Instance attribute representing the context of the current HTTP request.
        #: Can be used to store additional information for the duration of a request.
        self.request_context: dict = request_context

    @classmethod
    async def before_request(cls, request: Request, request_context: dict) -> None:
        """
        Optional hook that can be implemented by subclasses to execute logic before a request is handled.
        This will not run if an exception is raised before :meth:`handle_request` is called.

        For more advanced hooks, check starlette middleware.

        :param request: The current HTTP request
        :param request_context: The current request's context.
        """
        return

    @classmethod
    async def after_request(cls, request: Request, request_context: dict, response: Response) -> None:
        """
        Optional hook that can be implemented by subclasses to execute logic after a request is handled.
        This will not run if an exception is raised before :meth:`handle_request` is called, or if
        :meth:`before_request` throws an error.

        For more advanced hooks, check starlette middleware.

        :param request: The current HTTP request
        :param request_context: The current request's context.
        :param response: The Starlette Response object
        """
        return

    @classmethod
    async def handle_error(cls, request: Request, request_context: dict, exc: Exception) -> JSONAPIResponse:
        """
        Handles errors that may appear while a request is processed, taking care of serializing them
        to ensure the final response is json:api compliant.

        Subclasses can override this to add custom error handling.

        :param request: current HTTP request
        :param request_context: current request context
        :param exc: encountered error
        """
        if not isinstance(exc, HTTPException):
            logger.exception('Encountered an error while handling request.')
        return serialize_error(exc)

    async def to_response(self, data: dict, meta: dict = None, *args, **kwargs) -> JSONAPIResponse:
        """
        Wraps ``data`` in a :class:`starlette_jsonapi.responses.JSONAPIResponse` object and returns it.
        If ``meta`` is specified, it will be included as the top level ``"meta"`` object in the json:api response.
        Additional args and kwargs are passed when instantiating a new :class:`JSONAPIResponse`.

        :param data: Serialized resources / errors, as returned by :meth:`serialize` or :meth:`serialize_related`.
        :param meta: Optional dictionary with meta information. Overwrites any existing top level `meta` in ``data``.
        """
        if meta:
            data = data.copy()
            data.update(meta=meta)
        return JSONAPIResponse(
            content=data,
            *args, **kwargs,
        )

    @classmethod
    async def handle_request(
        cls, handler_name: str, request: Request, request_context: dict = None,
        extract_params: List[str] = None, *args, **kwargs
    ) -> Response:
        """
        Handles a request by calling the appropriate handler.
        Additional args and kwargs are passed to the handler method, which is usually one of:
        :meth:`get`, :meth:`patch`, :meth:`delete`, :meth:`get_many` or :meth:`post`.
        """
        request_context = request_context or {}
        extract_params = extract_params or []
        for path_param in extract_params:
            value = request.path_params.get(path_param)
            kwargs.update({path_param: value})
            request_context.update({path_param: value})

        # run before request hook
        try:
            await cls.before_request(request=request, request_context=request_context)
        except Exception as before_request_exc:
            response: Response = await cls.handle_error(request, request_context, exc=before_request_exc)
        else:
            # safely execute the handler
            try:
                if request.method not in cls.allowed_methods:
                    raise JSONAPIException(status_code=405)
                resource = cls(request, request_context, *args, **kwargs)
                handler = getattr(resource, handler_name, None)
                response = await handler(*args, **kwargs)
            except Exception as e:
                response = await cls.handle_error(request, request_context, exc=e)

            # run after request hook
            try:
                await cls.after_request(request=request, request_context=request_context, response=response)
            except Exception as after_request_exc:
                response = await cls.handle_error(request, request_context, exc=after_request_exc)

        return response

    def process_sparse_fields_request(self, serialized_data: dict, many: bool = False) -> dict:
        """
        Processes sparse fields requests by calling
        :func:`starlette_jsonapi.utils.process_sparse_fields`.

        Can be overridden in subclasses if custom behavior is needed.

        :param serialized_data: The complete json:api dict representation.
        :param many: Whether ``serialized_data`` should be treated as a collection.
        """
        return process_sparse_fields(
            serialized_data, many=many,
            sparse_fields=parse_sparse_fields_params(self.request),
        )


class BaseResource(_BaseResourceHandler, metaclass=RegisteredResourceMeta):
    """A basic json:api resource implementation, data layer agnostic.

    Subclasses can achieve basic functionality by implementing:

        :meth:`get` :meth:`patch` :meth:`delete` :meth:`get_many` :meth:`post`

    Additionally:

        - requests for compound documents (Example: ``GET /api/v1/articles?include=author``) can be
          supported by overriding :meth:`include_relations` to pre-populate
          the related objects before serializing.

        - requests for related objects (Example: ``GET /api/v1/articles/123/author``), can be supported
          by overriding the :meth:`get_related` handler.
          Related objects should be serialized with :meth:`serialize_related`.

    By default, requests for sparse fields will be handled by the :class:`BaseResource` implementation,
    without any effort required.

    Example subclass:

    .. code-block:: python

        class ExampleResource(BaseResource):
            type_ = 'examples'
            allowed_methods = {'GET'}

            async def get(self, id: str, *args, **kwargs) -> Response:
                obj = Example.objects.get(id)
                serialized_obj = await self.serialize(obj)
                return await self.to_response(serialized_obj)

            async def get_many(self, *args, **kwargs) -> Response:
                objects = Example.objects.all()
                serialized_objects = await self.serialize(objects, many=True)
                return await self.to_response(serialized_objects)

    """

    #: The json:api type, used to compute the path for this resource
    #: such that ``BaseResource.register_routes(app=app, base_path='/api/')`` will register
    #: the following routes:
    #:
    #: - ``GET /api/<type_>/``
    #: - ``POST /api/<type_>/``
    #: - ``GET /api/<type_>/{id:str}``
    #: - ``PATCH /api/<type_>/{id:str}``
    #: - ``DELETE /api/<type_>/{id:str}``
    type_: str = ''

    #: The json:api serializer, a subclass of :class:`JSONAPISchema`.
    schema: Type[JSONAPISchema] = JSONAPISchema

    #: By default `str`, but other options are documented in Starlette:
    #: ``'str', 'int', 'float', 'uuid', 'path'``
    id_mask: str = 'str'

    #: Pagination class, subclass of :class:`BasePagination`
    pagination_class: Optional[Type[BasePagination]] = None

    register_as: str = ''
    """
    Optional, by default this will equal :attr:`type_` and will be used as the :attr:`mount` name.
    Impacts the result of ``url_path_for``, so it can be used to support multiple resource versions.

    .. code-block:: python

        from starlette.applications import Starlette

        class ExamplesResource(BaseResource):
            type_ = 'examples'
            register_as = 'v2-examples'

        app = Starlette()
        ExamplesResource.register_routes(app=app, base_path='/api/v2')
        assert app.url_path_for('v2-examples:get_many') == '/api/v2/examples/'
    """

    #: The underlying :class:`starlette.routing.Mount` object used for registering routes.
    mount: Mount

    #: Switch for controlling meta class registration.
    #: Being able to refer to another resource via its name,
    #: rather than directly passing it, will prevent circular imports in projects.
    #: By default, subclasses are registered.
    register_resource = False

    #: This will be populated when routes are registered and we detect related resources.
    #: Used in :meth:`serialize_related`.
    _related: Dict[str, Type['BaseResource']]

    async def get(self, id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle ``GET /<id>`` requests. """
        raise JSONAPIException(status_code=405)

    async def patch(self, id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle ``PATCH /<id>`` requests. """
        raise JSONAPIException(status_code=405)

    async def delete(self, id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle ``DELETE /<id>`` requests. """
        raise JSONAPIException(status_code=405)

    async def get_many(self, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle ``GET /`` requests. """
        raise JSONAPIException(status_code=405)

    async def post(self, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle ``POST /`` requests. """
        raise JSONAPIException(status_code=405)

    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        """
        Subclasses should implement this to handle ``GET /<id>/<relationship>[/<related_id>]``.
        By default returns a 405 error.

        :param id: the resource id
        :param relationship: name of the relationship
        :param related_id: optional, an id can be specified to identify a specific related resource,
                           in case of one-to-many relationships.
        """
        raise JSONAPIException(status_code=405)

    async def include_relations(self, obj: Any, relations: List[str]) -> None:
        """
        Subclasses should implement this to support requests for compound documents.
        `<https://jsonapi.org/format/#document-compound-documents>`_

        By default returns a 400 error, according to the json:api specification.

        Example request URL: ``GET /?include=relationship1,relationship1.child_relationship``
        Example relations: ``['relationship1', 'relationship1.child_relationship']``

        :param obj: an object that was passed to :meth:`serialize`
        :param relations: list of relations described above
        """
        raise JSONAPIException(status_code=400)

    async def deserialize_body(self, partial=None) -> dict:
        """
        Deserializes the request body according to :attr:`schema`.

        :param partial: Can be set to ``True`` during PATCH requests, to ignore missing fields.
                        For more advanced uses, like a specific iterable of missing fields,
                        you should check the marshmallow documentation.
        :raises: :exc:`starlette_jsonapi.exceptions.JSONAPIException`
        """
        raw_body = await self.validate_body(partial=partial)
        deserialized_body = self.schema(app=self.request.app).load(raw_body, partial=partial)
        return deserialized_body

    async def validate_body(self, partial=None) -> dict:
        """
        Validates the raw request body, raising :exc:`JSONAPIException` 400 errors
        if the body is not valid according to :attr:`schema`.
        Otherwise, the whole request body is loaded as a ``dict`` and returned.

        :param partial: Can be set to ``True`` during PATCH requests, to ignore missing fields.
                        For more advanced uses, like a specific iterable of missing fields,
                        you should check the marshmallow documentation.
        :raises: :exc:`starlette_jsonapi.exceptions.JSONAPIException`
        """
        content_type = self.request.headers.get('content-type')
        if self.request.method in ('POST', 'PATCH') and content_type != 'application/vnd.api+json':
            raise JSONAPIException(
                status_code=400,
                detail='Incorrect or missing Content-Type header, expected `application/vnd.api+json`.',
            )
        try:
            body = await self.request.json()
        except Exception:
            logger.debug('Could not read request body.', exc_info=True)
            raise JSONAPIException(status_code=400, detail='Could not read request body as JSON.')

        errors = self.schema(app=self.request.app).validate(body, partial=partial)
        if errors:
            logger.debug('Could not validate request body according to JSON:API spec: %s.', errors)
            raise JSONAPIException(status_code=400, errors=errors.get('errors'))
        return body

    async def serialize(
            self, data: Any,
            many: bool = False,
            paginate: bool = False,
            pagination_kwargs: dict = None,
            *args, **kwargs
    ) -> dict:
        """
        Serializes data as a JSON:API payload and returns a `dict`
        which can be passed when calling :meth:`to_response`.

        Extra parameters can be sent inside the pagination process via ``pagination_kwargs``
        Additional args and kwargs are passed when initializing a new :attr:`schema`.

        :param data: an object, or a sequence of objects to be serialized
        :param many: whether ``data`` should be serialized as a collection
        :param paginate: whether to apply pagination to the given ``data``
        :param pagination_kwargs: additional parameters which are passed to :meth:`paginate_request`.
        """
        links = None
        if paginate:
            data, links = await self.paginate_request(data, pagination_kwargs)

        included_relations = await self._prepare_included(data=data, many=many)
        schema = self.schema(app=self.request.app, include_data=included_relations, *args, **kwargs)
        body = schema.dump(data, many=many)
        sparse_body = self.process_sparse_fields_request(body, many=many)

        if links:
            sparse_body['links'] = links
        return sparse_body

    async def serialize_related(self, data: Any, many=False, *args, **kwargs) -> dict:
        """
        Serializes related data as a JSON:API payload and returns a ``dict``
        which can be passed when calling :meth:`to_response`.

        When serializing related resources, the related items are passed as ``data``,
        instead of the parent objects.

        Additional args and kwargs are passed when initializing a new :attr:`schema`.

        :param data: an object, or a sequence of objects to be serialized
        :param many: whether ``data`` should be serialized as a collection
        """
        relationship = self.request_context['relationship']
        parent_id = self.request_context['id']
        related_resource_cls = self.__class__._related[relationship]  # type: Type[BaseResource]
        related_route = f'{self.mount.name}:{relationship}'
        related_route_kwargs = {
            'id': parent_id,
        }
        if self.request_context.get('related_id'):
            related_route += '-id'
            related_route_kwargs.update(related_id='<id>')

        related_schema = related_resource_cls.schema(
            app=self.request.app,
            self_related_route=related_route,
            self_related_route_kwargs=related_route_kwargs,
            *args, **kwargs,
        )  # type: JSONAPISchema
        body = related_schema.dump(data, many=many)
        sparse_body = self.process_sparse_fields_request(body, many=many)
        return sparse_body

    async def paginate_request(self, object_list: Sequence, pagination_kwargs: dict = None) -> Pagination:
        """
        Applies pagination using the helper class defined by :attr:`pagination_class`.
        Additional parameters can pe saved on the ``paginator`` instance using ``pagination_kwargs``.
        """
        if not self.pagination_class:
            raise Exception('Pagination class must be defined to use pagination')

        pagination_kwargs = pagination_kwargs or {}
        paginator = self.pagination_class(request=self.request, data=object_list, **pagination_kwargs)
        pagination = paginator.get_pagination()
        return pagination

    @classmethod
    def register_routes(cls, app: Starlette, base_path: str = ''):
        """
        Registers URL routes associated to this resource, using a :class:`starlette.routing.Mount`.
        The mount name will be set based on :attr:`type_`, or :attr:`register_as`, if defined.
        All routes will then be registered under this mount.

        If the configured :attr:`schema` defines relationships, then routes for related objects
        will also be registered.

        Let's take the articles resource as an example:.

        .. csv-table:: Registered Routes
            :header: "Name", "URL", "HTTP method", "Description"

            "articles:get_many", "/articles/", "GET", "Retrieve articles"
            "articles:post", "/articles/", "POST", "Create an article"
            "articles:get", "/articles/<id>", "GET", "Retrieve an article by ID"
            "articles:patch", "/articles/<id>", "PATCH", "Update an article by ID"
            "articles:delete", "/articles/<id>", "DELETE", "Delete an article by ID"
            "articles:author", "/articles/<id>/author", "GET", "Retrieve an article's author"
            "articles:comments", "/articles/<id>/comments", "GET", "Retrieve an article's comments"
            "articles:comments-id", "/articles/<id>/comments/<related_id>", "GET", "Retrieve an article comment by ID"

        """
        if not cls.type_ or not cls.schema:
            raise Exception('Cannot register a resource without specifying its `type_` and its `schema`.')

        # find relationships with `related_resource` specified
        cls._related = {}
        for fname, field in cls.schema.get_fields().items():
            if isinstance(field, JSONAPIRelationship):
                if field.related_resource:
                    cls._related[fname] = field.related_resource_class

        # attach secondary related routes, example: /articles/1/author/1
        routes = [
            Route(
                '/{{id:{}}}/{}/{{related_id:{}}}'.format(cls.id_mask, rel_name, rel_class.id_mask),
                functools.partial(
                    cls.handle_request,
                    'get_related',
                    relationship=rel_name,
                    extract_params=['id', 'related_id'],
                    request_context={'relationship': rel_name},
                ),
                methods=['GET'],
                name=f'{rel_name}-id',
            )
            for rel_name, rel_class in cls._related.items()
        ]
        # attach related routes, example: /articles/1/author
        routes += [
            Route(
                '/{{id:{}}}/{}'.format(cls.id_mask, rel_name),
                functools.partial(
                    cls.handle_request,
                    'get_related',
                    relationship=rel_name,
                    extract_params=['id'],
                    request_context={'relationship': rel_name},
                ),
                methods=['GET'],
                name=rel_name,
            )
            for rel_name in cls._related
        ]

        # attach primary routes, example: /articles/ and /articles/1
        routes += [
            Route(
                '/{{id:{}}}'.format(cls.id_mask),
                functools.partial(cls.handle_request, 'get', extract_params=['id']),
                methods=['GET'], name='get',
            ),
            Route(
                '/{{id:{}}}'.format(cls.id_mask),
                functools.partial(cls.handle_request, 'patch', extract_params=['id']),
                methods=['PATCH'], name='patch',
            ),
            Route(
                '/{{id:{}}}'.format(cls.id_mask),
                functools.partial(cls.handle_request, 'delete', extract_params=['id']),
                methods=['DELETE'], name='delete',
            ),
            Route(
                '/',
                functools.partial(cls.handle_request, 'get_many'),
                methods=['GET'], name='get_many',
            ),
            Route(
                '/',
                functools.partial(cls.handle_request, 'post'),
                methods=['POST'], name='post',
            ),
        ]

        name = cls.register_as or cls.type_
        cls.mount = Mount(
            name=name,
            path='{}/{}'.format(base_path.rstrip('/'), cls.type_),
            routes=routes,
        )

        app.routes.append(cls.mount)

    async def _prepare_included(self, data: Any, many: bool) -> Optional[List[str]]:
        """
        Processes the ``include`` query parameter and calls :meth:`include_relations`
        for every object in ``data``, to enable requests for compound documents.
        """
        include_param = parse_included_params(self.request)
        if not include_param:
            return None
        include_param_list = list(include_param)
        if many is True:
            for item in data:
                await self.include_relations(obj=item, relations=include_param_list)
        else:
            await self.include_relations(obj=data, relations=include_param_list)
        return include_param_list


class _StopInclude(Exception):
    pass


class BaseRelationshipResource(_BaseResourceHandler):
    """ A basic json:api relationships resource implementation, data layer agnostic. """

    #: The parent resource that this relationship belongs to
    parent_resource: Type[BaseResource]

    #: The relationship name, as found on the parent resource schema
    relationship_name: str

    async def post(self, parent_id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle POST /<parent_id>/relationships/<relationship> requests. """
        raise JSONAPIException(status_code=405)

    async def get(self, parent_id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle GET /<parent_id>/relationships/<relationship> requests. """
        raise JSONAPIException(status_code=405)

    async def patch(self, parent_id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle PATCH /<parent_id>/relationships/<relationship> requests. """
        raise JSONAPIException(status_code=405)

    async def delete(self, parent_id: Any, *args, **kwargs) -> Response:
        """ Subclasses should implement this to handle DELETE /<parent_id>/relationships/<relationship> requests. """
        raise JSONAPIException(status_code=405)

    def _get_relationship_field(self) -> JSONAPIRelationship:
        """ Returns the relationship field defined on the parent resource schema. """
        schema = self.parent_resource.schema(app=self.request.app)
        declared_fields = schema.declared_fields
        relationship = declared_fields.get(self.relationship_name)
        if not relationship or not isinstance(relationship, JSONAPIRelationship):
            raise AttributeError(f'Parent schema does not define `{self.relationship_name}` relationship.')
        return relationship

    async def serialize(self, data: Any) -> dict:
        """
        Serializes the parent instance relationships as a JSON:API payload, returning
        a `dict` which can be passed to `BaseRelationshipResource.to_response`.
        """
        relationship = self._get_relationship_field()
        body = relationship.serialize(self.relationship_name, data)
        return body

    async def deserialize_ids(self) -> Union[None, str, List[str]]:
        """
        Parses the request body to find relationship ids.
        Raises JSONAPIException with a 400 status code if the payload does not pass
        json:api validation.
        """
        content_type = self.request.headers.get('content-type')
        if self.request.method in ('POST', 'PATCH') and content_type != 'application/vnd.api+json':
            raise JSONAPIException(
                status_code=400,
                detail='Incorrect or missing Content-Type header, expected `application/vnd.api+json`.',
            )
        try:
            body = await self.request.json()
        except Exception:
            logger.debug('Could not read request body.', exc_info=True)
            raise JSONAPIException(status_code=400, detail='Could not read request body.')

        relationship = self._get_relationship_field()
        try:
            deserialized_ids = relationship.deserialize(body)
        except ValidationError as exc:
            logger.debug('Could not validate request body according to JSON:API spec: %s.', exc.messages)
            errors = []
            if isinstance(exc.messages, list) and len(exc.messages) > 0:
                for message in exc.messages:
                    errors.append({'detail': message})

            raise JSONAPIException(status_code=400, errors=errors)
        return deserialized_ids

    @classmethod
    def register_routes(cls, *args, **kwargs):
        """
        Registers URL routes associated to this resource.
        Should be called after calling register_routes for the parent resource.

        The following URL routes will be registered, relative to :attr:`parent_resource`:

            - **Relative name:** ``relationships-<relationship_name>``
            - **Relative URL:** ``/<parent_id>/relationships/<relationship_name>``

        For example, a relationship resource that would handle article authors
        would be registered relative to the articles resource as:

            - **Relative name:** ``relationships-author``
            - **Full name:** ``articles:relationships-author``
            - **Relative URL:** ``/<parent_id>/relationships/author``
            - **Full URL:** ``/articles/<parent_id>/relationships/author``
        """
        if not cls.parent_resource.type_:
            raise Exception(
                'Cannot register a relationship resource if the `parent_resource` does not specify a `type_`.'
            )

        if not getattr(cls.parent_resource, 'mount', None):
            raise Exception('Parent resource should be registered first.')

        name = f'relationships-{cls.relationship_name}'
        for method in cls.allowed_methods:
            cls.parent_resource.mount.routes.append(
                Route(
                    name=name,
                    path='/{{parent_id:{}}}/relationships/{}'.format(
                        cls.parent_resource.id_mask,
                        cls.relationship_name
                    ),
                    endpoint=functools.partial(cls.handle_request, method.lower(), extract_params=['parent_id']),
                    methods=[method],
                )
            )
