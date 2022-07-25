"""
Experimental support for generating OpenAPI 3.x specifications.

Example:

    .. code-block:: python

        from apispec import APISpec
        from starlette.applications import Starlette
        from starlette_jsonapi.openapi import JSONAPISchemaGenerator, JSONAPIMarshmallowPlugin

        schemas = JSONAPISchemaGenerator(
            APISpec(
                title='Example API',
                version='1.0',
                openapi_version='3.0.3',
                info={'description': 'An example API.'},
                plugins=[JSONAPIMarshmallowPlugin()],
            )
        )

        app = Starlette()

        # register resources routes on app

        schema_dict = schemas.get_schema(app.routes)

"""
import functools
import re
from collections import OrderedDict
from typing import List, Type, Union, Dict, Any

from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, OpenAPIConverter
from marshmallow_jsonapi.schema import SchemaOpts
from marshmallow.utils import is_collection
from marshmallow import fields as ma_fields
from marshmallow import Schema, validate, class_registry
from marshmallow.exceptions import RegistryError
from starlette.routing import BaseRoute, iscoroutinefunction_or_partial, Route
from starlette.schemas import BaseSchemaGenerator, EndpointInfo
from starlette.convertors import CONVERTOR_TYPES

from starlette_jsonapi.constants import OPENAPI_INFO, CONTENT_TYPE_HEADER
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.schema import JSONAPISchema
from starlette_jsonapi.utils import safe_merge, isinstance_or_subclass


SchemaType = Union[str, dict, JSONAPISchema, Type[JSONAPISchema]]
SchemaOrExceptionType = Union[SchemaType, Exception, Type[Exception]]

EXPECTED_PATH_PARAMETERS = ['id', 'related_id', 'parent_id']

PATH_PARAMS_REGEX = '({{({}):({})}})'.format(
    '|'.join(EXPECTED_PATH_PARAMETERS), '|'.join(CONVERTOR_TYPES.keys())
)


class BaseExceptionSchema(Schema):
    pass


def get_openapi_parameter_type(parameter_type: str) -> str:
    if parameter_type == 'int':
        return 'integer'
    elif parameter_type == 'float':
        return 'number'
    else:
        return 'string'


class JSONAPISchemaConverter(OpenAPIConverter):
    def init_attribute_functions(self):
        super().init_attribute_functions()
        self.add_attribute_function(self.relationship_field)

    def fields2jsonschema(self, fields, *, ordered=False, partial=None):
        schema_list = [field.parent for field in fields.values()]
        if schema_list:
            if not isinstance_or_subclass(schema_list[0], JSONAPISchema):
                return super().fields2jsonschema(fields, partial=partial)
        default_fields = [
            ('id', None),
            ('type', {'type': 'string'}),
        ]
        jsonschema = {
            'type': 'object',
            'properties': OrderedDict(default_fields) if ordered else dict(default_fields),
        }  # type: dict
        properties = jsonschema['properties']
        if schema_list:
            properties['type']['enum'] = list({schema.Meta.type_ for schema in schema_list})

        for field_name, field_obj in fields.items():
            observed_field_name = field_obj.data_key or field_name
            prop = self.field2property(field_obj)
            if observed_field_name == 'id':
                properties[observed_field_name] = prop
            elif isinstance(field_obj, JSONAPIRelationship):
                properties.setdefault('relationships', {'type': 'object', 'properties': {}})
                properties['relationships']['properties'][observed_field_name] = prop
            else:
                properties.setdefault('attributes', {'type': 'object', 'properties': {}})
                properties['attributes']['properties'][observed_field_name] = prop
            # TODO: support meta fields

            if field_obj.required:
                if not partial or (
                    is_collection(partial) and field_name not in partial
                ):
                    if isinstance(field_obj, JSONAPIRelationship):
                        properties['relationships'].setdefault('required', []).append(observed_field_name)
                    else:
                        properties['attributes'].setdefault('required', []).append(observed_field_name)

        jsonschema['required'] = ['type']
        if 'attributes' in properties and 'required' in properties['attributes']:
            properties['attributes']['required'].sort()
            jsonschema['required'].append('attributes')
        if 'relationships' in properties and 'required' in properties['relationships']:
            properties['relationships']['required'].sort()
            jsonschema['required'].append('relationships')

        return jsonschema

    def relationship_field(self, field, **kwargs):
        ret = {}  # type: dict
        if isinstance(field, JSONAPIRelationship):
            ret['type'] = 'object'
            ret['properties'] = {
                'data': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'type': {'type': 'string', 'enum': [field.type_]},
                    },
                },
            }
            links_prop = {'type': 'object', 'properties': {}, 'readOnly': True}  # type: dict
            if field.related_route:
                links_prop['properties']['related'] = {'type': 'string'}
            if field.self_route:
                links_prop['properties']['self'] = {'type': 'string'}
            if links_prop['properties']:
                ret['properties']['links'] = links_prop

        return ret

    def get_ref_dict(self, schema):
        """Method to create a dictionary containing a JSON reference to the
        schema in the spec
        """
        ret = super().get_ref_dict(schema)
        if isinstance_or_subclass(schema, BaseExceptionSchema):
            return ret
        return {'type': 'object', 'properties': {'data': ret}}


