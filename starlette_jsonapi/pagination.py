import logging
from math import ceil
from typing import Any, List, Union, Iterable, Dict, Tuple

from starlette.requests import Request

logger = logging.getLogger(__name__)


class PaginationException(Exception):
    # Pagination exception used to return pagination errors according to the spec
    # https://jsonapi.org/profiles/ethanresnick/cursor-pagination/#auto-id--invalid-parameter-value-error
    pass


class BasePaginator(object):
    """
    Base class used to easily add pagination support for resources
    Typical implementations will require overriding the following methods:
        - slice_object_list
        - has_next
        - has_previous
        - get_next_link
        - get_previous_link
        - get_last_link
    It it also HIGHLY recommended that total_result_count() is overridden to optimize database queries

    This class is agnostic about the pagination strategy, can can be effectively
    subclassed accommodate for any variant.
    """
    page_param_name = None
    size_param_name = None
    default_size = None
    max_size = None

    def __init__(self, object_list: Iterable):
        self.object_list = object_list
        self.current_page = None
        self.page_size = None
        self.sliced_object_list = None
        self.request = None
        self.__pagination_complete = False

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
        return len(self.object_list)

    @property
    def total_page_count(self) -> int:
        """Determine the total number of pages"""
        if self.total_result_count == 0:
            return 1

        return ceil(self.total_result_count / self.page_size)

    def slice_object_list(self, page: Union[str, int], size: int) -> list:
        """
        This method should be implemented in subclasses in order to accommodate for different ORM's
        and optimize the database operations
        """
        logger.warning('slice_object_list() method not implemented')
        return self.sliced_object_list

    def paginate_object_list(self, page: Union[str, int], size: int) -> list:
        """Slice the queryset and save the used parameters inside the instance"""
        objects = self.slice_object_list(page, size)
        self.sliced_object_list = objects
        self.current_page = page
        self.page_size = size
        self.__pagination_complete = True
        return objects

    def has_next(self) -> bool:
        raise NotImplementedError('has_next() must be implemented to generate pagination links')

    def has_previous(self) -> bool:
        raise NotImplementedError('has_previous() must be implemented to generate pagination links')

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
        url = request.url.replace_query_params(**params)
        return str(url)

    def get_next_link(self, request: Request) -> str:
        raise NotImplementedError('get_next_link() must be implemented to generate pagination links')

    def get_previous_link(self, request: Request) -> str:
        raise NotImplementedError('get_previous_link() must be implemented to generate pagination links')

    def get_last_link(self, request: Request) -> str:
        raise NotImplementedError('get_last_link() must be implemented to generate pagination links')

    def validate_page_value(self, page: Any) -> Union[str, int]:
        """
        This method should be implemented in subclasses to accommodate for various pagination methods
        """
        logger.warning('validate_page_value() method not implemented')
        return page

    def validate_page_size_value(self, page_size: Any) -> int:
        """Sanity check for size value"""
        try:
            page_size = int(page_size)
        except (ValueError, TypeError):
            raise PaginationException(f'{self.size_param} must be an integer; got {page_size}')

        if page_size < 1:
            raise PaginationException(f'{self.size_param} must be a positive integer; got {page_size}')

        # ensure size does not exceed max configured value
        page_size = min(page_size, self.max_size)
        return page_size

    def paginate_request(self, request: Request, page: Any, size: Any=None) -> Tuple[List, Dict]:
        """Wrapper method that encapsulates entire pagination logic. Used by the resource classes"""
        page = self.validate_page_value(page)
        size = self.validate_page_size_value(size) if size else self.default_size

        object_list = self.paginate_object_list(page, size)
        pagination_links = self.generate_pagination_links(request)
        return object_list, pagination_links

    def generate_pagination_links(self, request: Request) -> Dict:
        assert self.__pagination_complete, '`paginate_object_list` must be called first to use this method'

        links = {
            'first': None,
            'next': None,
            'prev': None,
            'last': None
        }

        links['first'] = self.get_first_link(request)
        links['last'] = self.get_last_link(request)

        if self.has_next():
            links['next'] = self.get_next_link(request)

        if self.has_previous():
            links['prev'] = self.get_previous_link(request)

        return links
