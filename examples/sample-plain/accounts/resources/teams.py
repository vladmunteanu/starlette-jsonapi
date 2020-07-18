import logging
from typing import List

from marshmallow_jsonapi import fields
from starlette.responses import Response

from starlette_jsonapi.fields import JSONAPIRelationship
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
        include_resource_linkage=True,
        many=True,
        required=True,
    )

    class Meta:
        type_ = 'teams'
        self_route = 'teams:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'teams:get_all'


class TeamsResource(BaseResource):
    type_ = 'teams'
    schema = TeamSchema
    id_mask = 'int'

    async def prepare_relations(self, obj: Team, relations: List[str]):
        """
        We override this to allow `included` requests against this resource,
        but we don't actually have to do anything here.
        The attribute is already populated because we're using plain NamedTuples.
        """
        return None

    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        team = Team.get_item(id)
        if not team:
            raise TeamNotFound

        return await self.to_response(await self.serialize(data=team))

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

    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        team = Team.get_item(id)
        if not team:
            raise TeamNotFound

        team.delete()

        return JSONAPIResponse(status_code=204)

    async def get_all(self, *args, **kwargs) -> Response:
        teams = Team.get_items()
        return await self.to_response(await self.serialize(data=teams, many=True))

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


class TeamUsersResource(BaseRelationshipResource):
    parent_resource = TeamsResource
    relationship_name = 'users'

    async def get(self, parent_id: str, *args, **kwargs) -> Response:
        team = Team.get_item(int(parent_id))
        if not team:
            raise TeamNotFound
        return await self.to_response(await self.serialize(data=team))

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
