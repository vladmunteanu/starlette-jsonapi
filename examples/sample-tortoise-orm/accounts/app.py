from starlette.applications import Starlette
from tortoise.contrib.starlette import register_tortoise

from starlette_jsonapi.utils import register_jsonapi_exception_handlers

app = Starlette()


def create_app():
    register_tortoise(
        app,
        db_url='sqlite://:memory:',
        modules={"models": ["accounts.models"]},
        generate_schemas=True,
    )

    # register exception handlers
    register_jsonapi_exception_handlers(app)

    # register routes
    from accounts.resources import users, organizations, teams
    users.UsersResource.register_routes(app, '/api')
    organizations.OrganizationsResource.register_routes(app, '/api')
    teams.TeamsResource.register_routes(app, '/api')
    teams.TeamUsersResource.register_routes(app)
    return app
