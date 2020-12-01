from starlette.requests import Request
from starlette.responses import Response
from starlette_jsonapi.resource import BaseResource, BaseRelationshipResource

from accounts.app import Session


class BaseResourceSQLA(BaseResource):
    register_resource = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_session = self.request_context['db_session']

    @classmethod
    async def before_request(cls, request: Request, request_context: dict) -> None:
        db_session = Session()
        request_context['db_session'] = db_session

    @classmethod
    async def after_request(cls, request: Request, request_context: dict, response: Response) -> None:
        request_context['db_session'].close()


class BaseRelationshipResourceSQLA(BaseRelationshipResource):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_session = self.request_context['db_session']

    @classmethod
    async def before_request(cls, request: Request, request_context: dict) -> None:
        db_session = Session()
        request_context['db_session'] = db_session

    @classmethod
    async def after_request(cls, request: Request, request_context: dict, response: Response) -> None:
        request_context['db_session'].close()
