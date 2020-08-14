from math import ceil
from typing import Dict, Sequence

from starlette_jsonapi.pagination import BasePageNumberPaginator


class PageNumberPaginator(BasePageNumberPaginator):

    def slice_object_list(self, params: dict=None) -> Sequence:
        data = self.data[(self.page_number-1) * self.page_size : self.page_number * self.page_size]
        return data

    def _create_pagination_link(self, page_number, page_size):
        params = {
            f'page[{self.page_number_param}]': page_number,
            f'page[{self.page_size_param}]': page_size
        }
        return str(self.request.url.replace_query_params(**params))

    def generate_pagination_links(self, params: dict=None) -> Dict[str, str]:
        links = dict(first=None, next=None, prev=None, last=None)
        page_count = ceil(len(self.data)/self.page_size)

        # first
        links['first'] = self._create_pagination_link(page_number=1, page_size=self.page_size)

        # last
        links['last'] = self._create_pagination_link(page_number=page_count, page_size=self.page_size)

        # next
        has_next = self.page_number < page_count
        if has_next:
            links['next'] = self._create_pagination_link(page_number=self.page_number+1, page_size=self.page_size)

        # previous
        has_prev = self.page_number > 1
        if has_prev:
            links['prev'] = self._create_pagination_link(page_number=self.page_number-1, page_size=self.page_size)

        return links
