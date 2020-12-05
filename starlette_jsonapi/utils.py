from typing import Optional, Set, Dict, List, Union

from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from starlette_jsonapi.exceptions import JSONAPIException
from starlette_jsonapi.responses import JSONAPIResponse


def serialize_error(exc: Exception) -> JSONAPIResponse:
    """
    Serializes exception according to the json:api spec
    and returns the equivalent :class:`JSONAPIResponse`.
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
    Parses a request's ``include`` query parameter, if present,
    and returns a sequence of included relations.

    Example:

    .. code-block:: python

        # request URL /some-resource/?include=foo,foo.bar
        assert parse_included_params(request) == {'foo', 'foo.bar'}
    """
    include = request.query_params.get('include')
    if include:
        include = set(include.split(','))
        return include
    return None


def parse_sparse_fields_params(request: Request) -> Dict[str, List[str]]:
    """
    Parses a request's ``fields`` query parameter, if present,
    and returns a dictionary of resource type -> sparse fields.

    Example:

    .. code-block:: python

        # request URL: /articles/?fields[articles]=title,content
        assert parse_sparse_fields_params(request) == {'articles': ['title', 'content']}
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


def filter_sparse_fields(item: dict, sparse_fields: List[str]) -> dict:
    """
    Given a dictionary with the json:api representation of an item,
    drops any attributes or relationships that are not found in ``sparse_fields``
    and returns a new dictionary.

    For detailed information, check the json:api
    `spec <https://jsonapi.org/format/#fetching-sparse-fieldsets>`_.
    """
    new_item = item.copy()
    # filter `attributes`
    item_attributes = new_item.get('attributes')
    if item_attributes:
        new_attributes = item_attributes.copy()
        for attr_name in item_attributes:
            if attr_name not in sparse_fields:
                new_attributes.pop(attr_name, None)
        if new_attributes:
            new_item['attributes'] = new_attributes
        else:
            del new_item['attributes']
    # filter `relationships`
    item_relationships = new_item.get('relationships')
    if item_relationships:
        new_relationships = item_relationships.copy()
        for rel_name in item_relationships:
            if rel_name not in sparse_fields:
                new_relationships.pop(rel_name, None)
        if new_relationships:
            new_item['relationships'] = new_relationships
        else:
            del new_item['relationships']
    return new_item


def process_sparse_fields(serialized_data: dict, many: bool = False, sparse_fields: dict = None) -> dict:
    """
    Processes sparse fields requests by removing extra attributes
    and relationships from the final serialized data.

    If a client does not specify the set of fields for a given resource type,
    all fields will be included.

    Consult the `json:api spec <https://jsonapi.org/format/#fetching-sparse-fieldsets>`_
    for more information.
    """
    if not sparse_fields or not serialized_data.get('data'):
        return serialized_data

    data = serialized_data['data']
    new_data = [] if many else {}  # type: Union[List, dict]

    included = serialized_data.get('included', None)
    new_included = []

    # process sparse-fields for `data`
    if many:
        new_data = []
        for item in data:
            if item['type'] in sparse_fields:
                new_data.append(filter_sparse_fields(item, sparse_fields[item['type']]))
            else:
                new_data.append(item)
    else:
        if data['type'] in sparse_fields:
            new_data = filter_sparse_fields(data, sparse_fields[data['type']])
        else:
            new_data = data

    # process sparse-fields for `included`
    if included:
        for item in included:
            if item['type'] in sparse_fields:
                new_included.append(filter_sparse_fields(item, sparse_fields[item['type']]))
            else:
                new_included.append(item)

    new_serialized_data = serialized_data.copy()
    new_serialized_data['data'] = new_data
    if new_included:
        new_serialized_data['included'] = new_included

    return new_serialized_data


def prefix_url_path(app: Starlette, path: str, **kwargs):
    """
    Prefixes all URLs generated by the framework with the value of ``app.url_prefix``, if set.
    Can be used to generate absolute links.
    """
    prefix = getattr(app, 'url_prefix', '')
    return f'{prefix}{app.url_path_for(path, **kwargs)}'
