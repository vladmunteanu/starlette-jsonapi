from marshmallow_jsonapi.fields import Relationship as __BaseRelationship
from marshmallow_jsonapi.utils import resolve_params
from starlette.applications import Starlette


class JSONAPIRelationship(__BaseRelationship):
    """
    Mostly marshmallow_jsonapi.fields.Relationship, but friendlier with async ORMs.
    Accepts the `id_attribute` attribute which should point to the id field corresponding to this relationship.
    In most cases, this attribute is available even if the relationship is not loaded.
    """

    def __init__(
        self,
        id_attribute=None,
        related_route=None,
        related_route_kwargs=None,
        *,
        self_route=None,
        self_route_kwargs=None,
        **kwargs
    ):
        self.id_attribute = id_attribute
        self.related_route = related_route
        self.related_route_kwargs = related_route_kwargs or {}
        self.self_route = self_route
        self.self_route_kwargs = self_route_kwargs or {}
        # When doing a PATCH on a relationship, `data` is allowed to be None
        # if the client wishes to empty a relation.
        kwargs.update(allow_none=kwargs.get('allow_none', True))
        super().__init__(**kwargs)

    # We override serialize because we want to allow asynchronous ORMs to do serialization
    # with an `id_attribute` that is available even if the relationship isn't loaded.
    def serialize(self, attr, obj, accessor=None):
        if self.include_resource_linkage or self.include_data:
            if self.include_data:
                return super().serialize(attr, obj, accessor)
            id_attr = self.id_attribute if self.id_attribute is not None else attr
            return super().serialize(id_attr, obj, accessor)
        return self._serialize(None, attr, obj)

    def get_url(self, obj, route_name, **kwargs):
        if route_name and self.parent and self.parent.app and isinstance(self.parent.app, Starlette):
            kwargs = resolve_params(obj, kwargs, default=self.default)
            return self.parent.app.url_path_for(route_name, **kwargs)
        return None

    def get_related_url(self, obj):
        return self.get_url(obj, self.related_route, **self.related_route_kwargs)

    def get_self_url(self, obj):
        return self.get_url(obj, self.self_route, **self.self_route_kwargs)
