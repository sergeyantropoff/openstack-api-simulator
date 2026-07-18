"""OpenStack-style limit/marker pagination helpers."""

from __future__ import annotations

from typing import Any, Callable

from starlette.requests import Request


def parse_limit(request: Request, *, default: int = 0, maximum: int = 1000) -> int:
    raw = request.query_params.get("limit")
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return min(value, maximum)


def paginate_rows(
    rows: list[Any],
    request: Request,
    *,
    id_attr: Callable[[Any], str],
    default_limit: int = 0,
) -> tuple[list[Any], list[dict[str, str]]]:
    """Slice rows by marker/limit. Returns (page, link dicts for next)."""

    marker = request.query_params.get("marker")
    limit = parse_limit(request, default=default_limit)
    start = 0
    if marker:
        for index, row in enumerate(rows):
            if id_attr(row) == marker:
                start = index + 1
                break
    page = rows[start:]
    links: list[dict[str, str]] = []
    if limit > 0 and len(page) > limit:
        page = page[:limit]
        last = page[-1]
        links.append({"rel": "next", "href": f"?marker={id_attr(last)}&limit={limit}"})
    return page, links
