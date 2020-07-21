from asyncio import Future
from unittest import mock
from typing import Sequence, Optional

import pytest
from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.testclient import TestClient

from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.pagination import BasePaginator
from starlette_jsonapi.schema import JSONAPISchema


def test_paginator_total_page_count():
    # empty object list
    paginator = BasePaginator(object_list=[])
    assert paginator.total_page_count == 1

    # populated object list
    paginator = BasePaginator(object_list=list(range(4)))
    paginator.page_size = 2
    assert paginator.total_page_count == 2

    # inexact division
    paginator = BasePaginator(object_list=list(range(5)))
    paginator.page_size = 2
    assert paginator.total_page_count == 3


def test_paginator_unimplemented_methods_throw_exceptions():
    class TPaginator(BasePaginator):
        pass
    paginator = TPaginator(object_list=[])

    with pytest.raises(Exception) as exc:
        paginator.slice_object_list(page=1, size=2)
    assert str(exc.value) == '`slice_object_list` method not implemented'

    with pytest.raises(Exception) as exc:
        paginator.has_next()
    assert str(exc.value) == '`has_next()` must be implemented to generate pagination links'

    with pytest.raises(Exception) as exc:
        paginator.has_previous()
    assert str(exc.value) == '`has_previous()` must be implemented to generate pagination links'

    request = mock.MagicMock()
    with pytest.raises(Exception) as exc:
        paginator.get_next_link(request)
    assert str(exc.value) == '`get_next_link()` must be implemented to generate pagination links'

    with pytest.raises(Exception) as exc:
        paginator.get_previous_link(request)
    assert str(exc.value) == '`get_previous_link()` must be implemented to generate pagination links'

    with pytest.raises(Exception) as exc:
        paginator.get_last_link(request)
    assert str(exc.value) == '`get_last_link()` must be implemented to generate pagination links'


def test_paginator_validate_page_size_value():
    paginator = BasePaginator(object_list=[])
    paginator.size_param_name = 'size'
    paginator.max_size = 4

    # string value
    with pytest.raises(Exception) as exc:
        paginator.validate_page_size_value('test')
    assert str(exc.value) == 'page[size] must be a positive integer; got test'

    # null value
    with pytest.raises(Exception) as exc:
        paginator.validate_page_size_value(None)
    assert str(exc.value) == 'page[size] must be a positive integer; got None'

    # negative integer value
    with pytest.raises(Exception) as exc:
        paginator.validate_page_size_value(-1)
    assert str(exc.value) == 'page[size] must be a positive integer; got -1'

    # max size restriction
    assert paginator.validate_page_size_value(5) == 4


def test_paginator_validate_page_value():
    paginator = BasePaginator(object_list=[])
    assert paginator.validate_page_value(1) == '1'


@pytest.fixture()
def pagination_app(app: Starlette):
    class TPaginator(BasePaginator):
        page_param_name = 'number'
        size_param_name = 'size'
        default_size = 2
        max_size = 3

        def __init__(self, object_list: Sequence):
            self.object_list = object_list
            self.current_page: Optional[int] = None
            self.page_size: Optional[int] = None
            self.sliced_object_list: Optional[Sequence] = None
            self.request: Optional[Request] = None
            self._pagination_complete: bool = False

        def validate_page_value(self, page) -> int:
            if not page:
                return 1
            return int(page)

        def slice_object_list(self, page, size) -> Sequence:
            page = page - 1
            objects = self.object_list[(page * size):(page + 1) * size]
            return objects

        def has_next(self):
            return self.current_page < self.total_page_count

        def has_previous(self):
            return self.current_page > 1

        def get_next_link(self, request):
            return self.create_pagination_link(request, self.current_page + 1)

        def get_previous_link(self, request):
            return self.create_pagination_link(request, self.current_page - 1)

        def get_last_link(self, request):
            if self.current_page == 1 and not self.has_next():
                last_page = self.current_page
            else:
                last_page = self.total_page_count

            return self.create_pagination_link(request, last_page)

    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema
        pagination_class = TPaginator

        async def get_all(self, *args, **kwargs) -> Response:
            data = [
                dict(id=1, name='foo'),
                dict(id=2, name='foo'),
                dict(id=3, name='foo'),
                dict(id=4, name='foo')
            ]
            return await self.to_response(await self.serialize(data, many=True, paginate=True))

        async def get(self, id=None, *args, **kwargs) -> Response:
            return await self.to_response(await self.serialize(dict(id=id, name='foo')))

        async def post(self, *args, **kwargs) -> Response:
            return await self.to_response(await self.serialize(dict(id=id, name='foo')))

        async def patch(self, id=None, *args, **kwargs) -> Response:
            return await self.to_response(await self.serialize(dict(id=id, name='foo')))

        async def delete(self, id=None, *args, **kwargs) -> Response:
            return await self.to_response({})

    TResource.register_routes(app, '/')
    return app


