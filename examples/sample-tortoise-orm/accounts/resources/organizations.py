from marshmallow_jsonapi import fields
from starlette.responses import JSONResponse, Response
from tortoise.exceptions import DoesNotExist

from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.schema import JSONAPISchema

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

    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        try:
            organization = await Organization.get(id=id)
        except DoesNotExist:
            raise OrganizationNotFound

        return await self.to_response(await self.serialize(data=organization))

    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        try:
            organization = await Organization.get(id=id)
        except DoesNotExist:
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

        await organization.save()

        return await self.to_response(await self.serialize(data=organization))

    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        try:
            organization = await Organization.get(id=id)
        except DoesNotExist:
            raise OrganizationNotFound

        await organization.delete()

        return JSONResponse(status_code=204)

    async def get_all(self, *args, **kwargs) -> Response:
        organizations = await Organization.all()
        return await self.to_response(await self.serialize(data=organizations, many=True))

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

        await organization.save()

        response = await self.serialize(data=organization)
        return await self.to_response(response, status_code=201)
