# test schema renders with correct types
# test schema is enclosed
# test response body with difference between patch and post
# test additional parameters passed to openapi
# test relationship resource
# test with_openapi_info overwrites values from class
import sys
from collections import OrderedDict
from typing import Any, List, Union, Dict, Type

import pytest
from apispec import APISpec
from apispec.utils import validate_spec
from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette.responses import Response

from starlette_jsonapi.constants import CONTENT_TYPE_HEADER
from starlette_jsonapi.exceptions import ResourceNotFound
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseResource, BaseRelationshipResource
from starlette_jsonapi.schema import JSONAPISchema
from starlette_jsonapi.meta import registered_resources
from starlette_jsonapi.openapi import (
    JSONAPISchemaGenerator, JSONAPIMarshmallowPlugin, preregistered_schemas,
    with_openapi_info, response_for_relationship,
)


@pytest.fixture(autouse=True)
def clear_imports():
    yield
    # Clear resource module import since we want
    # BaseResource and BaseRelationshipResource
    # to pre-register exceptions for every test.
    sys.modules.pop('starlette_jsonapi.resource', None)


@pytest.fixture(autouse=True)
def clear_preregistered_schemas():
    yield
    preregistered_schemas.clear()


@pytest.fixture
def openapi_schema_as_dict():
    def make_schema_for_app(starlette_app: Starlette) -> dict:
        starlette_app.schema_generator = JSONAPISchemaGenerator(
            APISpec(
                title='Test API',
                version='1.0',
                openapi_version='3.0.0',
                info={'description': 'Test OpenAPI resource'},
                plugins=[JSONAPIMarshmallowPlugin()],
            )
        )
        schema_dict = starlette_app.schema_generator.get_schema(starlette_app.routes)
        return schema_dict
    return make_schema_for_app


@pytest.fixture()
def openapi_resources() -> Dict[str, Type[Union[BaseResource, BaseRelationshipResource]]]:
    class TParentSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

        class Meta:
            type_ = 'test-parent-resource'
            self_route = 'test-parent-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-parent-resource:get_many'

    class TParentResource(BaseResource):
        type_ = 'test-parent-resource'
        schema = TParentSchema

    class TChildSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        parent = JSONAPIRelationship(
            schema='TParentSchema',
            type_='test-parent-resource',
            self_route='test-child-resource:relationship-parent',
            self_route_kwargs={'id': '<id>'},
            related_resource='TParentResource',
            related_route='test-child-resource:parent',
            related_route_kwargs={'id': '<id>'},
        )

        class Meta:
            type_ = 'test-child-resource'
            self_route = 'test-child-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-child-resource:get_many'

    class TChildResource(BaseResource):
        type_ = 'test-child-resource'
        schema = TChildSchema

    class TChildResourceRel(BaseRelationshipResource):
        parent_resource = TChildResource
        relationship_name = 'parent'

    return OrderedDict([
        ('TParentResource', TParentResource),
        ('TChildResource', TChildResource),
        ('TChildResourceRel', TChildResourceRel),
    ])


@pytest.fixture()
def openapi_app(app: Starlette, openapi_resources):
    for resource_cls in openapi_resources.values():
        resource_cls.register_routes(app, '/')

    return app


@pytest.mark.parametrize(
    ['path', 'methods', 'methods_registered'],
    [
        (
            '/test-parent-resource/{id}', ['get', 'patch', 'delete'], [True, True, True]
        ),
        (
            '/test-parent-resource/', ['get', 'post'], [True, True]
        ),
        (
            '/test-child-resource/{id}', ['get', 'patch', 'delete'], [True, True, True]
        ),
        (
            '/test-child-resource/', ['get', 'post'], [True, True]
        ),
        (
            '/test-child-resource/{id}/parent', ['get'], [True]
        ),
        (
            '/test-child-resource/{id}/parent/{related_id}', [], []
        ),
        (
            '/test-child-resource/{parent_id}/relationships/parent',
            ['get', 'patch', 'delete', 'post'],
            [True, True, True, True]
        ),
    ]
)
def test_routes_are_registered(
        openapi_app: Starlette, openapi_schema_as_dict,
        path: str, methods: List[str], methods_registered: List[bool],
):
    schema = openapi_schema_as_dict(openapi_app)
    if not methods:
        assert path not in schema['paths']
    else:
        assert path in schema['paths']
        for method, registered in zip(methods, methods_registered):
            assert (method in schema['paths'][path]) is registered


@pytest.fixture
def openapi_app_included(app: Starlette):
    class TParentSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

        class Meta:
            type_ = 'test-parent-resource'
            self_route = 'test-parent-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-parent-resource:get_many'

    class TParentResource(BaseResource):
        type_ = 'test-parent-resource'
        schema = TParentSchema

        @with_openapi_info(include_in_schema=False)
        async def get(self, id: Any, *args, **kwargs) -> Response:
            return Response(status_code=200)

    TParentResource.register_routes(app, '/')

    return app


