import logging
from typing import Any, List

import pytest
from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.testclient import TestClient

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseResource, BaseRelationshipResource
from starlette_jsonapi.schema import JSONAPISchema


def test_register_routes(app: Starlette):
    class TResource(BaseResource):
        type_ = 'test-resource'

    class T2Resource(BaseResource):
        type_ = 'test-resource-2'

    class T3Resource(BaseResource):
        register_as = 'v2-test-resource-2'
        type_ = 'test-resource-2'

    TResource.register_routes(app=app, base_path='/some-base-path')
    T2Resource.register_routes(app=app, base_path='')
    T3Resource.register_routes(app=app, base_path='/v2')
    assert len(app.routes) == 3

    # test routes for TResource
    assert app.url_path_for('test-resource:get', id='foo') == '/some-base-path/test-resource/foo'
    assert app.url_path_for('test-resource:patch', id='foo') == '/some-base-path/test-resource/foo'
    assert app.url_path_for('test-resource:delete', id='foo') == '/some-base-path/test-resource/foo'
    assert app.url_path_for('test-resource:get_all') == '/some-base-path/test-resource/'
    assert app.url_path_for('test-resource:post') == '/some-base-path/test-resource/'

    # test routes for T2Resource
    assert app.url_path_for('test-resource-2:get', id='foo') == '/test-resource-2/foo'
    assert app.url_path_for('test-resource-2:patch', id='foo') == '/test-resource-2/foo'
    assert app.url_path_for('test-resource-2:delete', id='foo') == '/test-resource-2/foo'
    assert app.url_path_for('test-resource-2:get_all') == '/test-resource-2/'
    assert app.url_path_for('test-resource-2:post') == '/test-resource-2/'

    # test routes for T3Resource
    assert app.url_path_for('v2-test-resource-2:get', id='foo') == '/v2/test-resource-2/foo'
    assert app.url_path_for('v2-test-resource-2:patch', id='foo') == '/v2/test-resource-2/foo'
    assert app.url_path_for('v2-test-resource-2:delete', id='foo') == '/v2/test-resource-2/foo'
    assert app.url_path_for('v2-test-resource-2:get_all') == '/v2/test-resource-2/'
    assert app.url_path_for('v2-test-resource-2:post') == '/v2/test-resource-2/'


@pytest.mark.parametrize(['method', 'url'], [
    ('get', '/test-resource/foo'),
    ('patch', '/test-resource/foo'),
    ('delete', '/test-resource/foo'),
    ('get', '/test-resource/'),
    ('post', '/test-resource/'),
])
def test_default_crud_methods(app: Starlette, method: str, url: str):
    class TResource(BaseResource):
        type_ = 'test-resource'
    TResource.register_routes(app=app, base_path='/')

    client = TestClient(app=app)
    rv = getattr(client, method)(url)
    assert rv.status_code == 405
    assert rv.json() == {
        'errors': [
            {
                'detail': 'Method Not Allowed',
            },
        ]
    }


@pytest.fixture()
def jsonapi_headers_app(app: Starlette):
    class TResource(BaseResource):
        type_ = 'test-resource'

        async def post(self, *args, **kwargs) -> Response:
            await self.validate_body()
            return Response(status_code=200)

        async def patch(self, id=None, *args, **kwargs) -> Response:
            await self.validate_body()
            return Response(status_code=200)

    TResource.register_routes(app, '/')
    return app


def test_jsonapi_headers_required(jsonapi_headers_app: Starlette):
    test_client = TestClient(app=jsonapi_headers_app)
    # test post requests
    rv = test_client.post(
        '/test-resource/',
        json={
            'data': {
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            }
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {
                'detail': (
                    'Incorrect or missing Content-Type header, '
                    'expected `application/vnd.api+json`.'
                )
            }
        ]
    }

    # test patch requests
    rv = test_client.patch(
        '/test-resource/bar',
        json={
            'data': {
                'id': 'bar',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            }
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {
                'detail': (
                    'Incorrect or missing Content-Type header, '
                    'expected `application/vnd.api+json`.'
                )
            }
        ]
    }


