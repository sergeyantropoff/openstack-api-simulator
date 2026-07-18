"""Heat Orchestration API v1."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token, require_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Heat"])


def _stack(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "stack_name": row["stack_name"],
        "stack_status": row["stack_status"],
        "description": row["description"],
        "creation_time": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_time": row["updated_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stack_owner": str(row["project_id"]),
        "parent": None,
        "stack_user_project_id": str(row["project_id"]),
        "outputs": row["outputs"]
        if not isinstance(row["outputs"], str)
        else json.loads(row["outputs"]),
        "parameters": row["parameters"]
        if not isinstance(row["parameters"], str)
        else json.loads(row["parameters"]),
        "links": [
            {
                "rel": "self",
                "href": f"/v1/{row['project_id']}/stacks/{row['stack_name']}/{row['id']}",
            }
        ],
    }


@router.get("/v1")
@router.get("/v1/")
async def heat_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="heat", resource_type="discovery_version", name="default"
    )


@router.get("/v1/{tenant_id}/stacks")
async def list_stacks(
    tenant_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    _ = tenant_id
    rows = list(
        await conn.fetch(
            "SELECT * FROM os_stacks WHERE project_id = $1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"stacks": [_stack(r) for r in page]}
    if links:
        body["stacks_links"] = links
    return body


@router.get("/v1/{tenant_id}/stacks/detail")
async def list_stacks_detail(
    tenant_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await list_stacks(tenant_id, request, conn, ctx)


@router.post("/v1/{tenant_id}/stacks", status_code=201)
async def create_stack(
    tenant_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    _ = tenant_id
    payload = await request.json()
    stack = payload.get("stack") or payload
    defaults = (
        await fetch_doc(conn, service="heat", resource_type="stack_defaults", name="default") or {}
    )
    name = stack.get("stack_name") or stack.get("name") or f"stack-{uuid4().hex[:8]}"
    template = (
        stack.get("template")
        if isinstance(stack.get("template"), dict)
        else defaults.get("template")
    )
    parameters = (
        stack.get("parameters")
        if isinstance(stack.get("parameters"), dict)
        else defaults.get("parameters")
    )
    if not isinstance(template, dict):
        template = {}
    if not isinstance(parameters, dict):
        parameters = {}
    row = await conn.fetchrow(
        """INSERT INTO os_stacks(id, project_id, stack_name, stack_status, description, template, parameters, outputs)
           VALUES($1,$2,$3,'CREATE_COMPLETE',$4,$5::jsonb,$6::jsonb,'[]'::jsonb) RETURNING *""",
        uuid4(),
        ctx.project_id,
        name,
        stack.get("description") or "",
        json.dumps(template),
        json.dumps(parameters),
    )
    return {"stack": _stack(row)}


@router.get("/v1/{tenant_id}/stacks/{id}")
async def show_stack_by_id(
    tenant_id: str,
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = tenant_id
    row = await conn.fetchrow(
        "SELECT * FROM os_stacks WHERE project_id=$1 AND (id::text=$2 OR stack_name=$2) ORDER BY created_at DESC LIMIT 1",
        ctx.project_id,
        id,
    )
    if row is None:
        raise OpenStackError("StackNotFound", "Stack not found", status_code=404)
    return {"stack": _stack(row)}


async def _update_stack(
    *,
    project_id: Any,
    stack_id: str | None,
    stack_name: str | None,
    request: Request,
    conn: Connection,
) -> dict[str, object]:
    payload = await request.json()
    stack = payload.get("stack") or payload
    if stack_id:
        row = await conn.fetchrow(
            "SELECT * FROM os_stacks WHERE project_id=$1 AND id::text=$2",
            project_id,
            stack_id,
        )
    else:
        row = await conn.fetchrow(
            """SELECT * FROM os_stacks
               WHERE project_id=$1 AND (id::text=$2 OR stack_name=$2)
               ORDER BY created_at DESC LIMIT 1""",
            project_id,
            stack_name,
        )
    if row is None:
        raise OpenStackError("StackNotFound", "Stack not found", status_code=404)
    desc = stack.get("description") if "description" in stack else row["description"]
    template = stack.get("template") if isinstance(stack.get("template"), dict) else None
    parameters = stack.get("parameters") if isinstance(stack.get("parameters"), dict) else None
    await conn.execute(
        """UPDATE os_stacks
           SET description=$1,
               template=COALESCE($2::jsonb, template),
               parameters=COALESCE($3::jsonb, parameters),
               updated_at=now(),
               stack_status='UPDATE_COMPLETE'
           WHERE id=$4""",
        desc,
        json.dumps(template) if template is not None else None,
        json.dumps(parameters) if parameters is not None else None,
        row["id"],
    )
    row = await conn.fetchrow("SELECT * FROM os_stacks WHERE id=$1", row["id"])
    return {"stack": _stack(row)}


@router.put("/v1/{tenant_id}/stacks/{id}")
@router.patch("/v1/{tenant_id}/stacks/{id}")
async def update_stack_by_id(
    tenant_id: str,
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = tenant_id
    return await _update_stack(
        project_id=ctx.project_id,
        stack_id=None,
        stack_name=id,
        request=request,
        conn=conn,
    )


@router.put("/v1/{tenant_id}/stacks/{stack_name}/{stack_id}")
@router.patch("/v1/{tenant_id}/stacks/{stack_name}/{stack_id}")
async def update_stack_by_name(
    tenant_id: str,
    stack_name: str,
    stack_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = tenant_id, stack_name
    return await _update_stack(
        project_id=ctx.project_id,
        stack_id=stack_id,
        stack_name=None,
        request=request,
        conn=conn,
    )


@router.delete("/v1/{tenant_id}/stacks/{id}", status_code=204)
async def delete_stack_by_id(
    tenant_id: str,
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    _ = tenant_id
    result = await conn.execute(
        "DELETE FROM os_stacks WHERE project_id=$1 AND (id::text=$2 OR stack_name=$2)",
        ctx.project_id,
        id,
    )
    if result.endswith("0"):
        raise OpenStackError("StackNotFound", "Stack not found", status_code=404)
    return Response(status_code=204)


@router.get("/v1/{tenant_id}/stacks/{stack_name}/{stack_id}")
@router.get("/v1/{tenant_id}/stacks/{stack_name}")
async def show_stack(
    tenant_id: str,
    stack_name: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    stack_id: str | None = None,
) -> dict[str, object]:
    _ = tenant_id
    if stack_name == "detail" and stack_id is None:
        from app.openstack.paging import paginate_rows

        rows = list(
            await conn.fetch(
                "SELECT * FROM os_stacks WHERE project_id = $1 ORDER BY created_at, id",
                ctx.project_id,
            )
        )
        page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
        body: dict[str, object] = {"stacks": [_stack(r) for r in page]}
        if links:
            body["stacks_links"] = links
        return body
    if stack_id:
        row = await conn.fetchrow(
            "SELECT * FROM os_stacks WHERE project_id=$1 AND id::text=$2",
            ctx.project_id,
            stack_id,
        )
    else:
        row = await conn.fetchrow(
            "SELECT * FROM os_stacks WHERE project_id=$1 AND stack_name=$2 ORDER BY created_at DESC LIMIT 1",
            ctx.project_id,
            stack_name,
        )
    if row is None:
        raise OpenStackError("StackNotFound", "Stack not found", status_code=404)
    return {"stack": _stack(row)}


@router.delete("/v1/{tenant_id}/stacks/{stack_name}/{stack_id}", status_code=204)
async def delete_stack(
    tenant_id: str,
    stack_name: str,
    stack_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    _ = tenant_id, stack_name
    result = await conn.execute(
        "DELETE FROM os_stacks WHERE project_id=$1 AND id::text=$2",
        ctx.project_id,
        stack_id,
    )
    if result.endswith("0"):
        raise OpenStackError("StackNotFound", "Stack not found", status_code=404)
    return Response(status_code=204)


@router.get("/v1/{tenant_id}/resource_types")
async def resource_types(
    tenant_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    _ = tenant_id
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="heat", resource_type="resource_type_list", name="default"
    )
