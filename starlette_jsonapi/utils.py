from typing import Optional, Set, Dict, List

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

    For example, if a request were to reach
        `/some-resource/?include=foo,foo.bar`
    then:
        `parse_included_params(request) == {'foo', 'foo.bar'}`
    """
    include = request.query_params.get('include')
    if include:
        include = set(include.split(','))
        return include
    return None


def parse_sparse_fields_params(request: Request) -> Dict[str, List[str]]:
    """
    Parses a request's `fields` query parameter, if present,
    and returns a dictionary of resource type -> sparse fields.

    For example, if a request were to reach
        `/some-resource/?fields[some-resource]=foo,bar`
    then:
        `parse_sparse_fields_params(request) == {'some-resource': ['foo', 'bar']}`
    """
    sparse_fields = dict()
    for qp_name, qp_value in request.query_params.items():
        if qp_name.startswith('fields[') and qp_name.endswith(']'):
            resource_name_start = qp_name.index('[') + 1
            resource_name_end = qp_name.index(']')
            resource_name = qp_name[resource_name_start:resource_name_end]
            if not resource_name or not qp_value or not all(qp_value.split(',')):
                raise JSONAPIException(status_code=400, detail='Incorrect sparse fields request.')

            sparse_fields[resource_name] = qp_value.split(',')
    return sparse_fields


def filter_sparse_fields(item: dict, sparse_fields) -> dict:
    """
    Given a dictionary representation of an item,
    mutate in place to drop fields according to a sparse fields request.

    https://jsonapi.org/format/#fetching-sparse-fieldsets
    """
    # filter `attributes`
    item_attributes = item.get('attributes')
    if item_attributes:
        new_attributes = item_attributes.copy()
        for attr_name in item_attributes:
            if attr_name not in sparse_fields:
                new_attributes.pop(attr_name, None)
        if new_attributes:
            item['attributes'] = new_attributes
        else:
            del item['attributes']
    # filter `relationships`
    item_relationships = item.get('relationships')
    if item_relationships:
        new_relationships = item_relationships.copy()
        for rel_name in item_relationships:
            if rel_name not in sparse_fields:
                new_relationships.pop(rel_name, None)
        if new_relationships:
            item['relationships'] = new_relationships
        else:
            del item['relationships']
    return item
