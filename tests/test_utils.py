import json

from starlette.exceptions import HTTPException
from starlette.testclient import TestClient

from starlette_jsonapi.exceptions import JSONAPIException
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.utils import (
    serialize_error, register_jsonapi_exception_handlers, filter_sparse_fields,
    process_sparse_fields,
)


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


def test_filter_sparse_fields_removes_fields():
    jsonapi_repr = {
        'id': '123',
        'type': 'users',
        'attributes': {
            'name': 'User 1',
            'country': 'US',
        },
        'relationships': {
            'organization': {
                'data': {
                    'type': 'organizations',
                    'id': '456',
                }
            }
        }
    }

    assert filter_sparse_fields(jsonapi_repr, ['name']) == {
        'id': '123',
        'type': 'users',
        'attributes': {
            'name': 'User 1',
        }
    }

    # check that the original data has not been mutated
    assert 'country' in jsonapi_repr['attributes']
    assert 'relationships' in jsonapi_repr


def test_filter_sparse_fields_unknown_field():
    jsonapi_repr = {
        'id': '123',
        'type': 'users',
        'attributes': {
            'name': 'User 1',
            'country': 'US',
        },
        'relationships': {
            'organization': {
                'data': {
                    'type': 'organizations',
                    'id': '456',
                }
            }
        }
    }

    assert filter_sparse_fields(jsonapi_repr, ['unknown']) == {
        'id': '123',
        'type': 'users',
    }

    # check that the original data has not been mutated
    assert 'attributes' in jsonapi_repr
    assert 'relationships' in jsonapi_repr


def test_process_sparse_fields_single():
    complete_jsonapi_repr = {
        'data': {
            'id': '123',
            'type': 'users',
            'attributes': {
                'name': 'User 1',
                'country': 'US',
            },
            'relationships': {
                'organization': {
                    'data': {
                        'type': 'organizations',
                        'id': '456',
                    }
                }
            }
        },
        'meta': {
            'key': 'value',
        }
    }

    assert process_sparse_fields(
        complete_jsonapi_repr,
        many=False, sparse_fields={'users': 'unknown'},
    ) == {
        'data': {
            'id': '123',
            'type': 'users',
        },
        'meta': {
            'key': 'value',
        }
    }


def test_process_sparse_fields_many():
    complete_jsonapi_repr = {
        'data': [
            {
                'id': '1',
                'type': 'users',
                'attributes': {
                    'name': 'User 1',
                    'country': 'US',
                },
                'relationships': {
                    'organization': {
                        'data': {
                            'type': 'organizations',
                            'id': '1',
                        }
                    }
                }
            },
            {
                'id': '2',
                'type': 'users',
                'attributes': {
                    'name': 'User 2',
                    'country': 'RO',
                },
                'relationships': {
                    'organization': {
                        'data': {
                            'type': 'organizations',
                            'id': '1',
                        }
                    }
                }
            },
        ],
        'meta': {
            'key': 'value',
        }
    }

    assert process_sparse_fields(
        complete_jsonapi_repr,
        many=True, sparse_fields={'users': 'unknown'},
    ) == {
        'data': [
            {
                'id': '1',
                'type': 'users',
            },
            {
                'id': '2',
                'type': 'users',
            }
        ],
        'meta': {
            'key': 'value',
        }
    }


def test_process_sparse_fields_included():
    complete_jsonapi_repr = {
        'data': {
            'id': '123',
            'type': 'users',
            'attributes': {
                'name': 'User 1',
                'country': 'US',
            },
            'relationships': {
                'organization': {
                    'data': {
                        'type': 'organizations',
                        'id': '456',
                    }
                }
            }
        },
        'included': [
            {
                'id': '456',
                'type': 'organizations',
                'attributes': {
                    'name': 'Organization 1',
                }
            }
        ],
        'meta': {
            'key': 'value',
        }
    }

    assert process_sparse_fields(
        complete_jsonapi_repr,
        many=False, sparse_fields={'users': 'unknown'},
    ) == {
        'data': {
            'id': '123',
            'type': 'users',
        },
        'included': [
            {
                'id': '456',
                'type': 'organizations',
                'attributes': {
                    'name': 'Organization 1',
                }
            }
        ],
        'meta': {
            'key': 'value',
        }
    }


def test_process_sparse_fields_without_fields():
    complete_jsonapi_repr = {
        'data': {
            'id': '123',
            'type': 'users',
            'attributes': {
                'name': 'User 1',
                'country': 'US',
            }
        }
    }

    assert process_sparse_fields(complete_jsonapi_repr, many=False) == complete_jsonapi_repr
    assert process_sparse_fields(complete_jsonapi_repr, many=False, sparse_fields={}) == complete_jsonapi_repr
