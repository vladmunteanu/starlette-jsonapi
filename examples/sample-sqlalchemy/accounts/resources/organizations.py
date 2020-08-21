from marshmallow_jsonapi import fields
from starlette.responses import Response
from sqlalchemy.orm.exc import NoResultFound

from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema

from accounts.decorators import with_sqlalchemy_session
from accounts.exceptions import OrganizationNotFound
from accounts.models import Organization


class OrganizationSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    name = fields.Str(required=True)
    contact_url = fields.Str()
    contact_phone = fields.Str()

    class Meta:
        type_ = 'organizations'
        self_route = 'organizations:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'organizations:get_all'


class OrganizationsResource(BaseResource):
    type_ = 'organizations'
    schema = OrganizationSchema
    id_mask = 'int'

    @with_sqlalchemy_session
    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        try:
            organization = self.db_session.query(Organization).filter_by(id=id).one()
        except NoResultFound:
            raise OrganizationNotFound

        return await self.to_response(await self.serialize(data=organization))

    @with_sqlalchemy_session
    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        try:
            organization = self.db_session.query(Organization).filter_by(id=id).one()
        except NoResultFound:
            raise OrganizationNotFound

        json_body = await self.deserialize_body(partial=True)
        name = json_body.get('name')
        if name:
            organization.name = name
        contact_phone = json_body.get('contact_phone')
        if contact_phone:
            organization.contact_phone = contact_phone
        contact_url = json_body.get('contact_url')
        if contact_url:
            organization.contact_url = contact_url

        self.db_session.add(organization)
        self.db_session.commit()

        return await self.to_response(await self.serialize(data=organization))

    @with_sqlalchemy_session
    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        try:
            organization = self.db_session.query(Organization).filter_by(id=id).one()
        except NoResultFound:
            raise OrganizationNotFound

        self.db_session.delete(organization)
        self.db_session.commit()

        return JSONAPIResponse(status_code=204)

    @with_sqlalchemy_session
    async def get_all(self, *args, **kwargs) -> Response:
        organizations = self.db_session.query(Organization).all()
        return await self.to_response(await self.serialize(data=organizations, many=True))

    @with_sqlalchemy_session
    async def post(self, *args, **kwargs) -> Response:
        json_body = await self.deserialize_body()
        organization = Organization()
        name = json_body.get('name')
        if name:
            organization.name = name
        contact_phone = json_body.get('contact_phone')
        if contact_phone:
            organization.contact_phone = contact_phone
        contact_url = json_body.get('contact_url')
        if contact_url:
            organization.contact_url = contact_url

        self.db_session.add(organization)
        self.db_session.commit()

        response = await self.serialize(data=organization)
        return await self.to_response(response, status_code=201)
