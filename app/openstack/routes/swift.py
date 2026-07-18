"""Swift Object Storage API v1."""

from __future__ import annotations

import json
from typing import Annotated
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import PlainTextResponse

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Swift"])


def _account(ctx: TokenContext) -> str:
    return f"AUTH_{ctx.project_id or ctx.user_id}"


@router.get("/info")
async def swift_info(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(conn, service="swift", resource_type="info", name="default")


@router.get("/v1/{account}")
async def list_containers(
    account: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> list[dict[str, object]]:
    _ = account
    rows = await conn.fetch(
        "SELECT name, meta, created_at FROM os_swift_containers WHERE account=$1 ORDER BY name",
        _account(ctx),
    )
    result = []
    for r in rows:
        count = await conn.fetchval(
            "SELECT count(*) FROM os_swift_objects WHERE account=$1 AND container=$2",
            _account(ctx),
            r["name"],
        )
        bytes_total = await conn.fetchval(
            "SELECT COALESCE(sum(bytes),0) FROM os_swift_objects WHERE account=$1 AND container=$2",
            _account(ctx),
            r["name"],
        )
        result.append({"name": r["name"], "count": int(count or 0), "bytes": int(bytes_total or 0)})
    return result


@router.put("/v1/{account}/{container}", status_code=201)
async def create_container(
    account: str,
    container: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    _ = account
    await conn.execute(
        """INSERT INTO os_swift_containers(account, name, meta)
           VALUES($1,$2,'{}'::jsonb) ON CONFLICT DO NOTHING""",
        _account(ctx),
        container,
    )
    return Response(status_code=201)


@router.get("/v1/{account}/{container}")
async def list_objects(
    account: str,
    container: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> list[dict[str, object]]:
    _ = account
    rows = await conn.fetch(
        """SELECT name, bytes, content_type, created_at FROM os_swift_objects
           WHERE account=$1 AND container=$2 ORDER BY name""",
        _account(ctx),
        container,
    )
    return [
        {
            "name": r["name"],
            "bytes": r["bytes"],
            "content_type": r["content_type"],
            "last_modified": r["created_at"].strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "hash": "0",
        }
        for r in rows
    ]


@router.put("/v1/{account}/{container}/{object_name:path}", status_code=201)
async def put_object(
    account: str,
    container: str,
    object_name: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    _ = account
    body = await request.body()
    await conn.execute(
        """INSERT INTO os_swift_containers(account, name, meta)
           VALUES($1,$2,'{}'::jsonb) ON CONFLICT DO NOTHING""",
        _account(ctx),
        container,
    )
    await conn.execute(
        """INSERT INTO os_swift_objects(id, account, container, name, content_type, bytes, body, meta)
           VALUES($1,$2,$3,$4,$5,$6,$7,'{}'::jsonb)
           ON CONFLICT (account, container, name) DO UPDATE
           SET bytes=EXCLUDED.bytes, body=EXCLUDED.body, content_type=EXCLUDED.content_type""",
        uuid4(),
        _account(ctx),
        container,
        object_name,
        request.headers.get("content-type") or "application/octet-stream",
        len(body),
        body,
    )
    return Response(status_code=201, headers={"Etag": "0"})


@router.post("/v1/{account}/{container}/{object_name:path}", status_code=202)
async def post_object(
    account: str,
    container: str,
    object_name: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    # Metadata update / create — reuse PUT semantics
    return await put_object(account, container, object_name, request, conn, ctx)


@router.get("/v1/{account}/{container}/{object_name:path}")
async def get_object(
    account: str,
    container: str,
    object_name: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    _ = account
    row = await conn.fetchrow(
        """SELECT body, content_type FROM os_swift_objects
           WHERE account=$1 AND container=$2 AND name=$3""",
        _account(ctx),
        container,
        object_name,
    )
    if row is None:
        raise OpenStackError("NotFound", "Object not found", status_code=404)
    return Response(content=bytes(row["body"] or b""), media_type=row["content_type"])


@router.delete("/v1/{account}/{container}/{object_name:path}", status_code=204)
async def delete_object(
    account: str,
    container: str,
    object_name: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    _ = account
    result = await conn.execute(
        "DELETE FROM os_swift_objects WHERE account=$1 AND container=$2 AND name=$3",
        _account(ctx),
        container,
        object_name,
    )
    if result.endswith("0"):
        raise OpenStackError("NotFound", "Object not found", status_code=404)
    return Response(status_code=204)
