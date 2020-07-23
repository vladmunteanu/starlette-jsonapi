from typing import Dict

from marshmallow import EXCLUDE
from marshmallow.fields import Field
from marshmallow_jsonapi import Schema as __Schema, SchemaOpts as __SchemaOpts
from marshmallow_jsonapi.utils import resolve_params
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
        # allow changing links through self_related_route, self_related_route_kwargs
        self.self_related_route = kwargs.pop('self_related_route', None)
        self.self_related_route_kwargs = kwargs.pop('self_related_route_kwargs', None)

        super().__init__(*args, **kwargs)

    def generate_url(self, link, **kwargs):
        if self.app and isinstance(self.app, Starlette) and link:
            return self.app.url_path_for(link, **kwargs)
        return None

    def get_top_level_links(self, data, many):
        """ Overriding base implementation to support serialization as a related resource. """
        self_link = None
        if self.self_related_route:
            if many:
                kwargs = self.self_related_route_kwargs
            else:
                kwargs = resolve_params(data, self.self_related_route_kwargs)
            self_link = self.generate_url(self.self_related_route, **kwargs)
        if self_link:
            return {"self": self_link}
        return super().get_top_level_links(data, many)

    def get_resource_links(self, item):
        """ Override the marshmallow-jsonapi implementation to check for None links. """
        links = super().get_resource_links(item)
        if links and isinstance(links, dict) and links.get('self'):
            return links
        return None

    @classmethod
    def get_fields(cls) -> Dict[str, Field]:
        return cls._declared_fields
