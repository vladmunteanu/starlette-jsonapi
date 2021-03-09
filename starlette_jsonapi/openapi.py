import functools
import re
from collections import OrderedDict
from typing import List, Type, Union, NamedTuple, Dict, Any, Callable

from starlette.routing import BaseRoute, iscoroutinefunction_or_partial, Route
from starlette.schemas import BaseSchemaGenerator, EndpointInfo
from starlette.convertors import CONVERTOR_TYPES
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin, OpenAPIConverter
from marshmallow_jsonapi.schema import SchemaOpts
from marshmallow.utils import is_collection
from marshmallow import fields as ma_fields

from starlette_jsonapi.constants import OPENAPI_INFO, CONTENT_TYPE_HEADER
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.schema import JSONAPISchema
from starlette_jsonapi.utils import safe_merge, isinstance_or_subclass


class ExceptionSchemaInfo(NamedTuple):
    name: str
    status_code: Union[int, str]
    detail: str
    schema: dict


SchemaType = Union[str, dict, JSONAPISchema, Type[JSONAPISchema]]
SchemaOrExceptionType = Union[SchemaType, Exception, Type[Exception]]

EXPECTED_PATH_PARAMETERS = ['id', 'related_id', 'parent_id']

preregistered_schemas: Dict[str, ExceptionSchemaInfo] = {}


def get_openapi_parameter_type(parameter_type: str) -> str:
    if parameter_type == 'int':
        return 'integer'
    elif parameter_type == 'float':
        return 'number'
    else:
        return 'string'


class EndpointInfoWithParameters(NamedTuple):
    path: str
    http_method: str
    func: Callable
    parameters: dict


class JSONAPISchemaConverter(OpenAPIConverter):
    def init_attribute_functions(self):
        super().init_attribute_functions()
        self.add_attribute_function(self.relationship_field)

    def fields2jsonschema(self, fields, *, ordered=False, partial=None):
        default_fields = [
            ('id', None),
            ('type', {'type': 'string'}),
        ]
        jsonschema = {
            'type': 'object',
            'properties': OrderedDict(default_fields) if ordered else dict(default_fields),
        }  # type: dict
        properties = jsonschema['properties']
        schema_list = [field.parent for field in fields.values()]
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
        return {'type': 'object', 'properties': {'data': ret}}


class JSONAPIMarshmallowPlugin(MarshmallowPlugin):
    Converter = JSONAPISchemaConverter


class JSONAPISchemaGenerator(BaseSchemaGenerator):

    def __init__(self, spec: APISpec):
        self.spec = spec

    def preregister_schemas(self):
        for exc_name, exc_schema_info in preregistered_schemas.items():
            if exc_schema_info.name not in self.spec.components.schemas:
                self.spec.components.schema(
                    exc_schema_info.name,
                    exc_schema_info.schema,
                )

    def get_endpoints(self, routes: List[BaseRoute]) -> List[EndpointInfo]:
        """ Temporarily override this to handle coroutines wrapped in functools.partial. """
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
        """ Override to handle unwrapping actual handlers passed to handle_request. """
        # importing BaseResource and BaseRelationshipResource here to prevent circular imports
        from starlette_jsonapi.resource import BaseRelationshipResource, BaseResource
        # make sure all referenced schemas are registered
        self.preregister_schemas()

        endpoints_info = self.get_endpoints(routes)
        params_path_regex = '({{({}):({})}})'.format(
            '|'.join(EXPECTED_PATH_PARAMETERS), '|'.join(CONVERTOR_TYPES.keys())
        )

        for endpoint in endpoints_info:
            openapi_info = {}  # type: dict
            path_params = []
            tags = None
            if isinstance(endpoint.func, functools.partial):
                obj = endpoint.func
                last_partial = obj
                while isinstance(obj, functools.partial):
                    last_partial = obj
                    obj = obj.func  # type: ignore

                # get resource class and handler
                handler_cls = obj.__self__  # type: Type[Union[BaseResource, BaseRelationshipResource]]
                handler = getattr(handler_cls, last_partial.args[0], None)

                # add tags based on resource class
                tags = []
                if issubclass(handler_cls, BaseResource):
                    tags.append(handler_cls.register_as or handler_cls.type_)
                elif issubclass(handler_cls, BaseRelationshipResource):
                    tags.append(handler_cls.parent_resource.register_as or handler_cls.parent_resource.type_)

                # return schema for handler, merging openapi_info
                if handler:
                    openapi_info = safe_merge(openapi_info, getattr(handler, OPENAPI_INFO, {}))
                    if tags:
                        openapi_info.update(tags=tags)
                    if not openapi_info.pop('include_in_schema', True):
                        continue
                else:
                    continue

            # add path parameters
            new_path = endpoint.path
            groups = re.findall(params_path_regex, endpoint.path)
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
                    new_path = new_path.replace(group[0], '{' + group[1] + '}')

            self.spec.path(path=new_path, operations={endpoint.http_method: openapi_info}, parameters=path_params)

        return self.spec.to_dict()


