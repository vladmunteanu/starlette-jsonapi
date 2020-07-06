# starlette_jsonapi
A minimal "framework" intended to help write [json:api](https://jsonapi.org) compliant services in async Python,
written on top of [starlette](https://starlette.io) and [marshmallow-jsonapi](https://marshmallow-jsonapi.readthedocs.io/).

In the maintainer's view, REST frameworks that come with a complete data layer implementation are quite limiting 
and rarely usable in production systems due to business logic needs or authorization constraints. 
The default implementation they come with is usually getting in the way, more than helping.

Because of that, `starlette_jsonapi` does not contain a data layer implementation, so you should be able to pick 
any available async ORM. This also means that you are going to get a very basic interface for writing a REST resource, 
with some helpers to make your experience more pleasant, but nothing fancy.

##### Installing
`pip install starlette-jsonapi==0.1.1`

Since this project is under development, please pin your dependencies to avoid problems.

### Features
- 100% tests coverage
- basic json:api serialization
- including related resources
- starlette friendly route generation
- exception handlers to serialize as json:api responses
- relationship resources 
- sparse fields

### Todo:
- pagination helpers
- sorting helpers
- documentation
- examples for other ORMs

## Documentation
You should take a look at the [examples](examples) directory for implementations.

### Defining a schema
After you've decided which ORM to use, you can start writing the associated schemas
using the marshmallow_jsonapi library (which itself is extending [marshmallow](https://marshmallow.readthedocs.io/)).  

```python
from marshmallow_jsonapi import fields
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.schema import JSONAPISchema

class ExampleSchema(JSONAPISchema):
    class Meta:
        type_ = 'examples'

    id = fields.Str(dump_only=True)
    some_optional_field = fields.Str()
    some_required_field = fields.Str(required=True)

class ChildExampleSchema(JSONAPISchema):
    class Meta:
        type_ = 'examples'

    id = fields.Str(dump_only=True)
    name = fields.Str()
    
    parent = JSONAPIRelationship(
        type_='examples',
        schema='ExampleSchema',
        include_resource_linkage=True,
        required=True,
        # `id_attribute` can be specified in order to allow serializing 
        # relationships even when the related object is not available. 
        # See the `sample-tortoise-orm` example for more information.
    )
```

You can also generate the associated `links` object by specifying more options in the Meta class of a schema:
```python
from marshmallow_jsonapi import fields
from starlette_jsonapi.schema import JSONAPISchema

class SomeSchema(JSONAPISchema):
    id = fields.Str(dump_only=True)
    name = fields.Str()

    class Meta:
        type_='some-resource'
        self_route = 'some-resource:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'some-resource:get_all'
```

### Defining a resource

Once the schema is defined, we can add the associated resource class and link them by setting the `schema` attribute
on the resource class.

Resources are implemented by subclassing `starlette_jsonapi.resource.BaseResource`.
A json:api compliant service will implement GET, POST, PATCH, DELETE HTTP methods on a resource,
so the `BaseResource` comes with 5 methods that you can override:
- `get -> handling GET /<id>`
- `patch -> handling PATCH /<id>`
- `delete -> handling DELETE /<id>`
- `get_all -> handling GET /`
- `post -> handling POST /`

All methods return 405 Method Not Allowed by default.
You can also customize `allowed_methods` to a subset of the above HTTP methods.

Additionally, the `prepare_relations` method is available for enabling inclusion of related resources.
Since the json:api specification does not enforce this, the default implementation will skip inclusion
in order to avoid data leaks.

Example:
```python
from starlette_jsonapi.resource import BaseResource
from starlette_jsonapi.responses import JSONAPIResponse
from starlette_jsonapi.exceptions import ResourceNotFound

examples_db = {}
last_id = 0

class ExampleResource(BaseResource):
    type_ = 'examples'
    schema = ExampleSchema

    async def get(self, id=None, *args, **kwargs):
        example = examples_db.get(id)
        if not example:
            raise ResourceNotFound
        return await self.serialize(example)
    
    async def patch(self, id=None, *args, **kwargs):
        example = examples_db.get(id)
        if not example:
            raise ResourceNotFound
        
        body = await self.deserialize_body(partial=True)
        if body.get('some_optional_field'):
            example['some_optional_field'] = body.get('some_optional_field')
        if body.get('some_required_field'):
            example['some_required_field'] = body.get('some_required_field')

        return await self.serialize(example)

    async def delete(self, id=None, *args, **kwargs):
        example = examples_db.pop(id, None)
        if not example:
            raise ResourceNotFound
        return JSONAPIResponse(status_code=204)

    async def get_all(self, *args, **kwargs):
        examples = list(examples_db.values())
        return self.serialize(examples, many=True) 
    
    async def post(self, *args, **kwargs):
        global last_id
        body = await self.deserialize_body()
        last_id += 1
        example = {'id': last_id}
        if body.get('some_optional_field'):
            example['some_optional_field'] = body.get('some_optional_field')
        
        # We didn't ask for a partial deserialization, so a required field shouldn't throw a KeyError
        example['some_required_field'] = body['some_required_field']
        examples_db[example['id']] = example

        return await self.serialize(example)
```

### Defining a relationship resource
You can choose to define a relationship resource by subclassing `starlette_jsonapi.resource.BaseRelationshipResource`.

A json:api compliant service might implement GET, POST, PATCH, DELETE HTTP methods on a relationship resource,
so the `BaseRelationshipResource` comes with 4 methods that you can override:
- `get -> handling GET /<parent_type>/<parent_id>/relationships/<relationship_name>`
- `patch -> handling PATCH /<parent_type>/<parent_id>/relationships/<relationship_name>`
- `delete -> handling DELETE /<parent_type>/<parent_id>/relationships/<relationship_name>`
- `post -> handling POST /<parent_type>/<parent_id>/relationships/<relationship_name>`

All methods return 405 Method Not Allowed by default.
You can also customize `allowed_methods` to a subset of the above HTTP methods.

When defining a relationship resource, the following class attributes must be set:
- `parent_resource` -> must point to the BaseResource subclass that is exposing the parent resource
- `relationship_name` -> must contain the relationship name, as found on `parent_resource.schema`

Example:
```python
from marshmallow_jsonapi import fields
from starlette.applications import Starlette
from starlette_jsonapi.fields import JSONAPIRelationship
from starlette_jsonapi.resource import BaseRelationshipResource, BaseResource
from starlette_jsonapi.schema import JSONAPISchema

class EmployeeSchema(JSONAPISchema):
    class Meta:
        type_ = 'employees'
        self_route = 'employees:get'
        self_route_kwargs = {'id': '<id>'}
        self_route_many = 'employees:get_all'

    id = fields.Str(dump_only=True)
    name = fields.Str()

    manager = JSONAPIRelationship(
        type_='employees',
        schema='EmployeeSchema',
        include_resource_linkage=True,
        self_route='employees:manager',
        self_route_kwargs={'parent_id': '<id>'},
        related_route='employees:get',
        related_route_kwargs={'id': '<id>'},
    )


class EmployeeResource(BaseResource):
    type_ = 'employees'
    schema = EmployeeSchema    


class EmployeeManagerResource(BaseRelationshipResource):
    parent_resource = EmployeeResource
    relationship_name = 'manager'


app = Starlette()
EmployeeResource.register_routes(app=app, base_path='/')
EmployeeManagerResource.register_routes(app=app)
```

#### Registering resource paths
To register a defined resource class, we need to add the appropriate paths to the Starlette app.
Considering the ExampleResource implementation above, it's as simple as:
```python
from starlette.applications import Starlette

app = Starlette()
ExampleResource.register_routes(app=app, base_path='/api/')
```

This will add the following routes to the Starlette application:
- GET `/api/examples/`
- POST `/api/examples/`
- GET `/api/examples/{id:str}`
- PATCH `/api/examples/{id:str}`
- DELETE `/api/examples/{id:str}`

You can also customize the registered Mount name by specifying `register_as` on the resource class.
```python
from starlette.applications import Starlette
from starlette_jsonapi.resource import BaseResource

class ExampleResourceV2(BaseResource):
    type_ = 'examples'
    register_as = 'v2-examples'

app = Starlette()
ExampleResourceV2.register_routes(app=app, base_path='/api/v2')

assert app.url_path_for('v2-examples:get_all') == '/api/v2/examples/'
assert app.url_path_for('v2-examples:post') == '/api/v2/examples/'
assert app.url_path_for('v2-examples:get', id='foo') == '/api/v2/examples/foo'
assert app.url_path_for('v2-examples:patch', id='foo') == '/api/v2/examples/foo'
assert app.url_path_for('v2-examples:delete', id='foo') == '/api/v2/examples/foo'
```
Which will cause the routes to be registered:
- GET `/api/v2/examples/`
- POST `/api/v2/examples/`
- GET `/api/v2/examples/{id:str}`
- PATCH `/api/v2/examples/{id:str}`
- DELETE `/api/v2/examples/{id:str}`


#### Accessing the request
While handling a request inside a resource, you can use `self.request` to access the Starlette Request object.

#### Accessing the request body
Although directly accessible from `self.request`, you should probably use `self.deserialize_body`
to raise any validation errors as 400 HTTP responses, while benefiting from a cleaner payload.

## Contributing
This project is in its early days, so **any** help is appreciated.

### Running tests:
As simple as running ```tox```.

If you plan to use pyenv and want to run tox for multiple python versions, 
you can create multiple virtual environments and then make them available to tox by running 
something like: `pyenv shell starlette_jsonapi_venv36 starlette_jsonapi_venv37`.