@pytest.mark.parametrize(
    ['path', 'methods', 'methods_registered'],
    [
        (
            '/test-parent-resource/{id}', ['get', 'patch', 'delete'], [False, True, True]
        ),
        (
            '/test-parent-resource/', ['get', 'post'], [True, True]
        ),
    ]
)
def test_routes_are_not_included(
        openapi_app_included: Starlette, openapi_schema_as_dict,
        path: str, methods: List[str], methods_registered: List[bool],
):

    schema = openapi_schema_as_dict(openapi_app_included)
    if not methods:
        assert path not in schema['paths']
    else:
        assert path in schema['paths']
        for method, registered in zip(methods, methods_registered):
            assert (method in schema['paths'][path]) is registered


def test_response_schema(openapi_app: Starlette, openapi_schema_as_dict):
    TChildResource = registered_resources['TChildResource']
    TChildResource.get = with_openapi_info(
        responses={'200': TChildResource.schema}
    )(TChildResource.get)
    TChildResource.get_many = with_openapi_info(
        responses={'200': TChildResource.schema(many=True)}
    )(TChildResource.get_many)
    schema = openapi_schema_as_dict(openapi_app)
    response_schema_name = TChildResource.schema.__name__.replace('Schema', '')
    assert response_schema_name in schema['components']['schemas']
    response_schema = schema['components']['schemas'][response_schema_name]
    assert response_schema == {
        'type': 'object',
        'properties': {
            'id': {'type': 'string', 'readOnly': True},
            'type': {'type': 'string', 'enum': [TChildResource.type_]},
            'attributes': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                }
            },
            'relationships': {
                'type': 'object',
                'properties': {
                    'parent': {
                        'type': 'object',
                        'nullable': True,
                        'properties': {
                            'data': {
                                'type': 'object',
                                'properties': {
                                    'id': {'type': 'string'},
                                    'type': {
                                        'type': 'string',
                                        'enum': [TChildResource.schema.get_fields()['parent'].type_],
                                    }
                                }
                            },
                            'links': {
                                'type': 'object',
                                'properties': {
                                    'self': {'type': 'string'},
                                    'related': {'type': 'string'}
                                },
                                'readOnly': True
                            }
                        }
                    }
                }
            }
        },
        'required': ['type'],
    }
    get_url = '/' + TChildResource.type_ + '/{id}'
    assert get_url in schema['paths']
    assert schema['paths'][get_url]['get']['responses']['200']['content'][CONTENT_TYPE_HEADER] == {
        'schema': {
            'type': 'object',
            'properties': {
                'data': {
                    '$ref': f'#/components/schemas/{response_schema_name}'
                }
            }
        }
    }

    get_many_url = '/' + TChildResource.type_ + '/'
    assert get_many_url in schema['paths']
    assert schema['paths'][get_many_url]['get']['responses']['200']['content'][CONTENT_TYPE_HEADER] == {
        'schema': {
            'type': 'object',
            'properties': {
                'data': {
                    'type': 'array',
                    'items': {
                        '$ref': f'#/components/schemas/{response_schema_name}'
                    }
                }
            }
        }
    }

    openapi_app.schema_generator.preregister_schemas()
    assert validate_spec(openapi_app.schema_generator.spec) is True


def test_exception_schema(openapi_app: Starlette, openapi_schema_as_dict):
    TParentResource = registered_resources['TParentResource']
    TParentResource.get = with_openapi_info(responses={'404': ResourceNotFound})(TParentResource.get)
    schema = openapi_schema_as_dict(openapi_app)
    assert 'ResourceNotFound-404' in schema['components']['schemas']
    exc_schema = schema['components']['schemas']['ResourceNotFound-404']
    expected_exc_schema = {
        'type': 'object',
        'properties': {
            'errors': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'detail': {
                            'type': 'string',
                            'enum': [ResourceNotFound.detail]
                        }
                    }
                }
            }
        }
    }
    get_url = '/' + TParentResource.type_ + '/{id}'
    assert get_url in schema['paths']
    assert schema['paths'][get_url]['get']['responses']['404']['content'][CONTENT_TYPE_HEADER] == {
        'schema': {
            '$ref': '#/components/schemas/ResourceNotFound-404'
        }
    }

    assert exc_schema == expected_exc_schema
    openapi_app.schema_generator.preregister_schemas()
    assert validate_spec(openapi_app.schema_generator.spec) is True


def test_request_schema(openapi_app: Starlette, openapi_schema_as_dict):
    TParentResource = registered_resources['TParentResource']
    TParentResource.patch = with_openapi_info(request_body=TParentResource.schema)(TParentResource.patch)
    TParentResource.post = with_openapi_info(request_body=TParentResource.schema)(TParentResource.post)
    schema = openapi_schema_as_dict(openapi_app)
    patch_schema_name = TParentResource.schema.__name__ + "-patch"
    post_schema_name = TParentResource.schema.__name__ + "-post"
    assert patch_schema_name in schema['components']['schemas']
    assert post_schema_name in schema['components']['schemas']
    request_schema = {
        'type': 'object',
        'properties': {
            'id': {'type': 'string'},
            'type': {'type': 'string', 'enum': [TParentResource.type_]},
            'attributes': {
                'type': 'object',
                'properties': {
                    'description': {'type': 'string'},
                }
            },
        },
        'required': ['type'],
    }  # type: dict
    assert schema['components']['schemas'][patch_schema_name] == request_schema
    request_schema['properties']['id']['readOnly'] = True
    assert schema['components']['schemas'][post_schema_name] == request_schema
    openapi_app.schema_generator.preregister_schemas()
    assert validate_spec(openapi_app.schema_generator.spec) is True


