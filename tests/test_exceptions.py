from starlette_jsonapi.exceptions import ResourceNotFound


def test_resource_not_found():
    exc = ResourceNotFound()
    assert exc.status_code == 404
    assert exc.detail == 'Resource object not found.'

    exc = ResourceNotFound(detail='Foo not found.')
    assert exc.status_code == 404
    assert exc.detail == 'Foo not found.'