@pytest.fixture()
def serialization_app(app: Starlette):
    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema

        async def get_all(self, *args, **kwargs) -> Response:
            return await self.serialize([dict(id=1, name='foo')], many=True)

        async def get(self, id=None, *args, **kwargs) -> Response:
            return await self.serialize(dict(id=id, name='foo'))

        async def post(self, *args, **kwargs) -> Response:
            body = await self.deserialize_body()
            return await self.serialize(dict(id=1, name=body.get('name')))

    TResource.register_routes(app, '/')
    return app


def test_serialize(serialization_app: Starlette):
    test_client = TestClient(app=serialization_app)
    rv = test_client.get('/test-resource/')
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': [
            {
                'id': '1',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
        ]
    }

    rv = test_client.get('/test-resource/bar')
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': {
            'id': 'bar',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo'
            }
        }
    }


def test_deserialize(serialization_app: Starlette):
    test_client = TestClient(app=serialization_app)
    rv = test_client.post(
        '/test-resource/',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': {
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            }
        }
    )
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': {
            'id': '1',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo'
            }
        }
    }


def test_deserialize_raises_validation_errors(serialization_app: Starlette):
    test_client = TestClient(app=serialization_app)
    rv = test_client.post(
        '/test-resource/',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': {
                'attributes': {
                    'name': 'foo'
                }
            }
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {
                'detail': '`data` object must include `type` key.',
                'source': {'pointer': '/data'}
            }
        ]
    }

    rv = test_client.post(
        '/test-resource/',
        headers={'Content-Type': 'application/vnd.api+json'},
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {
                'detail': 'Could not read request body.',
            }
        ]
    }


@pytest.fixture()
def included_app(app: Starlette):
    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        rel = JSONAPIRelationship(
            schema='TRelatedSchema',
            type_='test-related-resource',
            include_resource_linkage=True,
        )

        class Meta:
            type_ = 'test-resource'

    class TRelatedSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

        class Meta:
            type_ = 'test-related-resource'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema

        async def prepare_relations(self, obj: Any, relations: List[str]) -> None:
            return None

        async def get(self, id=None, *args, **kwargs) -> Response:
            return await self.serialize(
                dict(id='foo', name='foo-name', rel=dict(id='bar', description='bar-description'))
            )

        async def get_all(self, *args, **kwargs) -> Response:
            return await self.serialize(
                [
                    dict(id='foo', name='foo-name', rel=dict(id='bar', description='bar-description')),
                    dict(id='foo2', name='foo2-name', rel=dict(id='bar2', description='bar2-description')),
                ],
                many=True
            )

    class TResourceNotIncluded(BaseResource):
        type_ = 'test-resource-not-included'
        schema = TSchema

        async def get(self, id=None, *args, **kwargs) -> Response:
            return await self.serialize(
                dict(id='foo', name='foo-name', rel=dict(id='bar', description='bar-description'))
            )

        async def get_all(self, *args, **kwargs) -> Response:
            return await self.serialize(
                [dict(id='foo2', name='foo2-name', rel=dict(id='bar2', description='bar2-description'))],
                many=True
            )

    TResource.register_routes(app, '/')
    TResourceNotIncluded.register_routes(app, '/')
    return app


def test_included_data(included_app: Starlette):
    test_client = TestClient(app=included_app)
    rv = test_client.get('/test-resource/foo?include=rel')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': {
            'id': 'foo',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo-name',
            },
            'relationships': {
                'rel': {
                    'data': {
                        'type': 'test-related-resource',
                        'id': 'bar',
                    }
                }
            }
        },
        'included': [
            {
                'id': 'bar',
                'type': 'test-related-resource',
                'attributes': {
                    'description': 'bar-description',
                }
            }
        ]
    }


