import json

from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from starlette_jsonapi.exceptions import JSONAPIException
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.pagination import PaginationException
from starlette_jsonapi.utils import serialize_error, register_jsonapi_exception_handlers


def test_serialize_error():
    exc = Exception()
    response = serialize_error(exc)
    assert isinstance(response, JSONAPIResponse)
    assert response.status_code == 500
    assert json.loads(response.body) == {
        'errors': [{'detail': 'Internal server error'}]
    }

    exc = HTTPException(status_code=400)
    response = serialize_error(exc)
    assert isinstance(response, JSONAPIResponse)
    assert response.status_code == 400
    assert json.loads(response.body) == {
        'errors': [{'detail': 'Bad Request'}]
    }

    exc = JSONAPIException(status_code=400, errors=[{'detail': 'foo'}, {'detail': 'bar'}])
    response = serialize_error(exc)
    assert isinstance(response, JSONAPIResponse)
    assert response.status_code == 400
    assert json.loads(response.body) == {
        'errors': [{'detail': 'foo'}, {'detail': 'bar'}]
    }

    exc = PaginationException('Test exception')
    response = serialize_error(exc)
    assert isinstance(response, JSONAPIResponse)
    assert response.status_code == 400
    assert json.loads(response.body) == {
        'errors': [{'detail': 'Test exception'}]
    }


def test_uncaught_exceptions(app):
    register_jsonapi_exception_handlers(app)
    test_client = TestClient(app)
    rv = test_client.get('/does-not-exist')
    assert rv.status_code == 404
    assert rv.headers['Content-Type'] == 'application/vnd.api+json'
    assert rv.json() == {
        'errors': [
            {
                'detail': 'Not Found',
            }
        ]
    }
