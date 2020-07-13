from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.schema import JSONAPISchema


def test_jsonapi_relationship_id_attribute():

    class OtherSchema(JSONAPISchema):
        class Meta:
            type_ = 'bar'
        id = fields.Str()

    class TestSchema(JSONAPISchema):
        class Meta:
            type_ = 'foo'
        id = fields.Str()
        rel = JSONAPIRelationship(
            id_attribute='rel_id',
            schema=OtherSchema,
            include_resource_linkage=True,
            type_='bar'
        )

    d = TestSchema().dump(dict(rel=dict(id='bar'), rel_id='bar_id', id='foo'))
    assert d['data']['relationships'] == {
        'rel': {
            'data': {
                'type': 'bar',
                'id': 'bar_id',
            }
        }
    }


def test_jsonapi_relationship_not_rendered():

    class OtherSchema(JSONAPISchema):
        class Meta:
            type_ = 'bar'
        id = fields.Str()

    class TestSchema(JSONAPISchema):
        class Meta:
            type_ = 'foo'
        id = fields.Str()
        rel = JSONAPIRelationship(
            schema=OtherSchema,
            type_='bar'
        )

    d = TestSchema().dump(dict(rel=dict(id='bar'), rel_id='bar_id', id='foo'))
    assert 'relationships' not in d['data']


def test_jsonapi_relationship_routes(app: Starlette):

    class OtherSchema(JSONAPISchema):
        id = fields.Str()

        class Meta:
            type_ = 'others'
            self_route = 'others:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'others:get_all'

    class OtherResource(BaseResource):
        type_ = 'others'
        schema = OtherSchema

    OtherResource.register_routes(app, '/')
    assert len(OtherResource.mount.routes) == 5

    class FooSchema(JSONAPISchema):
        id = fields.Str()
        rel = JSONAPIRelationship(
            schema='OtherSchema',
            include_resource_linkage=True,
            type_='others',
            self_route='',
            related_resource='OtherResource',
            related_route='foo:rel',
            related_route_kwargs={'id': '<id>'},
            id_attribute='rel_id',
        )

        class Meta:
            type_ = 'foo'
            self_route = 'foo:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'foo:get_all'

    class FooResource(BaseResource):
        type_ = 'foo'
        schema = FooSchema

    FooResource.register_routes(app, '/')
    assert len(FooResource.mount.routes) == 6  # 5 from the resource + 1 related

    d = FooSchema(app=app).dump(dict(rel=dict(id='bar'), rel_id='bar', id='foo_id'))
    assert d['data']['relationships'] == {
        'rel': {
            'data': {
                'type': 'others',
                'id': 'bar',
            },
            'links': {
                'related': '/foo/foo_id/rel',
            }
        }
    }