def test_included_data_many(included_app: Starlette):
    test_client = TestClient(app=included_app)
    rv = test_client.get('/test-resource/?include=rel')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [
            {
                'id': 'foo',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo-name',
                },
                'relationships': {
                    'rel': {
                        'data': {
                            'type': 'test-related-resource',
                            'id': 'bar',
                        }
                    }
                }
            },
            {
                'id': 'foo2',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo2-name',
                },
                'relationships': {
                    'rel': {
                        'data': {
                            'type': 'test-related-resource',
                            'id': 'bar2',
                        }
                    }
                }
            }
        ],
        'included': [
            {
                'id': 'bar',
                'type': 'test-related-resource',
                'attributes': {
                    'description': 'bar-description',
                }
            },
            {
                'id': 'bar2',
                'type': 'test-related-resource',
                'attributes': {
                    'description': 'bar2-description',
                }
            }
        ]
    }


def test_no_included_data(included_app: Starlette):
    # if resource does not override `prepare_relations`,
    # compound documents will not be generated
    test_client = TestClient(app=included_app)
    rv = test_client.get('/test-resource-not-included/foo?include=rel')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': {
            'id': 'foo',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo-name',
            },
            'relationships': {
                'rel': {
                    'data': {
                        'type': 'test-related-resource',
                        'id': 'bar',
                    }
                }
            }
        }
    }

    rv = test_client.get('/test-resource-not-included/?include=rel')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [{
            'id': 'foo2',
            'type': 'test-resource',
            'attributes': {
                'name': 'foo2-name',
            },
            'relationships': {
                'rel': {
                    'data': {
                        'type': 'test-related-resource',
                        'id': 'bar2',
                    }
                }
            }
        }]
    }


def test_handle_error_logs_unhandled_exceptions(app: Starlette, caplog):
    # this should be useful, we don't want to return 500 exceptions without knowing what the error was.
    exc = Exception('TestException was raised')

    class TResource(BaseResource):
        type_ = 'test-resource'

        async def get(self, id=None, *args, **kwargs) -> Response:
            raise exc

    TResource.register_routes(app, '/')

    test_client = TestClient(app)
    rv = test_client.get('/test-resource/foo')
    assert rv.status_code == 500
    assert rv.json() == {
        'errors': [{'detail': 'Internal server error'}]
    }
    exception_log_message = (
        'starlette_jsonapi.resource', logging.ERROR, 'Encountered an error while handling request.'
    )
    assert exception_log_message in caplog.record_tuples
    assert any(log.exc_info[1] == exc and log.name == 'starlette_jsonapi.resource' for log in caplog.records)


def test_method_not_allowed(app: Starlette):
    class TResource(BaseResource):
        type_ = 'test-resource'
        allowed_methods = {'GET'}

        async def get_all(self, *args, **kwargs) -> Response:
            return Response(status_code=200)

        async def post(self, *args, **kwargs) -> Response:
            return Response(status_code=200)

    TResource.register_routes(app, '/')

    test_client = TestClient(app)
    rv = test_client.get('/test-resource/')
    assert rv.status_code == 200

    rv = test_client.post('/test-resource/')
    assert rv.status_code == 405
    assert rv.json() == {
        'errors': [{'detail': 'Method Not Allowed'}]
    }


def test_register_without_type_(app: Starlette):
    class TResource(BaseResource):
        pass

    with pytest.raises(Exception) as exc:
        TResource.register_routes(app, '/')
    assert str(exc.value) == 'Cannot register a resource without specifying its `type_`.'


@pytest.fixture()
def relationship_app(app: Starlette):
    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        rel = JSONAPIRelationship(
            schema='TRelatedSchema',
            type_='test-related-resource',
            include_resource_linkage=True,
        )

        class Meta:
            type_ = 'test-resource'

    class TRelatedSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

        class Meta:
            type_ = 'test-related-resource'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

        async def get(self, parent_id: str, *args, **kwargs) -> Response:
            return await self.serialize(
                dict(
                    id='foo', name='foo-name',
                    rel=dict(id='bar', description='bar-description'),
                )
            )

        async def post(self, parent_id: str, *args, **kwargs) -> Response:
            relationship_id = await self.deserialize_ids()
            return await self.serialize(
                dict(
                    id=parent_id, name='foo-name',
                    rel=dict(id=relationship_id, description='bar-description'),
                )
            )

    TResource.register_routes(app, '/')
    TResourceRel.register_routes(app)

    return app


