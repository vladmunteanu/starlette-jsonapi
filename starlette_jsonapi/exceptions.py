from typing import List

from starlette.exceptions import HTTPException


class JSONAPIException(HTTPException):
    """ HTTP exception with json:api representation. """

    def __init__(self, status_code: int, detail: str = None, errors: List[dict] = None) -> None:
        """
        Base json:api exception class.

        :param status_code: HTTP status code
        :param detail: Optional, error detail, will be serialized in the final HTTP response.
                       **DO NOT** include sensitive information here.
                       If not specified, the HTTP message associated to ``status_code``
                       will be used.
        :param errors: Optional, list of json:api error representations.
                       Used if multiple errors are returned.

                       .. code-block:: python

                           import json
                           from starlette_jsonapi.utils import serialize_error

                           error1 = JSONAPIException(400, 'foo')
                           error2 = JSONAPIException(400, 'bar')
                           final_error = JSONAPIException(
                               400, 'final', errors=error1.errors + error2.errors
                           )
                           response = serialize_error(final_error)
                           assert json.loads(response.body)['errors'] == [
                               {'detail': 'foo'},
                               {'detail': 'bar'},
                               {'detail': 'final'},
                           ]
        """
        super().__init__(status_code, detail=detail)
        self.errors = errors or []
        self.errors.append({'detail': self.detail})


class ResourceNotFound(JSONAPIException):
    """ HTTP 404 error, serialized according to json:api. """
    detail: str = 'Resource object not found.'

    def __init__(self, status_code: int = 404, detail: str = None) -> None:
        super().__init__(
            status_code,
            detail=detail if detail is not None else self.detail,
            errors=None,
        )
