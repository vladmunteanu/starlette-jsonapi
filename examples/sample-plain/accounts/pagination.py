from starlette_jsonapi.pagination import BasePaginator


class PageNumberPaginator(BasePaginator):
    page_param_name = 'number'
    size_param_name = 'size'
    default_size = 20
    max_size = 100

    def validate_page_value(self, page):
        if not page:
            return 1
        return int(page)

    def slice_object_list(self, page, size):
        page = page - 1
        objects = self.object_list[page * size: (page + 1) * size]
        return objects

    def has_next(self):
        return self.current_page < self.total_page_count

    def has_previous(self):
        return self.current_page > 1

    def get_next_link(self, request):
        return self.create_pagination_link(request, self.current_page+1)

    def get_previous_link(self, request):
        return self.create_pagination_link(request, self.current_page-1)

    def get_last_link(self, request):
        if self.current_page == 1 and not self.has_next():
            last_page = self.current_page
        else:
            last_page = self.total_page_count

        return self.create_pagination_link(request, last_page)
