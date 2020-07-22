import logging
from typing import Type, Any, List, Optional, Union, Dict

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
from starlette_jsonapi.utils import (
    parse_included_params,
    parse_sparse_fields_params, filter_sparse_fields,
    serialize_error,
)

logger = logging.getLogger(__name__)


class BaseResource(metaclass=RegisteredResourceMeta):
    """ A basic json:api resource implementation, data layer agnostic. """

    # The json:api type, used to compute the path for this resource
    # such that BaseResource.register_routes(app=app, base_path='/api/') will register
    # the following routes:
    # - GET `/api/<type_>/`
    # - POST `/api/<type_>/`
    # - GET `/api/<type_>/{id:str}`
    # - PATCH `/api/<type_>/{id:str}`
    # - DELETE `/api/<type_>/{id:str}`
    type_: str = ''

    # The json:api serializer, a subclass of JSONAPISchema.
    schema: Type[JSONAPISchema] = JSONAPISchema

    # High level filter for HTTP requests.
    # If you specify a smaller subset, any request that specifies a method
    # not listed here will result in a 405 error.
    allowed_methods = {'GET', 'PATCH', 'POST', 'DELETE'}

    # By default `str`, but other options are documented in Starlette:
    # 'str', 'int', 'float', 'uuid', 'path'
    id_mask: str = 'str'

    # Optional, by default this will equal `type_` and will be used as the `mount` name.
    # Impacts the result of `url_path_for`, so it can be used to support multiple resource versions.
    # For example:
    # ```
    # from starlette.applications import Starlette
    #
    # class SomeResource(BaseResource):
    #   type_ = 'examples'
    #   register_as = 'v2-examples'
    #
    # app = Starlette()
    # SomeResource.register_routes(app=app, base_path='/api/v2')
    # assert app.url_path_for('v2-examples:get_all') == '/api/v2/examples/'
    # ```
    # `url_path_for` will
    register_as: str = ''
    mount: Mount

    # Switch for controlling meta class registration.
    # Being able to refer to another resource via its name,
    # rather than directly passing it, will prevent circular imports in projects.
    # By default, subclasses are registered.
    register_resource = False

    # This will be populated when routes are registered and we detect related resources.
    # Used in `serialize_related`.
    _related: Dict[str, Type['BaseResource']]

    def __init__(self, request: Request, request_context: dict = None, *args, **kwargs) -> None:
        self.request = request
        self.request_context = request_context or {}

    async def get(self, id=None, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def patch(self, id=None, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def delete(self, id=None, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def get_all(self, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def post(self, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        """
        Subclasses should implement this if they specify relationships
        and want to support fetching related resources.
        By default returns a 405 error.
        """
        raise JSONAPIException(status_code=405)

    async def deserialize_body(self, partial=None) -> dict:
        """ Returns the request body as defined by this Resource's `schema`."""
        raw_body = await self.validate_body(partial=partial)
        deserialized_body = self.schema(app=self.request.app).load(raw_body, partial=partial)
        return deserialized_body

    async def validate_body(self, partial=None) -> dict:
        """
        Validates the raw request body, raising JSONAPIException 400 errors if the body is not valid.
        Otherwise, the request.json() content is returned.
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

    async def serialize(self, data: Any, many=False, *args, **kwargs) -> dict:
        """
        Serializes data as a JSON:API payload and returns a `dict`
        which can be passed when calling `BaseResource.to_response`.

        Additional args and kwargs are passed to the `marshmallow` based Schema.
        """
        included_relations = await self._prepare_included(data=data, many=many)
        schema = self.schema(app=self.request.app, include_data=included_relations, *args, **kwargs)
        body = schema.dump(data, many=many)
        sparse_body = await self.process_sparse_fields(body, many=many)
        return sparse_body

    async def serialize_related(self, data: Any, many=False, *args, **kwargs) -> dict:
        """
        Serializes related data as a JSON:API payload and returns a `dict`
        which can be passed when calling `BaseResource.to_response`.

        When serializing related resources, the related items are passed as `data` instead of the parent objects.

        Additional args and kwargs are passed to the `marshmallow` based Schema.
        """
        relationship = self.request_context['relationship']
        parent_id = self.request_context['id']
        related_resource_cls = self.__class__._related[relationship]  # type: Type[BaseResource]
        related_route = f'{self.mount.name}:{relationship}'
        related_route_kwargs = {
            'id': parent_id,
            # 'relationship': relationship,
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
        sparse_body = await self.process_sparse_fields(body, many=many)
        return sparse_body

    async def to_response(self, data: dict, *args, **kwargs) -> JSONAPIResponse:
        """
        Wraps `data` in a JSONAPIResponse object and returns it.
        Additional args and kwargs are passed to the `starlette` based Response.
        """
        return JSONAPIResponse(
            content=data,
            *args, **kwargs,
        )

    @classmethod
    async def handle_error(cls, request: Request, exc: Exception) -> JSONAPIResponse:
        if not isinstance(exc, HTTPException):
            logger.exception('Encountered an error while handling request.')
        return serialize_error(exc)

    @classmethod
    async def handle_request(
            cls, handler_name: str, request: Request, request_context: dict = None,
            extract_id: bool = False, *args, **kwargs
    ) -> Response:
        """
        Handles a request by calling the appropriate handler.
        Additional args and kwargs are passed to the handler method,
        which is usually one of: `get`, `patch`, `delete`, `get_all` or `post`.
        """
        request_context = request_context or {}
        if extract_id:
            id_ = request.path_params.get('id')
            kwargs.update({'id': id_})
            request_context.update({'id': id_})

        try:
            if request.method not in cls.allowed_methods:
                raise JSONAPIException(status_code=405)
            resource = cls(request, request_context=request_context)
            handler = getattr(resource, handler_name, None)
            response = await handler(*args, **kwargs)  # type: Response
        except Exception as e:
            response = await cls.handle_error(request=request, exc=e)
        return response

    @classmethod
    async def handle_get(cls, request: Request):
        return await cls.handle_request(handler_name='get', request=request, extract_id=True)

    @classmethod
    async def handle_patch(cls, request: Request):
        return await cls.handle_request(handler_name='patch', request=request, extract_id=True)

    @classmethod
    async def handle_delete(cls, request: Request):
        return await cls.handle_request(handler_name='delete', request=request, extract_id=True)

    @classmethod
    async def handle_get_all(cls, request: Request):
        return await cls.handle_request(handler_name='get_all', request=request)

    @classmethod
    async def handle_post(cls, request: Request):
        return await cls.handle_request(handler_name='post', request=request)

    @classmethod
    async def handle_get_related(cls, request: Request, relationship: str = None):
        """ Handles related resources requests, such as /articles/1/author. """
        related_id = request.path_params.get('related_id')
        request_context = {'relationship': relationship, 'related_id': related_id}
        return await cls.handle_request(
            handler_name='get_related', request=request,
            relationship=relationship, related_id=related_id,
            request_context=request_context,
            extract_id=True,
        )

    @classmethod
    def register_routes(cls, app: Starlette, base_path: str):
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
                _partial(relationship=rel_name)(cls.handle_get_related),
                methods=['GET'],
                name=f'{rel_name}-id',
            )
            for rel_name, rel_class in cls._related.items()
        ]
        # attach related routes, example: /articles/1/author
        routes += [
            Route(
                '/{{id:{}}}/{}'.format(cls.id_mask, rel_name),
                _partial(relationship=rel_name)(cls.handle_get_related),
                methods=['GET'],
                name=rel_name,
            )
            for rel_name in cls._related
        ]

        # attach primary routes, example: /articles/ and /articles/1
        routes += [
            Route(
                '/{{id:{}}}'.format(cls.id_mask), cls.handle_get,
                methods=['GET'], name='get',
            ),
            Route(
                '/{{id:{}}}'.format(cls.id_mask), cls.handle_patch,
                methods=['PATCH'], name='patch',
            ),
            Route(
                '/{{id:{}}}'.format(cls.id_mask), cls.handle_delete,
                methods=['DELETE'], name='delete',
            ),
            Route(
                '/', cls.handle_get_all,
                methods=['GET'], name='get_all',
            ),
            Route(
                '/', cls.handle_post,
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

    # Methods used to generate compound documents
    # https://jsonapi.org/format/#document-compound-documents
    async def _prepare_included(self, data: Any, many: bool) -> Optional[List[str]]:
        include_param = parse_included_params(self.request)
        if not include_param:
            return None
        include_param_list = list(include_param)
        if many is True:
            for item in data:
                try:
                    await self.prepare_relations(obj=item, relations=include_param_list)
                except _StopInclude:
                    return None
        else:
            try:
                await self.prepare_relations(obj=data, relations=include_param_list)
            except _StopInclude:
                return None
        return include_param_list

    async def prepare_relations(self, obj: Any, relations: List[str]) -> None:
        """
        Should be implemented by subclasses in order to support compound documents
        for asynchronous objects that may need fetching.

        Example `relations`:
            url = /some-url?include=resource1,resource1.resource2
            relations = ['resource1', 'resource1.resource2']

        :param obj: an object that was passed to `serialize`
        :param relations: list of relations, ex: ['resource1', 'resource1.resource2']
        """
        raise _StopInclude

    # Methods used to implement sparse fields
    # https://jsonapi.org/format/#fetching-sparse-fieldsets
    async def process_sparse_fields(self, serialized_data: dict, many: bool = False) -> dict:
        """
        Processes sparse fields requests by cleaning the serialized
        data of extra attributes and relationships.
        """
        sparse_fields = parse_sparse_fields_params(self.request)
        if not sparse_fields or not serialized_data.get('data'):
            return serialized_data

        data = serialized_data['data']
        new_data = [] if many else {}  # type: Union[List, dict]

        included = serialized_data.get('included', None)
        new_included = []

        for resource_name, fields in sparse_fields.items():
            # filter sparse fields in `data`
            if many:
                for item in data:
                    if item['type'] == resource_name:
                        new_data.append(filter_sparse_fields(item, fields))  # type: ignore
            else:
                if data['type'] == resource_name:
                    new_data = filter_sparse_fields(data, fields)

            # filter sparse fields in `included`
            if included:
                for item in included:
                    if item['type'] == resource_name:
                        new_included.append(filter_sparse_fields(item, fields))

        new_serialized_data = serialized_data.copy()
        new_serialized_data['data'] = new_data
        if new_included:
            new_serialized_data['included'] = new_included

        return serialized_data


class _StopInclude(Exception):
    pass


class BaseRelationshipResource:
    """ A basic json:api relationships resource implementation, data layer agnostic. """
    # The parent resource that this relationship belongs to
    parent_resource: Type[BaseResource]
    # The relationship name, as found on the parent resource schema
    relationship_name: str
    # High level filter for HTTP requests.
    # If you specify a smaller subset, any request that specifies a method
    # not listed here will result in a 405 error.
    allowed_methods = {'GET', 'PATCH', 'POST', 'DELETE'}

    def __init__(self, request: Request, *args, **kwargs) -> None:
        self.request = request

    async def post(self, parent_id: str, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def get(self, parent_id: str, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def patch(self, parent_id: str, *args, **kwargs) -> Response:
        raise JSONAPIException(status_code=405)

    async def delete(self, parent_id: str, *args, **kwargs) -> Response:
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

    async def to_response(self, data: dict, *args, **kwargs) -> JSONAPIResponse:
        """
        Wraps `data` in a JSONAPIResponse object and returns it.
        Additional args and kwargs are passed to the `starlette` based Response.
        """
        return JSONAPIResponse(
            content=data,
            *args, **kwargs,
        )

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
    async def handle_error(cls, request: Request, exc: Exception) -> JSONAPIResponse:
        if not isinstance(exc, HTTPException):
            logger.exception('Encountered an error while handling request.')
        return serialize_error(exc)

    @classmethod
    async def handle_request(cls, request: Request, *args, **kwargs) -> Response:
        """
        Handles a request by calling the appropriate handler based on the request method.
        Additional args and kwargs are passed to the handler method,
        which is usually one of: `get`, `patch`, `delete`, or `post`.
        """
        try:
            if request.method not in cls.allowed_methods:
                raise JSONAPIException(status_code=405)
            kwargs.update(parent_id=request.path_params['parent_id'])
            resource = cls(request)
            handler = getattr(resource, request.method.lower(), None)
            response = await handler(*args, **kwargs)  # type: Response
        except Exception as e:
            response = await cls.handle_error(request=request, exc=e)
        return response

    @classmethod
    def register_routes(cls, app: Starlette, *args, **kwargs):
        if not cls.parent_resource.type_:
            raise Exception(
                'Cannot register a relationship resource if the `parent_resource` does not specify a `type_`.'
            )

        if not getattr(cls.parent_resource, 'mount', None):
            raise Exception('Parent resource should be registered first.')

        name = f'relationships-{cls.relationship_name}'
        cls.parent_resource.mount.routes.append(
            Route(
                name=name,
                path='/{{parent_id:{}}}/relationships/{}'.format(
                    cls.parent_resource.id_mask,
                    cls.relationship_name
                ),
                endpoint=cls.handle_request,
                methods=['GET', 'POST', 'PATCH', 'DELETE'],
            )
        )


def _partial(*args, **kwargs):
    """
    This is a temporary partial, since we cannot use functools.partial with Starlette due to asyncio bugs.
    https://github.com/encode/starlette/pull/984
    """
    def outer(f):
        async def inner(request: Request):
            return await f(request, *args, **kwargs)
        return inner
    return outer