def test_relationship_resource(relationship_app: Starlette):
    test_client = TestClient(app=relationship_app)
    rv = test_client.get('/test-resource/foo/relationships/rel')
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': {
            'type': 'test-related-resource',
            'id': 'bar'
        }
    }

    rv = test_client.post(
        '/test-resource/foo/relationships/rel',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': {
                'type': 'test-related-resource',
                'id': 'rel2',
            }
        }
    )
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': {
            'type': 'test-related-resource',
            'id': 'rel2',
        }
    }

    # test missing data
    rv = test_client.post(
        '/test-resource/foo/relationships/rel',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Must include a `data` key'}
        ]
    }

    # test missing id
    rv = test_client.post(
        '/test-resource/foo/relationships/rel',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': {
                'type': 'test-related-resource',
            }
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Must have an `id` field'}
        ]
    }


@pytest.fixture()
def relationship_many_app(app: Starlette):
    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        rel_many = JSONAPIRelationship(
            schema='TRelatedSchema',
            type_='test-related-resource',
            include_resource_linkage=True,
            many=True
        )

        class Meta:
            type_ = 'test-resource'

    class TRelatedSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

        class Meta:
            type_ = 'test-related-resource'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel_many'

        async def get(self, parent_id: str, *args, **kwargs) -> Response:
            return await self.serialize(
                dict(
                    id='foo',
                    name='foo-name',
                    rel_many=[
                        dict(id='bar1', description='bar1-description'),
                        dict(id='bar2', description='bar2-description'),
                    ],
                )
            )

        async def post(self, parent_id: str, *args, **kwargs) -> Response:
            relationship_ids = await self.deserialize_ids()
            return await self.serialize(
                dict(
                    id=parent_id,
                    name='foo-name',
                    rel_many=[
                        dict(id='bar1', description='bar1-description'),
                        dict(id='bar2', description='bar2-description'),
                    ] + [
                        dict(id=relationship_id, description='bar-added-description')
                        for relationship_id in relationship_ids
                    ],
                )
            )

    TResource.register_routes(app, '/')
    TResourceRel.register_routes(app)

    return app


def test_relationship_many_resource(relationship_many_app: Starlette):
    test_client = TestClient(app=relationship_many_app)
    rv = test_client.get('/test-resource/foo/relationships/rel_many')
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': [
            {
                'type': 'test-related-resource',
                'id': 'bar1'
            },
            {
                'type': 'test-related-resource',
                'id': 'bar2'
            },
        ]
    }

    rv = test_client.post(
        '/test-resource/foo/relationships/rel_many',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': [{
                'type': 'test-related-resource',
                'id': 'bar3',
            }]
        }
    )
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': [
            {
                'type': 'test-related-resource',
                'id': 'bar1'
            },
            {
                'type': 'test-related-resource',
                'id': 'bar2'
            },
            {
                'type': 'test-related-resource',
                'id': 'bar3'
            },
        ]
    }

    # test missing data
    rv = test_client.post(
        '/test-resource/foo/relationships/rel_many',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Must include a `data` key'}
        ]
    }

    # test missing id
    rv = test_client.post(
        '/test-resource/foo/relationships/rel_many',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': [
                {'type': 'test-related-resource'}
            ]
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Must have an `id` field'}
        ]
    }

    # test expected list
    rv = test_client.post(
        '/test-resource/foo/relationships/rel_many',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': {
                'type': 'test-related-resource',
                'id': 'test-expected-list'
            }
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Relationship is list-like'}
        ]
    }
