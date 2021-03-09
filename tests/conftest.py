import pytest
from marshmallow import class_registry
from starlette.applications import Starlette

from starlette_jsonapi import meta, openapi


@pytest.fixture(autouse=True)
def cleanup_marshmallow_registry():
    yield
    class_registry._registry.clear()  # noqa


@pytest.fixture(autouse=True)
def cleanup_resources_registry():
    yield
    meta.registered_resources.clear()


@pytest.fixture(autouse=True)
def cleanup_preregistered_schemas():
    yield
    openapi.preregistered_schemas.clear()


@pytest.fixture()
def app():
    app = Starlette()
    return app
