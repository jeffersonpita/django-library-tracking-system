from rest_framework.pagination import PageNumberPagination

class CustomBookPagination(PageNumberPagination):
    page_size = 5  # Default page size
    page_size_query_param = 'page_size'  # Allows client to specify page size with ?page_size=X
    max_page_size = 50  # Maximum page size allowed