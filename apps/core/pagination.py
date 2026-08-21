from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Default pagination: 20 items per page, max 100."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class SmallResultsSetPagination(PageNumberPagination):
    """Small pagination for nested resources: 10 items per page."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50
