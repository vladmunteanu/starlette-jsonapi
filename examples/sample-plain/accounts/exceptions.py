from starlette_jsonapi.exceptions import ResourceNotFound


class OrganizationNotFound(ResourceNotFound):
    detail = 'Organization not found.'


class UserNotFound(ResourceNotFound):
    detail = 'User not found.'
