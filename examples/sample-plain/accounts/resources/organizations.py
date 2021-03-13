from marshmallow_jsonapi import fields
from starlette.responses import Response

from starlette_jsonapi.openapi import with_openapi_info
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.schema import JSONAPISchema

from accounts.exceptions import OrganizationNotFound
from accounts.models import Organization
from accounts.pagination import PageNumberPagination


class OrganizationSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    name = fields.Str(required=True)
    contact_url = fields.Str()
    contact_phone = fields.Str()

    class Meta:
        type_ = 'organizations'
        self_route = 'organizations:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'organizations:get_many'


class OrganizationsResource(BaseResource):
    type_ = 'organizations'
    schema = OrganizationSchema
    id_mask = 'int'
    pagination_class = PageNumberPagination

    @with_openapi_info(
        responses={
            '200': 'OrganizationSchema',
            '404': OrganizationNotFound,
        },
    )
    async def get(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        organization = Organization.get_item(id)
        if not organization:
            raise OrganizationNotFound

        return await self.to_response(await self.serialize(data=organization))

    @with_openapi_info(
        responses={
            '200': 'OrganizationSchema',
            '404': OrganizationNotFound,
        },
        request_body=OrganizationSchema,
    )
    async def patch(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        organization = Organization.get_item(id)
        if not organization:
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

        organization.save()

        return await self.to_response(await self.serialize(data=organization))

    @with_openapi_info(
        responses={
            '204': {'description': 'The resource was deleted successfully.'},
            '404': OrganizationNotFound,
        },
        request_body=OrganizationSchema,
    )
    async def delete(self, id=None, *args, **kwargs) -> Response:
        if not id:
            raise OrganizationNotFound
        organization = Organization.get_item(id)
        if not organization:
            raise OrganizationNotFound

        organization.delete()

        return JSONAPIResponse(status_code=204)

    @with_openapi_info(
        responses={'200': OrganizationSchema(many=True)},
    )
    async def get_many(self, *args, **kwargs) -> Response:
        organizations = Organization.get_items()
        return await self.to_response(await self.serialize(data=organizations, many=True, paginate=True))

    @with_openapi_info(
        responses={'201': 'OrganizationSchema'},
    )
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

        organization.save()

        response = await self.serialize(data=organization)
        return await self.to_response(response, status_code=201)
