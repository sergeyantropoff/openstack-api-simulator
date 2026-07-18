"""Unit tests for OpenStack pagination helper."""

from __future__ import annotations

from starlette.requests import Request

from app.openstack.paging import paginate_rows, parse_limit


def _request(query: str = "") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/v2.1/servers",
        "raw_path": b"/v2.1/servers",
        "query_string": query.encode(),
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
    }
    return Request(scope)


def test_parse_limit_clamps() -> None:
    assert parse_limit(_request("")) == 0
    assert parse_limit(_request("limit=25")) == 25
    assert parse_limit(_request("limit=99999"), maximum=100) == 100


def test_paginate_rows_marker_and_next_link() -> None:
    rows = [{"id": f"id-{i}"} for i in range(10)]
    page, links = paginate_rows(
        rows,
        _request("limit=3&marker=id-2"),
        id_attr=lambda r: r["id"],
    )
    assert [r["id"] for r in page] == ["id-3", "id-4", "id-5"]
    assert links and links[0]["rel"] == "next"
    assert "marker=id-5" in links[0]["href"]
