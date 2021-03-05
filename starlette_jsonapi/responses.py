from typing import Any

from starlette.responses import JSONResponse


class JSONAPIResponse(JSONResponse):
    """
    Base response class for json:api requests, sets `Content-Type: application/vnd.api+json`.

    For detailed information, see `Starlette responses <https://www.starlette.io/responses/>`_.
    """
    media_type = 'application/vnd.api+json'

    def render(self, content: Any) -> bytes:
        if content is None:
            return b''
        return super().render(content)
