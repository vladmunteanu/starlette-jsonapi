import inspect

from starlette_jsonapi.constants import OPENAPI_INFO
from starlette_jsonapi.utils import safe_merge

# map of resource class name to class
registered_resources = {}


class OpenAPIInfoMeta(type):
    def __new__(mcs, name, bases, attrs):
        klass = super().__new__(mcs, name, bases, attrs)
        base_openapi_info = {'handlers': {}}  # type: dict
        for base_cls in bases:
            if hasattr(base_cls, OPENAPI_INFO):
                base_openapi_info = safe_merge(base_openapi_info, getattr(base_cls, OPENAPI_INFO))
        if OPENAPI_INFO in attrs:
            base_openapi_info = safe_merge(base_openapi_info, attrs[OPENAPI_INFO])
        for attr_name, attr_value in attrs.items():
            if (
                attr_name in ('get', 'patch', 'delete', 'post', 'get_many', 'get_related')
                and inspect.isfunction(attr_value)
            ):
                func_openapi_info = getattr(attr_value, OPENAPI_INFO, {})
                func_openapi_info_from_base = base_openapi_info['handlers'].get(attr_name, {})
                func_openapi_info_from_base = safe_merge(func_openapi_info_from_base, func_openapi_info)
                setattr(attr_value, OPENAPI_INFO, func_openapi_info_from_base)
        return klass


class RegisteredResourceMeta(OpenAPIInfoMeta):
    """
    Registers resource classes in a dictionary, to make them accessible
    dynamically through the class name.

    Classes are registered by default, unless ``register_resource = False``
    is specified at the class level.
    """
    def __new__(mcs, name, bases, attrs):
        klass = super().__new__(mcs, name, bases, attrs)

        # we register classes by default, unless `register_resource = False` is specified at the class level
        if attrs.get('register_resource', True):
            registered_resources[name] = klass
        return klass