class JSONAPIMarshmallowPlugin(MarshmallowPlugin):
    """ JSON:API Marshmallow plugin to handle JSONAPISchema subclasses. """
    Converter = JSONAPISchemaConverter


class JSONAPISchemaGenerator(BaseSchemaGenerator):
    """ OpenAPI schema generator for JSON:API resources. """

    def __init__(self, spec: APISpec):
        self.spec = spec

    def get_endpoints(self, routes: List[BaseRoute]) -> List[EndpointInfo]:
        """ Extends the base implementation to handle coroutines wrapped in functools.partial. """
        ret = super().get_endpoints(routes)

        for route in routes:
            if isinstance(route, Route) and iscoroutinefunction_or_partial(route.endpoint):
                for method in route.methods or ['GET']:
                    if method == 'HEAD':
                        continue
                    ret.append(
                        EndpointInfo(route.path, method.lower(), route.endpoint)
                    )

        return ret

    def get_schema(self, routes: List[BaseRoute]) -> dict:
        """
        Registers routes and their OpenAPI information in the :class:`apispec.APISpec`.

        Returns the OpenAPI specification for the given routes.

        :param routes: List of registered routes
        :return: dict representation of the OpenAPI specification
        """
        # importing BaseResource and BaseRelationshipResource here to prevent circular imports
        from starlette_jsonapi.resource import BaseRelationshipResource, BaseResource

        endpoints_info = self.get_endpoints(routes)

        for endpoint in endpoints_info:
            openapi_info = {}  # type: dict
            path_params = []
            tags = None
            # we expect endpoint.func to be handle_request, wrapped in a functools.partial
            if isinstance(endpoint.func, functools.partial):
                obj = endpoint.func
                last_partial = obj
                while isinstance(obj, functools.partial):
                    last_partial = obj
                    obj = obj.func  # type: ignore

                # get resource class and handler
                handler_cls = getattr(obj, '__self__', None)
                if handler_cls and issubclass(handler_cls, (BaseResource, BaseRelationshipResource)):
                    handler = getattr(handler_cls, last_partial.args[0], None)
                    # traverse the reversed MRO of handler_cls, compute openapi_info
                    openapi_info = compute_base_openapi_info(handler_cls).get('handlers', {}).get(handler.__name__)
                    openapi_info['responses'] = process_responses(openapi_info.get('responses', {}))

                    # add tags based on resource class
                    tags = []
                    if issubclass(handler_cls, BaseResource):
                        tags.append(handler_cls.register_as or handler_cls.type_)
                    else:
                        tags.append(handler_cls.parent_resource.register_as or handler_cls.parent_resource.type_)

                    # compute schema for handler, merging openapi_info added by @with_openapi_info
                    openapi_info = safe_merge(openapi_info, getattr(handler, OPENAPI_INFO, {}))
                    if tags:
                        openapi_info.update(tags=tags)
                    if not openapi_info.pop('include_in_schema', True):
                        continue

                    path_params = openapi_info.get('parameters', [])

            # add path parameters
            new_path = endpoint.path
            groups = re.findall(PATH_PARAMS_REGEX, endpoint.path)
            if groups:
                for group in groups:
                    path_params.append(
                        {
                            'name': group[1],
                            'in': 'path',
                            'required': True,
                            'schema': {'type': get_openapi_parameter_type(group[2])}
                        }
                    )
                    # transform {<param_name>:<param_type>} into {<param_name>}
                    new_path = new_path.replace(group[0], '{' + group[1] + '}')

            self.spec.path(path=new_path, operations={endpoint.http_method: openapi_info}, parameters=path_params)

        return self.spec.to_dict()


def compute_base_openapi_info(klass: Type[Any]) -> dict:
    """
    Computes OpenAPI information for a resource class, traversing the MRO
    to merge information from base classes.

    :param klass: a BaseResource or BaseRelationshipResource subclass
    :return: merged OpenAPI information
    """
    from starlette_jsonapi.resource import BaseResource, BaseRelationshipResource
    openapi_info: dict = {}
    for base_klass in reversed(klass.__mro__):
        if issubclass(base_klass, (BaseResource, BaseRelationshipResource)):
            base_openapi_info = getattr(base_klass, OPENAPI_INFO, {})
            openapi_info = safe_merge(openapi_info, base_openapi_info)
    return openapi_info


