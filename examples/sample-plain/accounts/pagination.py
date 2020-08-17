from math import ceil
from typing import Dict, Sequence, Optional

from starlette_jsonapi.pagination import BasePageNumberPagination


class PageNumberPagination(BasePageNumberPagination):

    def slice_data(self, params: dict = None) -> Sequence:
        slice_start = (self.page_number - 1) * self.page_size
        slice_end = self.page_number * self.page_size
        data = self.data[slice_start:slice_end]
        return data

    def generate_pagination_links(self, params: dict = None) -> Dict[str, Optional[str]]:
        links = dict(first=None, next=None, prev=None, last=None)
        page_count = ceil(len(self.data)/self.page_size)

        # first
        links['first'] = self.create_pagination_link(page_number=1, page_size=self.page_size)

        # last
        links['last'] = self.create_pagination_link(page_number=page_count, page_size=self.page_size)

        # next
        has_next = self.page_number < page_count
        if has_next:
            links['next'] = self.create_pagination_link(page_number=self.page_number+1, page_size=self.page_size)

        # previous
        has_prev = self.page_number > 1
        if has_prev:
            links['prev'] = self.create_pagination_link(page_number=self.page_number-1, page_size=self.page_size)

        return links
