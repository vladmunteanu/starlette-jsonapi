from starlette_jsonapi.responses import JSONAPIResponse


def test_jsonapi_response_headers():
    resp = JSONAPIResponse()
    assert resp.status_code == 200
    assert resp.headers['content-type'] == 'application/vnd.api+json'
    assert resp.body == b''
