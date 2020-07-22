import logging

import pytest
from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.testclient import TestClient

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseResource, BaseRelationshipResource
from starlette_jsonapi.schema import JSONAPISchema


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
            return await self.to_response(await self.serialize(
                dict(
                    id='foo', name='foo-name',
                    rel=dict(id='bar', description='bar-description'),
                )
            ))

        async def post(self, parent_id: str, *args, **kwargs) -> Response:
            relationship_id = await self.deserialize_ids()
            if relationship_id is None:
                relationship = None
            else:
                relationship = dict(id=relationship_id, description='bar-description')
            return await self.to_response(await self.serialize(
                dict(
                    id=parent_id, name='foo-name',
                    rel=relationship,
                )
            ))

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

    # test emptying relationship
    rv = test_client.post(
        '/test-resource/foo/relationships/rel',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': None
        }
    )
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': None
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
            return await self.to_response(await self.serialize(
                dict(
                    id='foo',
                    name='foo-name',
                    rel_many=[
                        dict(id='bar1', description='bar1-description'),
                        dict(id='bar2', description='bar2-description'),
                    ],
                )
            ))

        async def post(self, parent_id: str, *args, **kwargs) -> Response:
            relationship_ids = await self.deserialize_ids()
            relationships = [
                dict(id='bar1', description='bar1-description'),
                dict(id='bar2', description='bar2-description'),
            ]

            if relationship_ids:
                relationships += [
                    dict(id=relationship_id, description='bar-added-description')
                    for relationship_id in relationship_ids
                ]
            else:
                relationships = []

            return await self.to_response(await self.serialize(
                dict(
                    id=parent_id,
                    name='foo-name',
                    rel_many=relationships,
                )
            ))

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

    # test emptying relationship
    rv = test_client.post(
        '/test-resource/foo/relationships/rel_many',
        headers={'Content-Type': 'application/vnd.api+json'},
        json={
            'data': []
        }
    )
    assert rv.status_code == 200
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'data': []
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


@pytest.mark.parametrize(['method', 'url'], [
    ('get', '/test-resource/foo/relationships/rel'),
    ('patch', '/test-resource/foo/relationships/rel'),
    ('delete', '/test-resource/foo/relationships/rel'),
    ('post', '/test-resource/foo/relationships/rel'),
])
def test_relationship_resource_default_crud_methods(app: Starlette, method: str, url: str):
    class TResource(BaseResource):
        type_ = 'test-resource'

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

    TResource.register_routes(app=app, base_path='/')
    TResourceRel.register_routes(app=app)

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


def test_relationship_resource_incorrect_field(app: Starlette):
    class TResourceSchema(JSONAPISchema):
        class Meta:
            type_ = 'test-resource'
        id = fields.Str(dump_only=True)

    class TResource(BaseResource):
        schema = TResourceSchema
        type_ = 'test-resource'

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

        async def get(self, parent_id: str, *args, **kwargs) -> Response:
            """ we inverse status_code to check for the error """
            try:
                self._get_relationship_field()
            except AttributeError as exc:
                if str(exc) == f'Parent schema does not define `{self.relationship_name}` relationship.':
                    return Response(status_code=200)
            return Response(status_code=500)

    TResource.register_routes(app=app, base_path='/')
    TResourceRel.register_routes(app=app)

    client = TestClient(app=app)
    rv = client.get('/test-resource/foo/relationships/rel')
    assert rv.status_code == 200


def test_relationship_resource_expects_content_type(relationship_app: Starlette):
    test_client = TestClient(relationship_app)
    rv = test_client.post(
        '/test-resource/foo/relationships/rel',
        json={
            'data': {
                'type': 'test-related-resource',
                'id': 'bar'
            }
        }
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Incorrect or missing Content-Type header, expected `application/vnd.api+json`.'}
        ]
    }


def test_relationship_resource_expects_valid_json(relationship_app: Starlette):
    test_client = TestClient(relationship_app)
    rv = test_client.post(
        '/test-resource/foo/relationships/rel',
        headers={'Content-Type': 'application/vnd.api+json'}
    )
    assert rv.status_code == 400
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {'detail': 'Could not read request body.'}
        ]
    }


def test_handle_error_logs_unhandled_exceptions_in_relationship_resource(app: Starlette, caplog):
    # this should be useful, we don't want to return 500 exceptions without knowing what the error was.
    exc = Exception('TestException was raised')

    class TResourceSchema(JSONAPISchema):
        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        schema = TResourceSchema
        type_ = 'test-resource'

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

        async def get(self, parent_id: str, *args, **kwargs) -> Response:
            raise exc

    TResource.register_routes(app=app, base_path='/')
    TResourceRel.register_routes(app=app)

    test_client = TestClient(app)
    rv = test_client.get('/test-resource/foo/relationships/rel')
    assert rv.status_code == 500
    assert rv.json() == {
        'errors': [{'detail': 'Internal server error'}]
    }
    exception_log_message = (
        'starlette_jsonapi.resource', logging.ERROR, 'Encountered an error while handling request.'
    )
    assert exception_log_message in caplog.record_tuples
    assert any(log.exc_info[1] == exc and log.name == 'starlette_jsonapi.resource' for log in caplog.records)