def test_get_many_calls_pagination(pagination_app: Starlette):
    test_client = TestClient(app=pagination_app)
    paginate_request_mock = mock.MagicMock(return_value=Future())

    object_list = [dict(id=1, name='foo')]
    links = {'first': 'first', 'next': 'next'}
    paginate_request_mock.return_value.set_result((object_list, links))

    with mock.patch.object(BaseResource, 'paginate_request', paginate_request_mock):
        rv = test_client.get('/test-resource/')
        assert paginate_request_mock.called_with(object_list)
        assert rv.status_code == 200
        assert rv.json() == {
            'data': [
                {
                    'id': '1',
                    'type': 'test-resource',
                    'attributes': {
                        'name': 'foo'
                    }
                },
            ],
            'links': {
                'first': 'first',
                'next': 'next'
            }
        }


def test_incorrect_request_type(pagination_app: Starlette):
    test_client = TestClient(app=pagination_app)
    paginate_request_mock = mock.MagicMock(return_value=Future())
    paginate_request_mock.return_value.set_result(([], {}))

    with mock.patch.object(BaseResource, 'paginate_request', paginate_request_mock):
        rv = test_client.get('/test-resource/1')
        assert rv.status_code == 200
        assert paginate_request_mock.not_called

        rv = test_client.post('/test-resource/', {})
        assert rv.status_code == 200
        assert paginate_request_mock.not_called

        rv = test_client.patch('/test-resource/1', {})
        assert rv.status_code == 200
        assert paginate_request_mock.not_called

        rv = test_client.delete('/test-resource/1', )
        assert rv.status_code == 200
        assert paginate_request_mock.not_called


def test_specified_params(pagination_app: Starlette):
    test_client = TestClient(app=pagination_app)

    # only size param
    rv = test_client.get('/test-resource/?page[size]=1')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [
            {
                'id': '1',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
        ],
        'links': {
            'first': 'http://testserver/test-resource/?page%5Bsize%5D=1',
            'next': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=1',
            'prev': None,
            'last': 'http://testserver/test-resource/?page%5Bnumber%5D=4&page%5Bsize%5D=1',
        }
    }

    # page and size param
    rv = test_client.get('/test-resource/?page[number]=3&page[size]=1')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [
            {
                'id': '3',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
        ],
        'links': {
            'first': 'http://testserver/test-resource/?page%5Bsize%5D=1',
            'next': 'http://testserver/test-resource/?page%5Bnumber%5D=4&page%5Bsize%5D=1',
            'prev': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=1',
            'last': 'http://testserver/test-resource/?page%5Bnumber%5D=4&page%5Bsize%5D=1',
        }
    }


def test_enforced_size_values(pagination_app: Starlette):
    test_client = TestClient(app=pagination_app)

    # default size
    rv = test_client.get('/test-resource/')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [
            {
                'id': '1',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
            {
                'id': '2',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            }
        ],
        'links': {
            'first': 'http://testserver/test-resource/?page%5Bsize%5D=2',
            'next': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=2',
            'prev': None,
            'last': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=2',
        }
    }

    # max size restriction
    rv = test_client.get('/test-resource/?page[number]=1&page[size]=4')
    assert rv.status_code == 200
    assert rv.json() == {
        'data': [
            {
                'id': '1',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
            {
                'id': '2',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
            {
                'id': '3',
                'type': 'test-resource',
                'attributes': {
                    'name': 'foo'
                }
            },
        ],
        'links': {
            'first': 'http://testserver/test-resource/?page%5Bsize%5D=3',
            'next': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=3',
            'prev': None,
            'last': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=3',
        }
    }


def test_parameter_error(pagination_app: Starlette):
    test_client = TestClient(app=pagination_app)

    # zero value
    rv = test_client.get('/test-resource/?page[size]=0')
    assert rv.status_code == 400
    assert rv.json() == {
        'errors': [
            {
                'detail': 'page[size] must be a positive integer; got 0'
            }
        ]
    }

    # negative value
    rv = test_client.get('/test-resource/?page[size]=-1')
    assert rv.status_code == 400
    assert rv.json() == {
        'errors': [
            {
                'detail': 'page[size] must be a positive integer; got -1'
            }
        ]
    }

    # string value
    rv = test_client.get('/test-resource/?page[size]=test')
    assert rv.status_code == 400
    assert rv.json() == {
        'errors': [
            {
                'detail': 'page[size] must be a positive integer; got test'
            }
        ]
    }
