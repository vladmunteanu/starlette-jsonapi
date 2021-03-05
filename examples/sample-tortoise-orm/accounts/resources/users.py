import logging
from typing import List, Any

from marshmallow_jsonapi import fields
from starlette.exceptions import HTTPException
from starlette.responses import Response, JSONResponse
from tortoise.exceptions import DoesNotExist

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.schema import JSONAPISchema

from accounts.exceptions import UserNotFound
from accounts.models import User, Organization

logger = logging.getLogger(__name__)


class UserSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    username = fields.Str(required=True)

    organization = JSONAPIRelationship(
        type_='organizations',
        schema='OrganizationSchema',
        id_attribute='organization_id',
        required=True,
        related_route='users:organization',
        related_route_kwargs={'id': '<id>'},
        related_resource='OrganizationsResource',
    )

    class Meta:
        type_ = 'users'
        strict = True
        self_route = 'users:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'users:get_many'


class UsersResource(BaseResource):
    type_ = 'users'
    schema = UserSchema
    id_mask = 'int'

    async def include_relations(self, obj: User, relations: List[str]):
        if 'organization' in relations:
            await obj.fetch_related('organization')

    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        try:
            user = await User.get(id=id)
        except DoesNotExist:
            raise UserNotFound

        return await self.to_response(await self.serialize(data=user))

    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        try:
            user = await User.get(id=id)
        except DoesNotExist:
            raise UserNotFound

        json_body = await self.deserialize_body(partial=True)
        username = json_body.get('username')
        if username:
            user.username = username

        organization_id = json_body.get('organization')
        if organization_id:
            try:
                org = await Organization.get(id=int(organization_id))
                user.organization = org
            except (DoesNotExist, ValueError, TypeError):
                raise HTTPException(status_code=404, detail='Related Organization not found.')

        await user.save()

        return await self.to_response(await self.serialize(data=user))

    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        try:
            user = await User.get(id=id)
        except DoesNotExist:
            raise UserNotFound

        await user.delete()

        return JSONResponse(status_code=204)

    async def get_many(self, *args, **kwargs) -> Response:
        users = await User.all()
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
        try:
            org = await Organization.get(id=int(organization_id))
            user.organization = org
        except (DoesNotExist, ValueError, TypeError):
            raise HTTPException(status_code=404, detail='Related Organization not found.')

        await user.save()

        result = await self.serialize(data=user)
        return await self.to_response(result, status_code=201)

    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        try:
            user = await User.get(id=id).prefetch_related('organization')
        except DoesNotExist:
            raise UserNotFound
        if relationship == 'organization' and related_id is None:
            return await self.to_response(await self.serialize_related(data=user.organization))
        raise HTTPException(status_code=404)
