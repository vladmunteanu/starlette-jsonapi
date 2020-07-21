import logging
from collections import namedtuple
from math import ceil
from typing import Any, Union, Dict, Tuple, Optional, Sequence

from starlette.requests import Request

from starlette_jsonapi.exceptions import PaginationException

logger = logging.getLogger(__name__)


Pagination = namedtuple('Pagination', ['data', 'links'])


class BasePaginator:
    """
    Base class used to easily add pagination support for resources
    This class is agnostic about the pagination strategy, and can be effectively
    subclassed to accommodate for any variant.

    Typical implementations will require overriding the following methods:
        - slice_object_list
        - has_next
        - has_previous
        - get_next_link
        - get_previous_link
        - get_last_link

    While not strictly required, it is HIGHLY recommended that total_result_count()
    is overridden to optimize database queries.

    It is also recommended to override validate_page_value to ensure value sanity checks
    for this parameter, and raise PaginationException to properly generate an API error
    """
    page_param_name: Optional[str] = None
    size_param_name: Optional[str] = None
    default_size: Optional[int] = None
    max_size: Optional[int] = None

    def __init__(self, object_list: Sequence):
        self.object_list = object_list
        self.current_page: Union[str, int, None] = None
        self.page_size: Optional[int] = None
        self.sliced_object_list: Optional[Sequence] = None
        self.request: Optional[Request] = None
        self._pagination_complete: bool = False

    @property
    def page_param(self) -> str:
        """wrap the page parameter name in the json:api specified pagination parameter"""
        # number -> page[number]
        return f'page[{self.page_param_name}]'

    @property
    def size_param(self) -> str:
        """wrap the size parameter name in the json:api specified pagination parameter"""
        # size -> page[size]
        return f'page[{self.size_param_name}]'

    @property
    def total_result_count(self) -> int:
        """
        It is recommended that this method is overridden in subclasses in order
        to optimize the database query, since this can end up evaluating the entire query
        before the actual slicing is done
        """
        logger.warning('overriding `total_result_count` is HIGHLY recommended to optimize db queries')
        return len(self.object_list)

    @property
    def total_page_count(self) -> int:
        """Determine the total number of pages"""
        if self.total_result_count == 0:
            return 1

        return ceil(self.total_result_count / self.page_size)

    def slice_object_list(self, page: Union[str, int], size: int) -> Sequence:
        """
        This method should be implemented in subclasses in order to accommodate for different ORM's
        and optimize the database operations
        """
        raise NotImplementedError('`slice_object_list` method not implemented')

    def paginate_object_list(self, page: Union[str, int], size: int) -> Sequence:
        """Slice the queryset and save the used parameters inside the instance"""
        objects = self.slice_object_list(page, size)
        self.sliced_object_list = objects
        self.current_page = page
        self.page_size = size
        self._pagination_complete = True
        return objects

    def has_next(self) -> bool:
        raise NotImplementedError('`has_next()` must be implemented to generate pagination links')

    def has_previous(self) -> bool:
        raise NotImplementedError('`has_previous()` must be implemented to generate pagination links')

    def create_pagination_link(self, request: Request, page: Union[str, int]) -> str:
        """Used to easily create a pagination link for a resource"""
        params = {
            self.page_param: page,
            self.size_param: self.page_size
        }
        url = request.url.replace_query_params(**params)
        return str(url)

    def get_first_link(self, request: Request) -> str:
        """Use the current url without the page parameter"""
        params = {key: value for key, value in request.query_params.items() if key != self.page_param}
        if self.page_param_name not in params:  # ensure size is added in case of default pagination
            params[self.size_param] = self.page_size

        url = request.url.replace_query_params(**params)
        return str(url)

    def get_next_link(self, request: Request) -> str:
        raise NotImplementedError('`get_next_link()` must be implemented to generate pagination links')

    def get_previous_link(self, request: Request) -> str:
        raise NotImplementedError('`get_previous_link()` must be implemented to generate pagination links')

    def get_last_link(self, request: Request) -> str:
        raise NotImplementedError('`get_last_link()` must be implemented to generate pagination links')

    def validate_page_value(self, page: Any) -> Union[str, int]:
        """
        This method should be implemented in subclasses to accommodate for various pagination methods
        """
        logger.warning('`validate_page_value()` method not implemented')
        return str(page)

    def validate_page_size_value(self, page_size: Any) -> int:
        """Sanity check for size value"""
        try:
            page_size = int(page_size)
        except (ValueError, TypeError):
            raise PaginationException(f'{self.size_param} must be a positive integer; got {page_size}')

        if page_size < 1:
            raise PaginationException(f'{self.size_param} must be a positive integer; got {page_size}')

        # ensure size does not exceed max configured value
        page_size = min(page_size, self.max_size)
        return page_size

    def paginate_request(self, request: Request, page: Any, size: int) -> Pagination:
        """Wrapper method that encapsulates entire pagination logic. Used by the resource classes"""
        page = self.validate_page_value(page)
        size = self.validate_page_size_value(size)

        object_list = self.paginate_object_list(page, size)
        pagination_links = self.generate_pagination_links(request)
        return Pagination(object_list, pagination_links)
        # return object_list, pagination_links

    def generate_pagination_links(self, request: Request) -> Dict:
        assert self._pagination_complete, '`paginate_object_list` must be called first to use this method'
        links: Dict[str, Optional[str]] = dict(first=None, next=None, prev=None, last=None)
        links['first'] = self.get_first_link(request)
        links['last'] = self.get_last_link(request)

        if self.has_next():
            links['next'] = self.get_next_link(request)

        if self.has_previous():
            links['prev'] = self.get_previous_link(request)

        return links