def with_openapi_info(
        request_body: SchemaType = None,
        responses: Dict[str, Union[SchemaOrExceptionType]] = None,
        include_in_schema: bool = True,
        *args, **kwargs,
):
    def update_openapi_info(func):
        nonlocal request_body

        @functools.wraps(func)
        def wrapper_openapi_info(*fargs, **fkwargs):
            return func(*fargs, **fkwargs)

        new_info = {'include_in_schema': include_in_schema, 'responses': {}}  # type: dict
        new_info.update(kwargs)

        # convert responses, add correct jsonschema representations
        if responses:
            computed_responses = {}  # type: dict
            for response_code, response in responses.items():
                if isinstance(response, dict):
                    computed_responses[response_code] = response
                elif isinstance(response, str) or isinstance_or_subclass(response, JSONAPISchema):
                    computed_responses.setdefault(response_code, {})
                    computed_responses[response_code] = safe_merge(
                        computed_responses[response_code], response_for_schema(schema=response)  # type: ignore
                    )
                elif isinstance_or_subclass(response, Exception):
                    computed_responses = safe_merge(
                        computed_responses,
                        response_for_exc(response, status_code=response_code)
                    )
            new_info['responses'] = computed_responses

        # convert request body, adding the correct jsonschema depending on the handler name
        if request_body:
            if (
                not isinstance(request_body, (str, dict))
                and isinstance_or_subclass(request_body, JSONAPISchema)
            ):
                request_body = request_for_schema(schema=request_body, method=func.__name__)
            new_info['requestBody'] = request_body

        openapi_info = getattr(func, OPENAPI_INFO, dict())
        openapi_info = safe_merge(openapi_info, new_info)
        setattr(wrapper_openapi_info, OPENAPI_INFO, openapi_info)
        return wrapper_openapi_info
    return update_openapi_info


def get_schema_for_exc(
        exc: Union[Exception, Type[Exception]],
        status_code: Union[int, str] = None
) -> ExceptionSchemaInfo:
    detail = getattr(exc, 'detail', 'Internal server error')
    status_code = str(getattr(exc, 'status_code', status_code or 500))
    exc_name = exc.__class__.__name__ if isinstance(exc, Exception) else exc.__name__
    name = f'{exc_name}-{status_code}'
    return ExceptionSchemaInfo(
        name=name,
        status_code=status_code,
        detail=detail,
        schema={
            'type': 'object',
            'properties': {
                'errors': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'detail': {'type': 'string', 'enum': [detail]},
                        },
                    },
                },
            },
        },
    )


def response_for_exc(exc: Union[Exception, Type[Exception]], status_code: Union[int, str] = None) -> dict:
    exc_schema_info = get_schema_for_exc(exc=exc, status_code=status_code)
    status_code = exc_schema_info.status_code if status_code is None else status_code
    preregistered_schemas[exc_schema_info.name] = exc_schema_info
    return {
        str(status_code): {
            'content': {
                CONTENT_TYPE_HEADER: {
                    'schema': exc_schema_info.name
                }
            },
            'description': 'Example error response'
        }
    }


def response_for_schema(schema: SchemaType) -> dict:
    return {'content': {CONTENT_TYPE_HEADER: {'schema': schema}}, 'description': 'Example response'}


def response_for_relationship(schema: Union[JSONAPISchema, Type[JSONAPISchema]], relationship_name: str) -> dict:
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
        'description': 'Example relationship response'
    }


def request_for_schema(
        schema: SchemaType,
        method: str = 'post',
) -> dict:
    if not isinstance(schema, (str, dict)):
        schema_cls = schema  # type: Any
        if isinstance(schema, JSONAPISchema):
            schema_cls = schema.__class__

        class RequestSchema(schema_cls):
            OPTIONS_CLASS = SchemaOpts
            id = schema_cls.get_fields().get('id', None)
            if method == 'patch' and id and id.dump_only:
                id = ma_fields.String(dump_only=False)

        RequestSchema.__name__ = schema_cls.__name__ + '-' + method
        schema = RequestSchema

    return {'content': {CONTENT_TYPE_HEADER: {'schema': schema}}}
