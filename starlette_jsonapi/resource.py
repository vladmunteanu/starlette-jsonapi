import logging
from typing import Type, Any, List, Optional, Union

from marshmallow.exceptions import ValidationError
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route, Mount

from starlette_jsonapi.exceptions import JSONAPIException, HTTPException
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema
from starlette_jsonapi.utils import (
    parse_included_params,
    parse_sparse_fields_params, filter_sparse_fields,
    serialize_error,
)

logger = logging.getLogger(__name__)


class BaseResource:
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

    # Optional, by default this will equal `type_` and will be used to register the Mount name.
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

    def __init__(self, request: Request, *args, **kwargs) -> None:
        self.request = request

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
            raise JSONAPIException(status_code=400, detail='Could not read request body.')

        errors = self.schema(app=self.request.app).validate(body, partial=partial)
        if errors:
            logger.debug('Could not validate request body according to JSON:API spec: %s.', errors)
            raise JSONAPIException(status_code=400, errors=errors.get('errors'))
        return body

    async def serialize(self, data: Any, many=False) -> JSONAPIResponse:
        """ Serializes data as a JSON:API payload and returns a JSONAPIResponse which can be served to clients. """
        included_relations = await self._prepare_included(data=data, many=many)
        schema = self.schema(app=self.request.app, include_data=included_relations)
        body = schema.dump(data, many=many)
        sparse_body = await self.process_sparse_fields(body, many=many)
        return JSONAPIResponse(
            content=sparse_body,
        )

    @classmethod
    async def handle_error(cls, request: Request, exc: Exception) -> JSONAPIResponse:
        if not isinstance(exc, HTTPException):
            logger.exception('Encountered an error while handling request.')
        return serialize_error(exc)

    @classmethod
    async def handle_request(
            cls, handler_name: str, request: Request,
            extract_id: bool = False, *args, **kwargs
    ) -> Response:
        """
        Handles a request by calling the appropriate handler.
        Additional args and kwargs are passed to the handler method,
        which is usually one of: `get`, `patch`, `delete`, `get_all` or `post`.
        """
        if extract_id:
            id_ = request.path_params.get('id')
            kwargs.update({'id': id_})

        try:
            if request.method not in cls.allowed_methods:
                raise JSONAPIException(status_code=405)
            resource = cls(request)
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
    def register_routes(cls, app: Starlette, base_path: str):
        if not cls.type_:
            raise Exception('Cannot register a resource without specifying its `type_`.')
        name = cls.register_as or cls.type_
        app.routes.append(
            Mount(
                name=name,
                path='{}/{}'.format(base_path.rstrip('/'), cls.type_),
                routes=[
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
                ],
            )
        )

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

    async def serialize(self, data: Any, many=False) -> JSONAPIResponse:
        """
        Serializes relationship for an object represented by the parent resource.
        """
        relationship = self._get_relationship_field()
        body = relationship.serialize(self.relationship_name, data)
        return JSONAPIResponse(
            content=body,
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

        parent_name = cls.parent_resource.register_as or cls.parent_resource.type_

        # find the parent mount and append the new Route to it
        for route in app.routes:
            if isinstance(route, Mount):
                if getattr(route, 'name', None) == parent_name:
                    route.routes.append(
                        Route(
                            name=cls.relationship_name,
                            path='/{{parent_id:{}}}/relationships/{}'.format(
                                cls.parent_resource.id_mask,
                                cls.relationship_name
                            ),
                            endpoint=cls.handle_request,
                            methods=['GET', 'POST', 'PATCH', 'DELETE'],
                        )
                    )
                    break
        else:
            raise Exception('Parent resource should be registered first.')