def process_responses(responses: dict) -> dict:
    """
    Processes response bodies, adding the OpenAPI representations for
    any JSONAPISchema or Exception subclasses.

    :param responses: Dictionary of HTTP status code -> response
    :return: OpenAPI dictionary of responses
    """
    computed_responses = {}
    for response_code, response in responses.items():
        if isinstance(response, dict):
            computed_responses[response_code] = response
        elif isinstance(response, str) or isinstance_or_subclass(response, JSONAPISchema):
            computed_responses.setdefault(response_code, {})
            computed_responses[response_code] = safe_merge(
                computed_responses[response_code], response_for_schema(schema=response)  # type: ignore
            )
        elif isinstance_or_subclass(response, Exception):
            computed_responses.setdefault(response_code, {})
            computed_responses[response_code] = safe_merge(
                computed_responses[response_code],
                response_for_exception(exception=response, status_code=response_code),
            )
    return computed_responses


def process_request_body(request_body: SchemaType, method: str):
    """
    Convert a request body to it's OpenAPI representation, correcting
    the `id` attribute of the schema.

    :param request_body: A schema for the request body which will be marked as required.
    :param method: The HTTP method, usually one of: 'patch', 'post'
    :return: The OpenAPI representation for the given schema
    """
    if (
        not isinstance(request_body, (str, dict))
        and isinstance_or_subclass(request_body, JSONAPISchema)
    ):
        request_body = request_for_schema(schema=request_body, method=method)
    return request_body


def with_openapi_info(
        request_body: SchemaType = None,
        responses: Dict[str, Union[SchemaOrExceptionType]] = None,
        include_in_schema: bool = True,
        *args, **kwargs,
):
    """
    Decorates a handler to add OpenAPI information that will be merged (deep update)
    into the resource class information, overwriting common keys.
    Additional ``kwargs`` are included too, and the final dictionary will be used as
    the operation's options.

    Multiple ``with_openapi_info`` decorators can be used on the same handler.

    Examples:

    .. code-block:: python

        class ExampleResource(BaseResource):
            schema = ExampleSchema
            type_ = 'examples'

            @with_openapi_info(responses={'200': ExampleSchema, '404': ResourceNotFound})
            async def get(self, id: Any, *args, **kwargs) -> Response:
                # A 200 response body will be formed from ExampleSchema.
                # A 404 response body will be formed from the ResourceNotFound exception.

            @with_openapi_info(request_body=ExampleSchema)
            @with_openapi_info(summary='Updating an example')
            async def patch(self, id: Any, *args, **kwargs) -> Response:
                # A requestBody schema will be formed from ExampleSchema.
                # Summary for the path will be added as well.

            @with_openapi_info(include_in_schema=False)
            async def delete(self, id: Any, *args, **kwargs) -> Response:
                # Will not be registered in the OpenAPI specification.

            @with_openapi_info(responses={'200': ExampleSchema(many=True)})
            async def get_many(self, *args, **kwargs) -> Response:
                # A 200 response body will be formed from ExampleSchema, for a list of items.

    :param request_body: optional, a request body which will be required
    :param responses: optional, a dictionary of HTTP status code -> response schema
    :param include_in_schema: Flag to control whether the handler is included in the OpenAPI spec
    :param args: Additional arguments, currently ignored
    :param kwargs: Additional keyword arguments, included in the operation's options
    :return: The decorated handler
    """
    def update_openapi_info(func):
        nonlocal request_body

        @functools.wraps(func)
        def wrapper_openapi_info(*fargs, **fkwargs):
            return func(*fargs, **fkwargs)

        new_info = {'include_in_schema': include_in_schema, 'responses': {}}  # type: dict
        new_info.update(kwargs)

        # Convert responses, add correct OpenAPI representations
        if responses:
            computed_responses = process_responses(responses=responses)
            new_info['responses'] = computed_responses

        # Convert request body, correcting the OpenAPI representation based on the handler name
        if request_body:
            new_info['requestBody'] = process_request_body(request_body=request_body, method=func.__name__)

        openapi_info = getattr(func, OPENAPI_INFO, dict())
        openapi_info = safe_merge(openapi_info, new_info)
        setattr(wrapper_openapi_info, OPENAPI_INFO, openapi_info)
        return wrapper_openapi_info
    return update_openapi_info


def response_for_schema(schema: SchemaType) -> dict:
    """ Generates a response schema. """
    return {'content': {CONTENT_TYPE_HEADER: {'schema': schema}}, 'description': 'Example response'}


