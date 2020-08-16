import logging
from typing import Dict, Sequence, NamedTuple, Optional

from starlette.requests import Request

logger = logging.getLogger(__name__)


class Pagination(NamedTuple):
    data: Sequence
    links: Dict[str, Optional[str]]


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
    def __init__(self, request: Request, data: Sequence):
        self.data = data
        self.request = request
        self.process_query_params()

    def process_query_params(self):
        return

    def slice_object_list(self, params: dict = None) -> Sequence:
        """
        This method should be implemented in subclasses in order to accommodate for different ORM's
        and optimize the database operations
        """
        raise NotImplementedError()

    def get_pagination(self, params: dict = None) -> Pagination:
        data = self.slice_object_list(params)
        links = self.generate_pagination_links(params)
        return Pagination(data=data, links=links)

    def generate_pagination_links(self, params: dict = None) -> Dict[str, Optional[str]]:
        return {}


class BasePageNumberPaginator(BasePaginator):
    page_number_param = 'number'
    page_size_param = 'size'

    default_page_number = 1
    default_page_size = 50

    def process_query_params(self):
        page_number = self.request.query_params.get(
            f'page[{self.page_number_param}]',
            self.default_page_number
        )
        page_size = self.request.query_params.get(
            f'page[{self.page_size_param}]',
            self.default_page_size
        )

        self.page_number = int(page_number)
        self.page_size = int(page_size)


class BaseOffsetPaginator(BasePaginator):
    page_offset_param = 'offset'
    page_size_param = 'size'

    default_page_offset = 0
    default_page_size = 50

    def process_query_params(self):
        page_offset = self.request.query_params.get(
            f'page[{self.page_offset_param}]',
            self.default_page_offset
        )
        page_size = self.request.query_params.get(
            f'page[{self.page_size_param}]',
            self.default_page_size
        )

        self.page_offset = int(page_offset)
        self.page_size = int(page_size)


class BaseCursorPaginator(BasePaginator):
    page_before_param = 'before'
    page_after_param = 'after'
    page_size_param = 'size'

    default_page_before = None
    default_page_after = 0
    default_page_size = 50

    def process_query_params(self):
        page_size = self.request.query_params.get(
            f'page[{self.page_size_param}]',
            self.default_page_size
        )

        self.page_size = int(page_size)
        self.page_before = self.request.query_params.get(
            f'page[{self.page_before_param}]',
            self.default_page_before
        )
        self.page_after = self.request.query_params.get(
            f'page[{self.page_after_param}]',
            self.default_page_after
        )
