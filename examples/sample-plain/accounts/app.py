from starlette.applications import Starlette
from apispec import APISpec

from starlette_jsonapi.utils import register_jsonapi_exception_handlers
from starlette_jsonapi.openapi import (
    JSONAPISchemaGenerator, JSONAPIMarshmallowPlugin,
)

app = Starlette()


def create_app():
    schemas = JSONAPISchemaGenerator(
        APISpec(
            title='Accounts Management API',
            version='1.0',
            openapi_version='3.0.3',
            info={'description': 'An example API for managing accounts.'},
            plugins=[JSONAPIMarshmallowPlugin()],
        )
    )

    # register exception handlers
    register_jsonapi_exception_handlers(app)

    # register routes
    from accounts.resources import users, organizations, teams
    users.UsersResource.register_routes(app, '/api')
    organizations.OrganizationsResource.register_routes(app, '/api')
    teams.TeamsResource.register_routes(app, '/api')
    teams.TeamUsersResource.register_routes(app)

    def openapi_schema(request):
        import json
        from starlette.responses import Response
        schema_dict = schemas.get_schema(app.routes)
        return Response(
            json.dumps(schema_dict, indent=4),
            media_type='application/json',
        )

    app.add_route('/schema', route=openapi_schema, include_in_schema=False)
    return app