def response_for_exception(
        exception: Union[Exception, Type[Exception]],
        status_code: str,
) -> dict:
    """ Generates an exception schema. """
    detail_message = getattr(exception, 'detail', 'Internal server error')
    status_code = str(getattr(exception, 'status_code', status_code or 500))
    exc_name = exception.__class__.__name__ if isinstance(exception, Exception) else exception.__name__

    schema_cls_name = f'{exc_name}-{status_code}'
    detail_schema_cls_name = f'{schema_cls_name}-detail'
    try:
        schema_cls = class_registry.get_class(schema_cls_name)
    except RegistryError:
        detail_schema_cls = type(
            detail_schema_cls_name, (BaseExceptionSchema,),
            {'detail': ma_fields.String(validate=validate.OneOf([detail_message]))}
        )

        schema_cls = type(
            schema_cls_name, (BaseExceptionSchema,),
            {'errors': ma_fields.List(ma_fields.Nested(detail_schema_cls))}
        )

    return {
        'content': {
            CONTENT_TYPE_HEADER: {
                'schema': schema_cls,
            }
        },
        'description': 'Example error response'
    }


def response_for_relationship(schema: Union[JSONAPISchema, Type[JSONAPISchema]], relationship_name: str) -> dict:
    """
    Generates a relationship response schema.

    Examples:

    .. code-block:: python

        class ExampleRelationshipResource(BaseRelationshipResource):
            parent_resource = ExampleResource
            relationship_name = 'rel'

            @with_openapi_info(
                responses={
                    '200': response_for_relationship(ExampleResource.schema, relationship_name)
                }
            )
            async def get(self, parent_id: Any, *args, **kwargs) -> Response:
                # A 200 response body will be formed from the relationship
                # defined on parent resource schema.

    :param schema: the JSONAPISchema of the parent resource
    :param relationship_name: the name of the relationship, as defined on the parent resource schema
    :return: The OpenAPI representation of the response
    """
    rel_field = schema.get_fields()[relationship_name]
    if not isinstance(rel_field, JSONAPIRelationship):
        raise ValueError(f'{relationship_name} is not a relationship of {schema}')
    rel_item_schema = {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'type': {'type': 'string', 'enum': [rel_field.type_]},
        }
    }
    if getattr(rel_field, 'many', False):
        rel_item_schema = {'type': 'array', 'items': rel_item_schema}
    else:
        rel_item_schema = rel_item_schema
    return {
        'content': {
            CONTENT_TYPE_HEADER: {'schema': {'type': 'object', 'properties': {'data': rel_item_schema}}}
        },
        'description': 'Example relationship response',
    }


def request_for_relationship(schema: Union[JSONAPISchema, Type[JSONAPISchema]], relationship_name: str) -> dict:
    """
    Generates a relationship request schema.

    Examples:

    .. code-block:: python

        class ExampleRelationshipResource(BaseRelationshipResource):
            parent_resource = ExampleResource
            relationship_name = 'rel'

            @with_openapi_info(
                request_body=request_for_relationship(ExampleResource.schema, relationship_name)
            )
            async def post(self, parent_id: Any, *args, **kwargs) -> Response:
                # A request body will be formed from the relationship
                # defined on parent resource schema and marked as required.

    :param schema: the JSONAPISchema of the parent resource
    :param relationship_name: the name of the relationship, as defined on the parent resource schema
    :return: The OpenAPI representation of the request
    """
    rel_field = schema.get_fields()[relationship_name]
    if not isinstance(rel_field, JSONAPIRelationship):
        raise ValueError(f'{relationship_name} is not a relationship of {schema}')
    rel_item_schema = {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'type': {'type': 'string', 'enum': [rel_field.type_]},
        }
    }
    if getattr(rel_field, 'many', False):
        rel_item_schema = {'type': 'array', 'items': rel_item_schema}
    else:
        rel_item_schema = rel_item_schema
    return {
        'content': {
            CONTENT_TYPE_HEADER: {'schema': {'type': 'object', 'properties': {'data': rel_item_schema}}}
        },
        'description': 'Example relationship request',
        'required': True,
    }


def request_for_schema(
        schema: SchemaType,
        method: str = 'post',
) -> dict:
    """ Generates a request schema. """
    if not isinstance(schema, (str, dict)):
        schema_cls = schema  # type: Any
        if isinstance(schema, JSONAPISchema):
            schema_cls = schema.__class__

        schema_cls_id_field = schema_cls.get_fields().get('id', None)
        if method == 'patch' and schema_cls_id_field and schema_cls_id_field.dump_only:
            id_field = ma_fields.String(dump_only=False)
        else:
            id_field = schema_cls_id_field
        schema = type(
            schema_cls.__name__ + '-' + method, (schema_cls,),
            {
                'id': id_field,
                'OPTIONS_CLASS': SchemaOpts,
            }
        )

    return {'content': {CONTENT_TYPE_HEADER: {'schema': schema}}, 'required': True}
