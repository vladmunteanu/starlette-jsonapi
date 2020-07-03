import pytest
from marshmallow import class_registry
from starlette.applications import Starlette


@pytest.fixture()
def cleanup_marshmallow_registry():
    yield
    class_registry._registry.clear()  # noqa


@pytest.fixture()
def app():
    app = Starlette()
    return app
