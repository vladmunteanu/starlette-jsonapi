from starlette.applications import Starlette
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from starlette_jsonapi.utils import register_jsonapi_exception_handlers

app = Starlette()
Session = sessionmaker()


def create_app():
    engine = create_engine('sqlite:///:memory:')
    Session.configure(bind=engine)
    from accounts.models import Base
    Base.metadata.create_all(engine)

    # register exception handlers
    register_jsonapi_exception_handlers(app)

    # register routes
    from accounts.resources import users, organizations, teams
    users.UsersResource.register_routes(app, '/api')
    organizations.OrganizationsResource.register_routes(app, '/api')
    teams.TeamsResource.register_routes(app, '/api')
    teams.TeamUsersResource.register_routes(app)

    return app
