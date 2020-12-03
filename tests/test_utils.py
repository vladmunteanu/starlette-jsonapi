import json

from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from starlette_jsonapi.exceptions import JSONAPIException
from starlette_jsonapi.responses import JSONAPIResponse
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
        'errors': [{'detail': 'foo'}, {'detail': 'bar'}, {'detail': 'Bad Request'}]
    }

    error1 = JSONAPIException(404, 'error1')
    error2 = JSONAPIException(400, 'error2')
    final_error = JSONAPIException(400, 'final', errors=error1.errors + error2.errors)
    response = serialize_error(final_error)
    assert isinstance(response, JSONAPIResponse)
    assert response.status_code == 400
    assert json.loads(response.body) == {
        'errors': [{'detail': 'error1'}, {'detail': 'error2'}, {'detail': 'final'}]
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
