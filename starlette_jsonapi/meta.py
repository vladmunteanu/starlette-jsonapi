
# map of resource class name to class
registered_resources = {}


class MetaRegisterResource(type):
    def __new__(mcs, name, bases, attrs):
        klass = super().__new__(mcs, name, bases, attrs)
        if attrs.get('register_resource', True):
            registered_resources[name] = klass
        return klass
