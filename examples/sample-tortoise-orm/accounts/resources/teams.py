import logging
from typing import List, Any

from marshmallow_jsonapi import fields
from starlette.exceptions import HTTPException
from starlette.responses import Response
from tortoise.exceptions import DoesNotExist

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
        self_route_many = 'teams:get_all'


class TeamsResource(BaseResource):
    type_ = 'teams'
    schema = TeamSchema
    id_mask = 'int'

    async def prepare_relations(self, obj: Team, relations: List[str]):
        """
        We override this to allow `included` requests against this resource.
        """
        if 'users' in relations:
            await obj.fetch_related('users')

    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        try:
            team = await Team.get(id=id).prefetch_related('users')
        except DoesNotExist:
            raise TeamNotFound

        return await self.to_response(await self.serialize(data=team))

    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        try:
            team = await Team.get(id=id).prefetch_related('users')
        except DoesNotExist:
            raise TeamNotFound

        json_body = await self.deserialize_body(partial=True)
        name = json_body.get('name')
        if name:
            team.name = name

        user_ids = json_body.get('users')
        if user_ids:
            await team.users.clear()
            users = []
            for user_id in user_ids:
                try:
                    user = await User.get(id=int(user_id))
                except DoesNotExist:
                    raise UserNotFound
                users.append(user)
            await team.users.add(*users)

        await team.save()

        return await self.to_response(await self.serialize(data=team))

    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise TeamNotFound
        try:
            team = await Team.get(id=id)
        except DoesNotExist:
            raise TeamNotFound

        await team.delete()

        return JSONAPIResponse(status_code=204)

    async def get_all(self, *args, **kwargs) -> Response:
        teams = await Team.all().prefetch_related('users')
        return await self.to_response(await self.serialize(data=teams, many=True))

    async def post(self, *args, **kwargs) -> Response:
        json_body = await self.deserialize_body()

        name = json_body.get('name')
        user_ids = json_body['users']
        users = []
        for user_id in user_ids:
            try:
                user = await User.get(id=int(user_id))
            except DoesNotExist:
                raise UserNotFound
            users.append(user)

        team = await Team.create(name=name)
        await team.fetch_related('users')
        await team.users.add(*users)
        await team.save()

        await team.fetch_related('users')
        result = await self.serialize(data=team)
        return await self.to_response(result, status_code=201)

    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        try:
            team = await Team.get(id=id).prefetch_related('users')
        except DoesNotExist:
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

    async def get(self, parent_id: str, *args, **kwargs) -> Response:
        try:
            team = await Team.get(id=int(parent_id)).prefetch_related('users')
        except DoesNotExist:
            raise TeamNotFound
        return await self.to_response(await self.serialize(data=team))

    async def patch(self, parent_id: str, *args, **kwargs) -> Response:
        """ replacing users """
        try:
            team = await Team.get(id=int(parent_id)).prefetch_related('users')
        except DoesNotExist:
            raise TeamNotFound

        user_ids = await self.deserialize_ids() or []
        users = []
        for user_id in user_ids:
            try:
                user = await User.get(id=int(user_id))
            except DoesNotExist:
                raise UserNotFound
            users.append(user)
        await team.users.clear()
        await team.users.add(*users)
        await team.save()
        return await self.to_response(await self.serialize(data=team))

    async def post(self, parent_id: str, *args, **kwargs) -> Response:
        """ associating with specific users """
        try:
            team = await Team.get(id=int(parent_id)).prefetch_related('users')
        except DoesNotExist:
            raise TeamNotFound

        user_ids = await self.deserialize_ids() or []
        users = []
        for user_id in user_ids:
            try:
                user = await User.get(id=int(user_id))
            except DoesNotExist:
                raise UserNotFound
            users.append(user)
        await team.users.add(*users)
        await team.save()
        return await self.to_response(await self.serialize(data=team))

    async def delete(self, parent_id: str, *args, **kwargs) -> Response:
        """ deleting association with specific users """
        try:
            team = await Team.get(id=int(parent_id)).prefetch_related('users')
        except DoesNotExist:
            raise TeamNotFound
        user_ids = await self.deserialize_ids()
        if not user_ids:
            user_ids = []
        users = []
        for user_id in user_ids:
            try:
                user = await User.get(id=int(user_id))
            except DoesNotExist:
                raise UserNotFound
            users.append(user)
        await team.users.remove(*users)
        await team.save()
        return await self.to_response(await self.serialize(data=team))
