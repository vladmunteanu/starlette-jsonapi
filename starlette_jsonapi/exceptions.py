from typing import List

from starlette.exceptions import HTTPException


class JSONAPIException(HTTPException):

    def __init__(self, status_code: int, detail: str = None, errors: List[dict] = None) -> None:
        super().__init__(status_code, detail=detail)
        self.errors = errors
        if not self.errors:
            self.errors = [{'detail': self.detail}]


class ResourceNotFound(JSONAPIException):
    detail: str = 'Resource object not found.'

    def __init__(self, status_code: int = 404, detail: str = None) -> None:
        super().__init__(
            status_code,
            detail=detail if detail is not None else self.detail,
            errors=None,
        )
