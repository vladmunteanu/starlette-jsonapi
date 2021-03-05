from typing import Union, Type

from marshmallow_jsonapi.fields import Relationship as __BaseRelationship
from marshmallow_jsonapi.utils import resolve_params
from starlette.applications import Starlette

from starlette_jsonapi.meta import registered_resources
from starlette_jsonapi.utils import prefix_url_path


class JSONAPIRelationship(__BaseRelationship):
    """
    Mostly :class:`marshmallow_jsonapi.fields.Relationship`, but friendlier with async ORMs.
    Accepts ``id_attribute`` which should point to the id field corresponding to a relationship object.
    In most cases, this attribute is available even if the relationship is not loaded.
    """

    def __init__(
        self,
        id_attribute: str = None,
        related_resource: Union[str, Type] = None,
        related_route: str = None,
        related_route_kwargs: dict = None,
        *,
        self_route: str = None,
        self_route_kwargs: dict = None,
        **kwargs
    ):
        """
        Serializes a related object, according to the json:api standard.

        Example definition:

        .. code-block:: python
            :linenos:
            :emphasize-lines: 32,33,34,35,36

            from starlette_jsonapi.schema import JSONAPISchema

            # example "models"
            class Author:
                id: int
                name: str

            class Article:
                id: int
                title: str
                content: str

                author: Author
                author_id: int

            # example schemas with relationship
            class AuthorSchema(JSONAPISchema):
                class Meta:
                    type_ = 'authors'

                id = fields.Str(dump_only=True)
                name = fields.Str(required=True)

            class ArticleSchema(JSONAPISchema):
                class Meta:
                    type_ = 'articles'

                id = fields.Str(dump_only=True)
                title = fields.Str(required=True)
                content = fields.Str(required=True)

                author = JSONAPIRelationship(
                    type_='authors',
                    schema='AuthorSchema',
                    id_attribute='author_id',
                )

        :param id_attribute:  Represents the attribute name of a relationship's id.
                              Useful if the related object is not fetched.
                              Otherwise, the id attribute of a related object is accessed
                              by resolving the model attribute represented by this relationship,
                              then accessing as ``related_object.id``. When the related object
                              is populated already, or when it is lazy loaded, this parameter
                              shouldn't be needed. It should be used when the ORM of choice
                              is async and does not support lazy loading, or when fetching
                              would be considered too expensive.
        :param related_resource: The related resource, or its name, required if you wish
                                 to enable related links inside the json:api `links` object.
        :param related_route: The related route name, such that ``app.url_path_for``
                              will match back to it. Renders as `related` inside the `links` object.
                              For example, ``ArticleSchema.author`` would specify
                              ``related_route='articles:author'``, which would render as
                              `/articles/<id>/author`.
        :param related_route_kwargs: Additional :attr:``related_route`` kwargs that should be
                                     passed when calling ``app.url_path_for`` to build path params.
        :param self_route: Same as :attr:`related_route`, but refers to the relationship
                           resource GET handler. Renders as `self` inside the `links` object.
                           For example, ``ArticleSchema.author`` would specify
                           ``self_route='articles:relationships-author'``, which would render as
                           `/articles/<parent_id>/relationships/author`.
        :param self_route_kwargs: Additional :attr:`self_route` kwargs that should be
                                  passed when calling ``app.url_path_for`` to build path params.
        :param kwargs: Other keyword arguments passed to the base class
        """
        self.id_attribute = id_attribute
        self.related_resource = related_resource
        self.related_route = related_route
        self.related_route_kwargs = related_route_kwargs or {}
        self.self_route = self_route
        self.self_route_kwargs = self_route_kwargs or {}
        # When doing a PATCH on a relationship, `data` is allowed to be None
        # if the client wishes to empty a relation.
        kwargs.setdefault('allow_none', True)
        kwargs.setdefault('include_resource_linkage', True)
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
            return prefix_url_path(self.parent.app, route_name, **kwargs)
        return None

    def get_related_url(self, obj):
        return self.get_url(obj, self.related_route, **self.related_route_kwargs)

    def get_self_url(self, obj):
        return self.get_url(obj, self.self_route, **self.self_route_kwargs)

    @property
    def related_resource_class(self):
        related_resource = self.related_resource
        if isinstance(self.related_resource, str):
            related_resource = registered_resources.get(self.related_resource)
        return related_resource
