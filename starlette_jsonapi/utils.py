from typing import Optional, Set

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from starlette_jsonapi.exceptions import JSONAPIException
from starlette_jsonapi.responses import JSONAPIResponse


def serialize_error(exc: Exception) -> JSONAPIResponse:
    """
    Serializes exception according to the json:api spec
    and returns the equivalent JSONAPIResponse.
    """
    if isinstance(exc, JSONAPIException):
        status_code = exc.status_code
        errors = exc.errors
    elif isinstance(exc, HTTPException):
        status_code = exc.status_code
        errors = [{'detail': exc.detail}]
    else:
        status_code = 500
        errors = [{'detail': 'Internal server error'}]

    error_body = {
        'errors': errors
    }
    return JSONAPIResponse(status_code=status_code, content=error_body)


def register_jsonapi_exception_handlers(app: Starlette):
    """
    Registers exception handlers on a Starlette app,
    serializing uncaught Exception and HTTPException to a json:api compliant body.
    """
    async def _serialize_error(request: Request, exc: Exception) -> Response:
        return serialize_error(exc)

    app.add_exception_handler(Exception, _serialize_error)
    app.add_exception_handler(HTTPException, _serialize_error)


def parse_included_params(request: Request) -> Optional[Set[str]]:
    """
    Parses a request's `include` query parameter, if present,
    and returns a sequence of included relations.

    For example, if a request were to reach `/some-resource/?include=foo,foo.bar`, then:
        `parse_included_params(request) -> {'foo', 'foo.bar'}`
    """
    include = request.query_params.get('include')
    if include:
        include = set(include.split(','))
        return include
    return None