def test_method_not_allowed_relationship_resource(app: Starlette):
    class TResourceSchema(JSONAPISchema):
        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        schema = TResourceSchema
        type_ = 'test-resource'

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'
        allowed_methods = {'DELETE'}

        async def get(self, parent_id: str, *args, **kwargs) -> Response:
            return Response(status_code=200)

    TResource.register_routes(app=app, base_path='/')
    TResourceRel.register_routes(app=app)

    test_client = TestClient(app)
    rv = test_client.get('/test-resource/foo/relationships/rel')
    assert rv.status_code == 405
    assert rv.json() == {
        'errors': [{'detail': 'Method Not Allowed'}]
    }


def test_relationship_resource_register_routes_missing_parent_type(app: Starlette):
    class TResourceSchema(JSONAPISchema):
        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        schema = TResourceSchema

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

    with pytest.raises(Exception) as exc:
        TResourceRel.register_routes(app=app)

    assert str(exc.value) == (
        'Cannot register a relationship resource if the `parent_resource` does not specify a `type_`.'
    )


def test_relationship_resource_register_routes_parent_registration_required(app: Starlette):
    class TResourceSchema(JSONAPISchema):
        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        schema = TResourceSchema
        type_ = 'test-resource'

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

    with pytest.raises(Exception) as exc:
        TResourceRel.register_routes(app=app)

    assert str(exc.value) == 'Parent resource should be registered first.'


@pytest.fixture()
def relationship_links_app(app: Starlette):
    class TRelatedSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        description = fields.Str()

        class Meta:
            type_ = 'test-related-resource'
            self_route = 'test-related-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-related-resource:get_all'

    class TRelatedResource(BaseResource):
        type_ = 'test-related-resource'
        schema = TRelatedSchema

    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        rel = JSONAPIRelationship(
            schema='TRelatedSchema',
            type_='test-related-resource',
            self_route='test-resource:relationship-rel',
            self_route_kwargs={'id': '<id>'},
            related_resource='TRelatedResource',
            related_route='test-resource:rel',
            related_route_kwargs={'id': '<id>'},
            include_resource_linkage=True,
        )

        class Meta:
            type_ = 'test-resource'
            self_route = 'test-resource:get'
            self_route_kwargs = {'id': '<id>'}
            self_route_many = 'test-resource:get_all'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema

    class TResourceRel(BaseRelationshipResource):
        parent_resource = TResource
        relationship_name = 'rel'

    TRelatedResource.register_routes(app, '/')
    TResource.register_routes(app, '/')
    TResourceRel.register_routes(app)

    return app


def test_related_resource_default_not_allowed(relationship_links_app: Starlette):
    test_client = TestClient(relationship_links_app)
    rv = test_client.get('/test-resource/1/rel')
    assert rv.status_code == 405


def test_related_resource_relationship_not_found(relationship_links_app: Starlette):
    test_client = TestClient(relationship_links_app)
    rv = test_client.get('/test-resource/1/non-existing-rel')
    assert rv.status_code == 404
    assert rv.json() == {
        'errors': [
            {'detail': 'Not Found'}
        ]
    }


def test_get_related_resource(relationship_links_app: Starlette):
    from starlette_jsonapi import meta

    async def get_related(self, id, relationship, *args, **kwargs):
        return await self.to_response(
            # we serialize the related object directly
            await self.serialize_related(
                dict(id='related-item-id', description='related-item-description'),
                id=id,
                relationship=relationship,
            )
        )

    TResource = meta.registered_resources.get('TResource')
    assert TResource is not None
    setattr(TResource, 'get_related', get_related)

    test_client = TestClient(relationship_links_app)
    rv = test_client.get('/test-resource/1/rel')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': {
            'id': 'related-item-id',
            'type': 'test-related-resource',
            'attributes': {
                'description': 'related-item-description',
            },
            'links': {
                'self': '/test-resource/1/rel',
            }
        },
        'links': {
            'self': '/test-resource/1/rel',
        }
    }


def test_get_related_resource_many(relationship_links_app: Starlette):
    from starlette_jsonapi import meta

    async def get_related(self, id, relationship, *args, **kwargs):
        return await self.to_response(
            # we serialize the related object directly
            await self.serialize_related(
                [
                    dict(id='related-item-id', description='related-item-description'),
                    dict(id='related-item-id-2', description='related-item-description-2'),
                ],
                id=id,
                relationship=relationship,
                many=True,
            )
        )

    TResource = meta.registered_resources.get('TResource')
    assert TResource is not None
    setattr(TResource, 'get_related', get_related)

    test_client = TestClient(relationship_links_app)
    rv = test_client.get('/test-resource/1/rel')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [
            {
                'id': 'related-item-id',
                'type': 'test-related-resource',
                'attributes': {
                    'description': 'related-item-description',
                },
                'links': {
                    'self': '/test-resource/1/rel',
                }
            },
            {
                'id': 'related-item-id-2',
                'type': 'test-related-resource',
                'attributes': {
                    'description': 'related-item-description-2',
                },
                'links': {
                    'self': '/test-resource/1/rel',
                }
            }
        ],
        'links': {
            'self': '/test-resource/1/rel',
        }
    }
