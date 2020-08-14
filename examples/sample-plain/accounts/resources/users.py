import logging
from typing import List, Any

from marshmallow_jsonapi import fields
from starlette.exceptions import HTTPException
from starlette.responses import Response

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema

from accounts.exceptions import UserNotFound, OrganizationNotFound
from accounts.models import User, Organization

logger = logging.getLogger(__name__)


class UserSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    username = fields.Str(required=True)

    organization = JSONAPIRelationship(
        type_='organizations',
        schema='OrganizationSchema',
        include_resource_linkage=True,
        required=True,
        related_resource='OrganizationsResource',
        related_route='users:organization',
        related_route_kwargs={'id': '<id>'},
    )

    class Meta:
        type_ = 'users'
        self_route = 'users:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'users:get_all'


class UsersResource(BaseResource):
    type_ = 'users'
    schema = UserSchema
    id_mask = 'int'

    async def prepare_relations(self, obj: User, relations: List[str]):
        """
        We override this to allow `included` requests against this resource,
        but we don't actually have to do anything here.
        The attribute is already populated because we're using plain NamedTuples.
        """
        return None

    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        return await self.to_response(await self.serialize(data=user))

    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        json_body = await self.deserialize_body(partial=True)
        username = json_body.get('username')
        if username:
            user.username = username

        organization_id = json_body.get('organization')
        if organization_id:
            org = Organization.get_item(int(organization_id))
            if not org:
                raise OrganizationNotFound
            user.organization = org

        user.save()

        return await self.to_response(await self.serialize(data=user))

    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        user.delete()

        return JSONAPIResponse(status_code=204)

    async def get_all(self, *args, **kwargs) -> Response:
        users = User.get_items()
        return await self.to_response(await self.serialize(data=users, many=True))

    async def post(self, *args, **kwargs) -> Response:
        json_body = await self.deserialize_body()

        user = User()
        username = json_body.get('username')
        if username:
            user.username = username
        else:
            raise HTTPException(status_code=400, detail='A valid `username` is required.')

        organization_id = json_body.get('organization')
        org = Organization.get_item(int(organization_id))
        if not org:
            raise OrganizationNotFound
        user.organization = org

        user.save()

        result = await self.serialize(data=user)
        return await self.to_response(result, status_code=201)

    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        if relationship == 'organization' and related_id is None:
            return await self.to_response(await self.serialize_related(user.organization))
        raise HTTPException(status_code=404)
