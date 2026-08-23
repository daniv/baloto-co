"""Generic pagination envelope for paginated list endpoints."""

from pydantic import BaseModel


class PaginatedResponse[T](BaseModel):
    """
    A generic paginated response envelope.

    :param items: The results for the current page.
    :param page: The current 1-indexed page number.
    :param size: The number of items requested per page.
    :param total: The total number of items across all pages.
    :param pages: The total number of pages available.
    """

    items: list[T]
    page: int
    size: int
    total: int
    pages: int
