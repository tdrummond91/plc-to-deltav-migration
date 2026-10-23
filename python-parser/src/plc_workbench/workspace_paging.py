"""Explicit bounded page sizes shared by the local review projections."""
from __future__ import annotations

LIST_SIZES = (10, 50, 100, 200, 500)
GRAPH_SIZES = (10, 25, 50, 100)


def page_size(query: dict, default: int, *, key: str = 'page_size', graph: bool = False,
              error: type[Exception] = ValueError) -> int:
    value = query.get(key, default)
    if (type(value) not in (str, int) or len(str(value)) > 3
            or not str(value).isascii() or not str(value).isdigit()):
        raise error('Choose one of the available page sizes.')
    result = int(value)
    if result not in {*(GRAPH_SIZES if graph else LIST_SIZES), default}:
        raise error('Choose one of the available page sizes.')
    return result
