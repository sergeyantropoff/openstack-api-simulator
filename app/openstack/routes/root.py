"""Port-aware root / version discovery (and HTML console for browsers)."""

from __future__ import annotations

from typing import Annotated

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.openstack.db_docs import require_doc
from app.openstack.deps import get_conn
from app.openstack.dispatch import resolve_service
from app.web.assets import console_html

router = APIRouter(tags=["OpenStack"])


def _service_name(request: Request) -> str:
    headers = {k.lower(): v for k, v in request.headers.items()}
    # Prefer explicit gateway port/service; also pass path for disambiguation.
    resolved = resolve_service(headers, path=request.url.path)
    if resolved and resolved not in ("", "https"):
        return resolved
    # Fallback: Host:port when proxies strip/alter X-Forwarded-Port.
    host = headers.get("host") or ""
    if ":" in host:
        try:
            port = int(host.rsplit(":", 1)[1])
        except ValueError:
            port = None
        if port is not None:
            from app.openstack.dispatch import _PORT_TO_SERVICE

            by_host = _PORT_TO_SERVICE.get(port)
            if by_host:
                return by_host
    return "keystone"


def _wants_html(request: Request) -> bool:
    accept = (request.headers.get("accept") or "*/*").lower()
    if accept.startswith("application/json"):
        return False
    return "text/html" in accept.split(",")[0] or (
        "text/html" in accept and "application/json" not in accept
    )


async def _json_versions(conn: Connection, name: str) -> dict[str, object]:
    return await require_doc(conn, service=name, resource_type="discovery_version", name="default")


@router.get("/")
async def root(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
):
    if _wants_html(request):
        return HTMLResponse(console_html(), headers={"Cache-Control": "no-store"})
    return JSONResponse(await _json_versions(conn, _service_name(request)))
