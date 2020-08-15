
# map of resource class name to class
registered_resources = {}


class RegisteredResourceMeta(type):
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
