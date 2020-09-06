import logging
from typing import Dict, Sequence, NamedTuple, Optional, Union

from starlette.requests import Request

logger = logging.getLogger(__name__)


class Pagination(NamedTuple):
    data: Sequence
    links: Dict[str, Optional[str]]


class BasePagination:
    """
    Base class used to easily add pagination support for resources
    This class is agnostic about the pagination strategy, and can be effectively
    subclassed to accommodate for any variant.

    Implementation will require overriding the following methods:
        - slice_data
        - process_query_params
        - generate_pagination_links
    """
    def __init__(self, request: Request, data: Sequence, **kwargs):
        self.data = data
        self.request = request
        self.process_query_params()

    def process_query_params(self):
        """
        Parse the request to store the pagination parameters for later usage
        Should be implemented in subclasses
        """
        return

    def slice_data(self, params: dict = None) -> Sequence:
        """
        This method should be implemented in subclasses in order to accommodate for different ORM's
        and optimize the database operations
        """
        raise NotImplementedError()

    def get_pagination(self, params: dict = None) -> Pagination:
        """Slice the queryset according to the pagination rules, and create pagination links"""
        data = self.slice_data(params)
        links = self.generate_pagination_links(params)
        return Pagination(data=data, links=links)

    def generate_pagination_links(self, params: dict = None) -> Dict[str, Optional[str]]:
        """Create a dict of pagination helper links"""
        return {}


class BasePageNumberPagination(BasePagination):
    """
    Base class for accommodating the page number pagination strategy using the standard parameters
    under the JSON:API format
        - page[number]
        - page[size]

    Implementation will require overriding the following methods:
        - slice_data
        - generate_pagination_links
    """
    page_number_param = 'number'
    page_size_param = 'size'

    default_page_number = 1
    default_page_size = 50
    max_page_size = 100

    def process_query_params(self):
        """Extract the page number and page size from the query parameters"""
        page_number = self.request.query_params.get(
            f'page[{self.page_number_param}]',
            self.default_page_number
        )
        page_size = self.request.query_params.get(
            f'page[{self.page_size_param}]',
            self.default_page_size
        )

        # perform sanity checks for page size and number values
        page_size = int(page_size)
        page_size = min(page_size, self.max_page_size)  # ensure max page size is not exceeded

        page_number = int(page_number)
        if page_number < 0:
            page_number = self.default_page_number

        self.page_size = page_size
        self.page_number = page_number

    def create_pagination_link(self, page_number: int, page_size: int) -> str:
        """Helper method used to easily generate links used in pagination"""
        params = {
            f'page[{self.page_number_param}]': page_number,
            f'page[{self.page_size_param}]': page_size
        }
        return str(self.request.url.replace_query_params(**params))


class BaseOffsetPagination(BasePagination):
    """
    Base class for accommodating the offset pagination strategy using the standard parameters
    under the JSON:API format
        - page[offset]
        - page[size]

    Implementation will require overriding the following methods:
        - slice_data
        - generate_pagination_links
    """
    page_offset_param = 'offset'
    page_size_param = 'size'

    default_page_offset = 0
    default_page_size = 50
    max_page_size = 100

    def process_query_params(self):
        """Extract the page offset and page size from the query parameters"""
        page_offset = self.request.query_params.get(
            f'page[{self.page_offset_param}]',
            self.default_page_offset
        )
        page_size = self.request.query_params.get(
            f'page[{self.page_size_param}]',
            self.default_page_size
        )

        # perform sanity checks for page size and offset
        page_size = int(page_size)
        page_size = min(page_size, self.max_page_size)  # ensure max page size is not exceeded

        page_offset = int(page_offset)
        if page_offset < 0:
            page_offset = self.default_page_offset

        self.page_size = page_size
        self.page_offset = page_offset

    def create_pagination_link(self, page_offset: int, page_size: int) -> str:
        """Helper method used to easily generate links used in pagination"""
        params = {
            f'page[{self.page_offset_param}]': page_offset,
            f'page[{self.page_size_param}]': page_size
        }
        return str(self.request.url.replace_query_params(**params))


class BaseCursorPagination(BasePagination):
    """
    Base class for accommodating the cursor pagination strategy using the standard parameters
    under the JSON:API format
        - page[after]
        - page[before]
        - page[size]

    Implementation will require overriding the following methods:
        - slice_data
        - generate_pagination_links
    """
    page_after_param = 'after'
    page_before_param = 'before'
    page_size_param = 'size'

    default_page_after = 0
    default_page_before = None
    default_page_size = 50
    max_page_size = 100

    def process_query_params(self):
        """Extract the cursor positions and page size from the query parameters"""
        page_size = self.request.query_params.get(
            f'page[{self.page_size_param}]',
            self.default_page_size
        )
        # perform sanity checks for page size values
        page_size = int(page_size)
        page_size = min(page_size, self.max_page_size)  # ensure max page size is not exceeded

        self.page_size = int(page_size)
        self.page_after = self.request.query_params.get(
            f'page[{self.page_after_param}]',
            self.default_page_after
        )
        self.page_before = self.request.query_params.get(
            f'page[{self.page_before_param}]',
            self.default_page_before
        )

    def create_pagination_link(
            self, page_size: int,
            page_after: Union[str, int, None] = None,
            page_before: Union[str, int, None] = None,
    ) -> str:
        """Helper method used to easily generate links used in pagination"""
        params = {
            f'page[{self.page_size_param}]': page_size
        }  # type: Dict[str, Union[str, int]]
        if page_after is not None:
            params[f'page[{self.page_after_param}]'] = page_after
        if page_before is not None:
            params[f'page[{self.page_before_param}]'] = page_before

        return str(self.request.url.replace_query_params(**params))
