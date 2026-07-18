"""FastAPI dependencies for OpenStack routes."""

from __future__ import annotations

from typing import Annotated

from asyncpg import Connection, Pool
from fastapi import Depends, Request

from app.db.pool import AsyncpgDatabase
from app.dependencies import get_database
from app.openstack.auth import TokenContext, extract_token, validate_token
from app.openstack.errors import OpenStackError


async def get_pool(request: Request) -> Pool:
    database = get_database(request)
    if not isinstance(database, AsyncpgDatabase):
        raise OpenStackError("ServiceUnavailable", "Database unavailable", status_code=503)
    return database.pool


async def get_conn(pool: Annotated[Pool, Depends(get_pool)]) -> Connection:
    async with pool.acquire() as connection:
        yield connection


async def require_token(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
) -> TokenContext:
    token_id = extract_token({k: v for k, v in request.headers.items()})
    if token_id is None:
        raise OpenStackError(
            "Unauthorized",
            "The request you have made requires authentication.",
            status_code=401,
        )
    return await validate_token(conn, token_id)


async def require_project_token(
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> TokenContext:
    if ctx.project_id is None:
        raise OpenStackError(
            "Forbidden",
            "A project-scoped token is required for this action.",
            status_code=403,
        )
    return ctx


def request_public_host(request: Request, default: str = "localhost") -> str:
    forwarded = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if not forwarded:
        return default
    host = forwarded.split(",")[0].strip()
    # Strip port from Host header so catalog can attach service ports.
    if host.startswith("["):
        # [ipv6]:port
        if "]" in host:
            return host[1 : host.index("]")]
        return host.strip("[]")
    return host.rsplit(":", 1)[0]


def request_scheme(request: Request) -> str:
    return request.headers.get("x-forwarded-proto") or request.url.scheme or "http"
