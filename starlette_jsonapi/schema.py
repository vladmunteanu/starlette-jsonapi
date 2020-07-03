from marshmallow import EXCLUDE
from marshmallow_jsonapi import Schema as __Schema, SchemaOpts as __SchemaOpts
from starlette.applications import Starlette


class BaseSchemaOpts(__SchemaOpts):
    """ An adaptation of marshmallow-jsonapi Flask SchemaOpts for use with Starlette. """
    def __init__(self, meta, *args, **kwargs):
        if getattr(meta, 'self_url', None):
            raise ValueError(
                'Use `self_route` instead of `self_url` when using the Starlette extension.'
            )
        if getattr(meta, 'self_url_kwargs', None):
            raise ValueError(
                'Use `self_route_kwargs` instead of `self_url_kwargs` when using the Starlette extension.'
            )
        if getattr(meta, 'self_url_many', None):
            raise ValueError(
                'Use `self_route_many` instead of `self_url_many` when using the Starlette extension.'
            )

        if (
            getattr(meta, 'self_route_kwargs', None)
            and not getattr(meta, 'self_route', None)
        ):
            raise ValueError(
                'Must specify `self_route` Meta option when `self_route_kwargs` is specified.'
            )

        # Transfer Starlette options to URL options
        meta.self_url = getattr(meta, 'self_route', None)
        meta.self_url_kwargs = getattr(meta, 'self_route_kwargs', None)
        meta.self_url_many = getattr(meta, 'self_route_many', None)

        super().__init__(meta, *args, **kwargs)
        self.unknown = getattr(meta, 'unknown', EXCLUDE)


class JSONAPISchema(__Schema):
    OPTIONS_CLASS = BaseSchemaOpts

    class Meta:
        """
        Options object that takes the same options as `marshmallow-jsonapi.Schema`,
        but instead of ``self_url``, ``self_url_kwargs`` and ``self_url_many``
        has the following options to resolve the URLs from Starlette route names:

        * ``self_route`` - Route name to resolve the self URL link from.
        * ``self_route_kwargs`` - Replacement fields for ``self_route``. String
          attributes enclosed in ``< >`` will be interpreted as attributes to
          pull from the schema data.
        * ``self_route_many`` - Route name to resolve the self URL link when a
          collection of resources is returned.
        """
        pass

    def __init__(self, *args, **kwargs):
        self.app = kwargs.pop('app', None)  # type: Starlette
        super().__init__(*args, **kwargs)

    def generate_url(self, link, **kwargs):
        if self.app and isinstance(self.app, Starlette) and link:
            return self.app.url_path_for(link, **kwargs)
        return None

    def get_resource_links(self, item):
        """ Override the marshmallow-jsonapi implementation to check for None links. """
        links = super().get_resource_links(item)
        if links and isinstance(links, dict) and links.get('self'):
            return links
        return None
