import logging
from typing import List, Any

from marshmallow_jsonapi import fields
from starlette.exceptions import HTTPException
from starlette.responses import Response

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.openapi import (
    with_openapi_info, response_for_schema,
    response_for_relationship, request_for_relationship,
)
from starlette_jsonapi.resource import BaseResource, BaseRelationshipResource
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema

from accounts.exceptions import TeamNotFound, UserNotFound
from accounts.models import User, Team

logger = logging.getLogger(__name__)


class TeamSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    name = fields.Str(required=True)

    users = JSONAPIRelationship(
        type_='users',
        schema='UserSchema',
        many=True,
        required=True,
        self_route='teams:relationships-users',
        self_route_kwargs={'parent_id': '<id>'},
        related_resource='UsersResource',
        related_route='teams:users',
        related_route_kwargs={'id': '<id>'},
    )

    class Meta:
        type_ = 'teams'
        self_route = 'teams:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'teams:get_many'


class TeamsResource(BaseResource):
    type_ = 'teams'
    schema = TeamSchema
    id_mask = 'int'

    async def include_relations(self, obj: Team, relations: List[str]):
        """
        We override this to allow `included` requests against this resource,
        but we don't actually have to do anything here.
        The attribute is already populated because we're using plain NamedTuples.
        """
        return None

    @with_openapi_info(
        responses={
            '200': TeamSchema,
            '404': TeamNotFound,
        },
    )
    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        team = Team.get_item(id)
        if not team:
            raise TeamNotFound

        return await self.to_response(await self.serialize(data=team))

    @with_openapi_info(
        responses={
            '200': TeamSchema,
            '404': TeamNotFound,
        },
    )
    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        team = Team.get_item(id)
        if not team:
            raise TeamNotFound

        json_body = await self.deserialize_body(partial=True)
        name = json_body.get('name')
        if name:
            team.name = name

        user_ids = json_body.get('users')
        if user_ids:
            users = []
            for user_id in user_ids:
                user = User.get_item(int(user_id))
                if not user:
                    raise UserNotFound
                users.append(user)
            team.users = users

        team.save()

        return await self.to_response(await self.serialize(data=team))

    @with_openapi_info(
        responses={
            '204': {'description': 'The resource was deleted successfully.'},
            '404': TeamNotFound,
        },
    )
    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        team = Team.get_item(id)
        if not team:
            raise TeamNotFound

        team.delete()

        return JSONAPIResponse(status_code=204)

    @with_openapi_info(
        responses={'200': TeamSchema(many=True)},
    )
    async def get_many(self, *args, **kwargs) -> Response:
        teams = Team.get_items()
        return await self.to_response(await self.serialize(data=teams, many=True))

    @with_openapi_info(
        responses={'201': TeamSchema},
    )
    async def post(self, *args, **kwargs) -> Response:
        json_body = await self.deserialize_body()

        team = Team()
        name = json_body.get('name')
        if name:
            team.name = name

        user_ids = json_body['users']
        users = []
        for user_id in user_ids:
            user = User.get_item(int(user_id))
            if not user:
                raise UserNotFound
            users.append(user)
        team.users = users

        team.save()

        result = await self.serialize(data=team)
        return await self.to_response(result, status_code=201)

    @with_openapi_info(
        responses={
            '200': 'UserSchema',
            '404': TeamNotFound,
        },
    )
    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        team = Team.get_item(id)
        if not team:
            raise TeamNotFound
        if relationship == 'users':
            if not related_id:
                return await self.to_response(await self.serialize_related(team.users, many=True))
            else:
                filtered_users = list(filter(lambda user: user.id == related_id, team.users))
                if len(filtered_users) == 1:
                    return await self.to_response(await self.serialize_related(filtered_users[0]))
        raise HTTPException(status_code=404)


class TeamUsersResource(BaseRelationshipResource):
    parent_resource = TeamsResource
    relationship_name = 'users'

    @with_openapi_info(
        responses={'200': response_for_relationship(parent_resource.schema, relationship_name)},
    )
    async def get(self, parent_id: str, *args, **kwargs) -> Response:
        team = Team.get_item(int(parent_id))
        if not team:
            raise TeamNotFound
        return await self.to_response(await self.serialize(data=team))

    @with_openapi_info(
        responses={'200': response_for_relationship(parent_resource.schema, relationship_name)},
        request_body=request_for_relationship(parent_resource.schema, relationship_name),
    )
    async def patch(self, parent_id: str, *args, **kwargs) -> Response:
        team = Team.get_item(int(parent_id))
        if not team:
            raise TeamNotFound

        user_ids = await self.deserialize_ids()
        if not user_ids:
            users = []
        else:
            users = []
            for user_id in user_ids:
                user = User.get_item(int(user_id))
                if not user:
                    raise UserNotFound
                users.append(user)
        team.users = users
        team.save()
        return await self.to_response(await self.serialize(data=team))

    @with_openapi_info(
        responses={'200': response_for_relationship(parent_resource.schema, relationship_name)},
        request_body=request_for_relationship(parent_resource.schema, relationship_name),
    )
    async def post(self, parent_id: str, *args, **kwargs) -> Response:
        team = Team.get_item(int(parent_id))
        if not team:
            raise TeamNotFound

        user_ids = await self.deserialize_ids()
        if not user_ids:
            users = []
        else:
            users = team.users
            for user_id in user_ids:
                user = User.get_item(int(user_id))
                if not user:
                    raise UserNotFound
                users.append(user)
        team.users = users
        team.save()
        return await self.to_response(await self.serialize(data=team))

    @with_openapi_info(
        responses={'200': response_for_relationship(parent_resource.schema, relationship_name)},
        request_body=request_for_relationship(parent_resource.schema, relationship_name),
    )
    async def delete(self, parent_id: str, *args, **kwargs) -> Response:
        team = Team.get_item(int(parent_id))
        if not team:
            raise TeamNotFound
        user_ids = await self.deserialize_ids()
        if not user_ids:
            user_ids = []
        users = []
        for user in team.users:
            if str(user.id) not in user_ids:
                users.append(user)
        team.users = users
        team.save()
        return await self.to_response(await self.serialize(data=team))
