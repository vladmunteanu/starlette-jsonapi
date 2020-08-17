from asyncio import Future
from math import ceil
from unittest import mock
from typing import Sequence, Dict, Optional, Type

import pytest
from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette.requests import URL
from starlette.responses import Response
from starlette.testclient import TestClient

from starlette_jsonapi import meta
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.pagination import (BasePagination, BasePageNumberPagination,
                                          BaseCursorPagination, BaseOffsetPagination)
from starlette_jsonapi.schema import JSONAPISchema


def test_process_query_params_called_on_init():
    paginator = BasePagination(request=mock.MagicMock(), data=[])
    assert paginator.process_query_params() is None

    process_query_params_mock = mock.MagicMock()
    with mock.patch.object(BasePagination, 'process_query_params', process_query_params_mock):
        BasePagination(request=mock.MagicMock(), data=[])
        assert process_query_params_mock.called


def test_unimplemented_slice_throws_error():
    class TPagination(BasePagination):
        pass

    paginator = TPagination(request=mock.MagicMock(), data=[])
    with pytest.raises(NotImplementedError):
        paginator.get_pagination()


def test_unimplemented_generate_pagination_links():
    class TPagination(BasePagination):
        def slice_data(self, params: dict = None) -> Sequence:
            return self.data

    paginator = TPagination(request=mock.MagicMock(), data=[1, 2, 3])
    data, links = paginator.get_pagination()
    assert links == {}


def test_base_page_number_pagination_process_query_params():
    # test initialization on specified values
    request = mock.MagicMock()
    request.query_params = {'page[number]': 1, 'page[size]': 1}
    paginator = BasePageNumberPagination(request=request, data=[])

    assert paginator.page_number == 1
    assert paginator.page_size == 1

    # test initialization for default values
    request = mock.MagicMock()
    request.query_params = {}
    paginator = BasePageNumberPagination(request=request, data=[])

    assert paginator.page_number == paginator.default_page_number
    assert paginator.page_size == paginator.default_page_size


def test_base_page_number_pagination_create_pagination_link():
    from starlette.requests import URL
    url = URL('http://testserver/test-resource')
    request = mock.MagicMock()
    request.url = url

    paginator = BasePageNumberPagination(request=request, data=[])
    link = paginator.create_pagination_link(page_number=2, page_size=4)
    assert link == 'http://testserver/test-resource?page%5Bnumber%5D=2&page%5Bsize%5D=4'


def test_base_offset_pagination_process_query_params():
    # test initialization on specified values
    request = mock.MagicMock()
    request.query_params = {'page[offset]': 1, 'page[size]': 1}
    paginator = BaseOffsetPagination(request=request, data=[])

    assert paginator.page_offset == 1
    assert paginator.page_size == 1

    # test initialization for default values
    request = mock.MagicMock()
    request.query_params = {}
    paginator = BaseOffsetPagination(request=request, data=[])

    assert paginator.page_offset == paginator.default_page_offset
    assert paginator.page_size == paginator.default_page_size


def test_base_offset_pagination_create_pagination_link():
    url = URL('http://testserver/test-resource')
    request = mock.MagicMock()
    request.url = url

    paginator = BaseOffsetPagination(request=request, data=[])
    link = paginator.create_pagination_link(page_offset=35, page_size=4)
    assert link == 'http://testserver/test-resource?page%5Boffset%5D=35&page%5Bsize%5D=4'


def test_base_cursor_pagination_process_query_params():
    # test initialization on specified values
    request = mock.MagicMock()
    request.query_params = {'page[after]': 2, 'page[before]': 4, 'page[size]': 1}
    paginator = BaseCursorPagination(request=request, data=[])

    assert paginator.page_before == 4
    assert paginator.page_after == 2
    assert paginator.page_size == 1

    # test initialization for default values
    request = mock.MagicMock()
    request.query_params = {}
    paginator = BaseCursorPagination(request=request, data=[])

    assert paginator.page_before == paginator.default_page_before
    assert paginator.page_after == paginator.default_page_after
    assert paginator.page_size == paginator.default_page_size


def test_base_cursor_pagination_create_pagination_link():
    url = URL('http://testserver/test-resource')
    request = mock.MagicMock()
    request.url = url

    paginator = BaseCursorPagination(request=request, data=[])
    link = paginator.create_pagination_link(page_after=2, page_before=6, page_size=4)
    assert link == 'http://testserver/test-resource?page%5Bsize%5D=4&page%5Bafter%5D=2&page%5Bbefore%5D=6'


@pytest.fixture()
def pagination_app(app: Starlette):
    class TPagination(BasePageNumberPagination):
        default_page_size = 2

        def process_query_params(self):
            super(TPagination, self).process_query_params()

        def slice_data(self, params: dict = None) -> Sequence:
            data = self.data[(self.page_number - 1) * self.page_size: self.page_number * self.page_size]
            return data

        def generate_pagination_links(self, params: dict = None) -> Dict[str, Optional[str]]:
            links = dict(first=None, next=None, prev=None, last=None)  # type: Dict[str, Optional[str]]
            page_count = ceil(len(self.data) / self.page_size)

            # first
            links['first'] = self.create_pagination_link(page_number=1, page_size=self.page_size)

            # last
            links['last'] = self.create_pagination_link(page_number=page_count, page_size=self.page_size)

            # next
            has_next = self.page_number < page_count
            if has_next:
                links['next'] = self.create_pagination_link(page_number=self.page_number + 1, page_size=self.page_size)

            # previous
            has_prev = self.page_number > 1
            if has_prev:
                links['prev'] = self.create_pagination_link(page_number=self.page_number - 1, page_size=self.page_size)

            return links

    class TSchema(JSONAPISchema):
        id = fields.Str(dump_only=True)
        name = fields.Str()

        class Meta:
            type_ = 'test-resource'

    class TResource(BaseResource):
        type_ = 'test-resource'
        schema = TSchema
        pagination_class = TPagination

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


def test_get_many_without_pagination_class(pagination_app: Starlette):
    resource = meta.registered_resources['TResource']  # type: Type[BaseResource]
    resource.pagination_class = None
    test_client = TestClient(app=pagination_app)

    with pytest.raises(Exception) as exc:
        test_client.get('/test-resource/')
        assert str(exc.value) == 'Pagination class must be defined to use pagination'


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
            'first': 'http://testserver/test-resource/?page%5Bnumber%5D=1&page%5Bsize%5D=1',
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
            'first': 'http://testserver/test-resource/?page%5Bnumber%5D=1&page%5Bsize%5D=1',
            'next': 'http://testserver/test-resource/?page%5Bnumber%5D=4&page%5Bsize%5D=1',
            'prev': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=1',
            'last': 'http://testserver/test-resource/?page%5Bnumber%5D=4&page%5Bsize%5D=1',
        }
    }


def test_default_value_enforcement(pagination_app: Starlette):
    test_client = TestClient(app=pagination_app)

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
            'first': 'http://testserver/test-resource/?page%5Bnumber%5D=1&page%5Bsize%5D=2',
            'next': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=2',
            'prev': None,
            'last': 'http://testserver/test-resource/?page%5Bnumber%5D=2&page%5Bsize%5D=2',
        }
    }
