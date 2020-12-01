import logging
from typing import List, Any

from marshmallow_jsonapi import fields
from starlette.exceptions import HTTPException
from starlette.responses import Response
from sqlalchemy.orm.exc import NoResultFound

from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema

from accounts.app import Session
from accounts.exceptions import UserNotFound
from accounts.models import User, Organization
from accounts.resources.base import BaseResourceSQLA

logger = logging.getLogger(__name__)


class UserSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    username = fields.Str(required=True)

    organization = JSONAPIRelationship(
        type_='organizations',
        schema='OrganizationSchema',
        include_resource_linkage=True,
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


class UsersResource(BaseResourceSQLA):
    type_ = 'users'
    schema = UserSchema
    id_mask = 'int'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = Session()

    async def prepare_relations(self, obj: User, relations: List[str]):
        """ We override this to allow include requests. """
        # sqlalchemy supports lazy loading of relationships,
        # so we don't need to load them manually,
        # as is generally the case with an async orm.
        return None

    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        try:
            user = self.db_session.query(User).filter_by(id=id).one()
        except NoResultFound:
            raise UserNotFound

        return await self.to_response(await self.serialize(data=user))

    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        try:
            user = self.db_session.query(User).filter_by(id=id).one()
        except NoResultFound:
            raise UserNotFound

        json_body = await self.deserialize_body(partial=True)
        username = json_body.get('username')
        if username:
            user.username = username

        organization_id = json_body.get('organization')
        if organization_id:
            try:
                organization = self.db_session.query(Organization).filter_by(id=organization_id).one()
                user.organization = organization
            except (NoResultFound, ValueError, TypeError):
                raise HTTPException(status_code=404, detail='Related Organization not found.')

        self.db_session.add(user)
        self.db_session.commit()

        return await self.to_response(await self.serialize(data=user))

    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise UserNotFound
        try:
            user = self.db_session.query(User).filter_by(id=id).one()
        except NoResultFound:
            raise UserNotFound

        self.db_session.delete(user)
        self.db_session.commit()

        return JSONAPIResponse(status_code=204)

    async def get_many(self, *args, **kwargs) -> Response:
        users = self.db_session.query(User).all()
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
            organization = self.db_session.query(Organization).filter_by(id=organization_id).one()
            user.organization = organization
        except (NoResultFound, ValueError, TypeError):
            raise HTTPException(status_code=404, detail='Related Organization not found.')

        self.db_session.add(user)
        self.db_session.commit()

        result = await self.serialize(data=user)
        return await self.to_response(result, status_code=201)

    async def get_related(self, id: Any, relationship: str, related_id: Any = None, *args, **kwargs) -> Response:
        try:
            user = self.db_session.query(User).filter_by(id=id).one()
        except NoResultFound:
            raise UserNotFound
        if relationship == 'organization' and related_id is None:
            return await self.to_response(await self.serialize_related(data=user.organization))
        raise HTTPException(status_code=404)
