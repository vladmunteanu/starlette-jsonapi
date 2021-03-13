import logging
from typing import List, Any

from marshmallow_jsonapi import fields
from starlette.exceptions import HTTPException
from starlette.responses import Response

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.openapi import with_openapi_info, response_for_schema
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
        required=True,
        related_resource='OrganizationsResource',
        related_route='users:organization',
        related_route_kwargs={'id': '<id>'},
    )

    class Meta:
        type_ = 'users'
        self_route = 'users:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'users:get_many'


class UsersResource(BaseResource):
    type_ = 'users'
    schema = UserSchema
    id_mask = 'int'

    openapi_info = {
        'handlers': {
            'get': {
                'description': 'Retrieve an user by id.'
            },
            'get_related': {
                'description': 'Retrieve a related organization.'
            }
        }
    }

    async def include_relations(self, obj: User, relations: List[str]):
        """
        We override this to allow `included` requests against this resource,
        but we don't actually have to do anything here.
        The attribute is already populated because we're using plain NamedTuples.
        """
        return None

    @with_openapi_info(responses={'200': UserSchema, '404': UserNotFound})
    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        return await self.to_response(await self.serialize(data=user))

    @with_openapi_info(
        responses={
            '200': UserSchema,
            '404': UserNotFound,
        },
        request_body=UserSchema,
    )
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

    @with_openapi_info(
        responses={
            '204': {'description': 'The resource was deleted successfully.'},
            '404': UserNotFound,
        },
    )
    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        user.delete()

        return JSONAPIResponse(status_code=204)

    @with_openapi_info(
        responses={'200': UserSchema(many=True)}
    )
    async def get_many(self, *args, **kwargs) -> Response:
        users = User.get_items()
        return await self.to_response(await self.serialize(data=users, many=True))

    @with_openapi_info(
        responses={'201': UserSchema},
        request_body=UserSchema,
        summary='Create a new account',
    )
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

    @with_openapi_info(
        responses={'200': response_for_schema('OrganizationSchema')},
    )
    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        user = User.get_item(id)
        if not user:
            raise UserNotFound

        if relationship == 'organization' and related_id is None:
            return await self.to_response(await self.serialize_related(user.organization))
        raise HTTPException(status_code=404)
