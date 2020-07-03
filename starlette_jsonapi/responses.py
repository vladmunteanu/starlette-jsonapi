from typing import Any

from starlette.responses import JSONResponse


class JSONAPIResponse(JSONResponse):
    media_type = 'application/vnd.api+json'

    def render(self, content: Any) -> bytes:
        if content is None:
            return b''
        return super().render(content)
