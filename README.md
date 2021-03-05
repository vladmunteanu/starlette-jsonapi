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
`pip install starlette-jsonapi`

Since this project is under development, please pin your dependencies to avoid problems.

### Features
- 100% tests coverage
- basic json:api serialization
- including related resources
- starlette friendly route generation
- exception handlers to serialize as json:api responses
- relationship resources
- sparse fields
- support for client generated IDs
- support top level meta objects
- [pagination helpers](https://jsonapi.org/format/#fetching-pagination)

### Todo:
- [sorting helpers](https://jsonapi.org/format/#fetching-sorting)
- examples for other ORMs
- [support jsonapi objects](https://jsonapi.org/format/#document-jsonapi-object)
- [enforce member name validation](https://jsonapi.org/format/#document-member-names)
- [optionally enforce query name validation](https://jsonapi.org/format/#query-parameters)

## Documentation
Available on [Read The Docs](https://starlette-jsonapi.readthedocs.io/)

You should take a look at the [examples](examples) directory for full implementations.

To generate documentation files locally, you should create a virtualenv,
then activate it and install the requirements:
```shell
cd docs
pip install -r requirements.txt
```

With the docs virtualenv activated, you can then run `make html` to generate the HTML files.

The result will be written to `docs/build`, and you can open `docs/build/html/index.html` in your browser of choice
to view the pages.

## Contributing
This project is in its early days, so **any** help is appreciated.

### Running tests:
As simple as running ```tox```.

If you plan to use pyenv and want to run tox for multiple python versions,
you can create multiple virtual environments and then make them available to tox by running
something like: `pyenv shell starlette_jsonapi_venv36 starlette_jsonapi_venv37 starlette_jsonapi_venv38 starlette_jsonapi_venv39`.
