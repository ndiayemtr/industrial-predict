from math import ceil

from app.schemas.pagination import Page


def build_page(
    *,
    items: list,
    total: int,
    page: int,
    page_size: int,
) -> Page:
    pages = ceil(total / page_size) if total > 0 else 0

    return Page(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )