import pytest
from marshmallow_jsonapi import fields
from starlette.applications import Starlette

from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.schema import JSONAPISchema


def test_schema_urls(app: Starlette):
    class TResource(BaseResource):
        type_ = 'test-resource'
    TResource.register_routes(app, '/')

    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        class Meta:
            type_ = 'test-resource'
            self_route = 'test-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-resource:get_many'

    rv = TSchema().dump(dict(id='foo', name='foo-name'))
    assert rv == {
        'data': {
            'id': 'foo',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo-name',
            }
        }
    }
    rv = TSchema(app=app).dump(dict(id='foo', name='foo-name'))
    assert rv == {
        'data': {
            'id': 'foo',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo-name',
            },
            'links': {
                'self': '/test-resource/foo',
            },
        },
        'links': {
            'self': '/test-resource/foo',
        },
    }


def test_prefixed_schema_urls(app: Starlette):
    class TResource(BaseResource):
        type_ = 'test-resource'
    TResource.register_routes(app, '/')

    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        class Meta:
            type_ = 'test-resource'
            self_route = 'test-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-resource:get_many'

    app.url_prefix = 'https://example.com'
    rv = TSchema(app=app).dump(dict(id='foo', name='foo-name'))
    assert rv == {
        'data': {
            'id': 'foo',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo-name',
            },
            'links': {
                'self': 'https://example.com/test-resource/foo',
            },
        },
        'links': {
            'self': 'https://example.com/test-resource/foo',
        },
    }


def test_schema_raises_wrong_meta_parameters():
    with pytest.raises(ValueError) as exc:
        class TSchema(JSONAPISchema):
            id = fields.Str(dump_only=True)
            name = fields.Str()

            class Meta:
                type_ = 'test-resource'
                self_url = 'foo'
    assert str(exc.value) == 'Use `self_route` instead of `self_url` when using the Starlette extension.'

    with pytest.raises(ValueError) as exc:
        class TSchema2(JSONAPISchema):
            id = fields.Str(dump_only=True)
            name = fields.Str()

            class Meta:
                type_ = 'test-resource'
                self_url_kwargs = 'foo'
    assert str(exc.value) == 'Use `self_route_kwargs` instead of `self_url_kwargs` when using the Starlette extension.'

    with pytest.raises(ValueError) as exc:
        class TSchema3(JSONAPISchema):
            id = fields.Str(dump_only=True)
            name = fields.Str()

            class Meta:
                type_ = 'test-resource'
                self_url_many = 'foo'
    assert str(exc.value) == 'Use `self_route_many` instead of `self_url_many` when using the Starlette extension.'

    with pytest.raises(ValueError) as exc:
        class TSchema4(JSONAPISchema):
            id = fields.Str(dump_only=True)
            name = fields.Str()

            class Meta:
                type_ = 'test-resource'
                self_route_kwargs = 'foo'
    assert str(exc.value) == 'Must specify `self_route` Meta option when `self_route_kwargs` is specified.'


def test_schema_excludes_unknown():
    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        class Meta:
            type_ = 'test-resource'

    d = TSchema().loads('{"data": {"type": "test-resource", "id": "foo", "attributes": {"unknown": "bar"}}}')
    assert d == {}

    d = TSchema().loads('{"data": {"type": "test-resource", "id": "foo", "attributes": {"name": "bar"}, "unknown": 1}}')
    assert d == {'name': 'bar'}