# test response for relationships
def test_response_for_relationships(openapi_resources, openapi_app: Starlette, openapi_schema_as_dict):
    TChildResourceRel = openapi_resources['TChildResourceRel']
    TChildResourceRel.get = with_openapi_info(
        responses={
            '200': response_for_relationship(
                TChildResourceRel.parent_resource.schema,
                TChildResourceRel.relationship_name
            )
        }
    )(TChildResourceRel.get)
    schema = openapi_schema_as_dict(openapi_app)
    relationships_url = ''.join(
        [
            '/', TChildResourceRel.parent_resource.type_,
            '/{parent_id}/relationships/', TChildResourceRel.relationship_name
        ]
    )
    assert relationships_url in schema['paths']
    rel_field = TChildResourceRel.parent_resource.schema.get_fields()[TChildResourceRel.relationship_name]
    assert isinstance(rel_field, JSONAPIRelationship)
    assert schema['paths'][relationships_url]['get']['responses']['200']['content'][CONTENT_TYPE_HEADER] == {
        'schema': {
            'type': 'object',
            'properties': {
                'data': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'string'},
                        'type': {'type': 'string', 'enum': [rel_field.type_]},
                    }
                }
            }
        }
    }
    openapi_app.schema_generator.preregister_schemas()
    assert validate_spec(openapi_app.schema_generator.spec) is True


def test_path_parameters(app: Starlette, openapi_schema_as_dict):
    class TResourceSchema(JSONAPISchema):
        id = fields.String()
        description = fields.String()

        class Meta:
            type_ = 'test'

    class TResourceInt(BaseResource):
        schema = TResourceSchema
        type_ = 'test-int'
        id_mask = 'int'

    class TResourceFloat(BaseResource):
        schema = TResourceSchema
        type_ = 'test-float'
        id_mask = 'float'

    class TResourceString(BaseResource):
        schema = TResourceSchema
        type_ = 'test-string'
        id_mask = 'str'

    class TResourceUUID(BaseResource):
        schema = TResourceSchema
        type_ = 'test-uuid'
        id_mask = 'uuid'

    class TRelatedResourceSchema(JSONAPISchema):
        id = fields.String()
        description = fields.String()

        rel = JSONAPIRelationship(
            type_=TResourceInt.type_,
            schema=TResourceSchema,
            many=True,
            related_resource=TResourceInt,
        )

        class Meta:
            type_ = 'test-related'

    class TResourceRelated(BaseResource):
        schema = TRelatedResourceSchema
        type_ = 'test-related'
        id_mask = 'int'

    class TResourceRelationship(BaseRelationshipResource):
        parent_resource = TResourceRelated
        relationship_name = 'rel'

    TResourceInt.register_routes(app)
    TResourceFloat.register_routes(app)
    TResourceString.register_routes(app)
    TResourceUUID.register_routes(app)
    TResourceRelated.register_routes(app)
    TResourceRelationship.register_routes(app)

    schema = openapi_schema_as_dict(app)
    assert schema['paths']['/test-int/{id}']['parameters'] == [
        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}
    ]
    assert 'parameters' not in schema['paths']['/test-int/']
    assert schema['paths']['/test-float/{id}']['parameters'] == [
        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'number'}}
    ]
    assert 'parameters' not in schema['paths']['/test-float/']
    assert schema['paths']['/test-string/{id}']['parameters'] == [
        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}
    ]
    assert 'parameters' not in schema['paths']['/test-string/']
    assert schema['paths']['/test-uuid/{id}']['parameters'] == [
        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}}
    ]
    assert 'parameters' not in schema['paths']['/test-uuid/']
    assert schema['paths']['/test-related/{id}/rel']['parameters'] == [
        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}
    ]
    assert schema['paths']['/test-related/{id}/rel/{related_id}']['parameters'] == [
        {'name': 'id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
        {'name': 'related_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}}
    ]
    assert schema['paths']['/test-related/{parent_id}/relationships/rel']['parameters'] == [
        {'name': 'parent_id', 'in': 'path', 'required': True, 'schema': {'type': 'integer'}},
    ]

    app.schema_generator.preregister_schemas()
    assert validate_spec(app.schema_generator.spec) is True


# test resource openapi info is included
# def test_resource_openapi_info_included(openapi_app: Starlette, openapi_schema_as_dict):
#     assert False, 'ToDo'


# test base resource openapi info is included
# def test_base_resource_openapi_info_included(openapi_app: Starlette, openapi_schema_as_dict):
#     assert False, 'ToDo'
