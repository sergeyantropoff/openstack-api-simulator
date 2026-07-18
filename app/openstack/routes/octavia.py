"""Octavia Load Balancer API v2."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Octavia"])


def _lb(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "project_id": str(row["project_id"]),
        "vip_address": row["vip_address"],
        "vip_subnet_id": str(row["vip_subnet_id"]) if row["vip_subnet_id"] else None,
        "provisioning_status": row["provisioning_status"],
        "operating_status": row["operating_status"],
        "listeners": row["listeners"]
        if not isinstance(row["listeners"], str)
        else json.loads(row["listeners"]),
        "pools": row["pools"] if not isinstance(row["pools"], str) else json.loads(row["pools"]),
        "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%S"),
    }


@router.get("/v2")
@router.get("/v2/")
@router.get("/v2.0")
@router.get("/v2.0/")
async def octavia_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="octavia", resource_type="discovery_version", name="default"
    )


@router.get("/v2/lbaas/loadbalancers")
@router.get("/v2.0/lbaas/loadbalancers")
async def list_lbs(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(
        await conn.fetch(
            "SELECT * FROM os_loadbalancers WHERE project_id=$1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"loadbalancers": [_lb(r) for r in page]}
    if links:
        body["loadbalancers_links"] = links
    return body


@router.post("/v2/lbaas/loadbalancers", status_code=201)
@router.post("/v2.0/lbaas/loadbalancers", status_code=201)
async def create_lb(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    payload = (await request.json()).get("loadbalancer") or {}
    defaults = (
        await fetch_doc(
            conn, service="octavia", resource_type="loadbalancer_defaults", name="default"
        )
        or {}
    )
    row = await conn.fetchrow(
        """INSERT INTO os_loadbalancers(id, project_id, name, description, vip_address, vip_subnet_id, provisioning_status, operating_status)
           VALUES($1,$2,$3,$4,$5,$6::uuid,'ACTIVE','ONLINE') RETURNING *""",
        uuid4(),
        ctx.project_id,
        payload.get("name") or defaults.get("name") or "lb",
        payload.get("description") or "",
        payload.get("vip_address") or defaults.get("vip_address"),
        payload.get("vip_subnet_id"),
    )
    return {"loadbalancer": _lb(row)}


@router.get("/v2/lbaas/loadbalancers/{lb_id}")
@router.get("/v2.0/lbaas/loadbalancers/{lb_id}")
async def show_lb(
    lb_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_loadbalancers WHERE id::text=$1 AND project_id=$2",
        lb_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", "Load balancer not found", status_code=404)
    return {"loadbalancer": _lb(row)}


async def _update_lb(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("loadbalancer") or {}
    row = await conn.fetchrow(
        """UPDATE os_loadbalancers
           SET name = COALESCE($1, name),
               description = COALESCE($2, description)
           WHERE id::text = $3 AND project_id = $4
           RETURNING *""",
        payload.get("name"),
        payload.get("description"),
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", "Load balancer not found", status_code=404)
    return {"loadbalancer": _lb(row)}


@router.put("/v2/lbaas/loadbalancers/{lb_id}")
@router.put("/v2.0/lbaas/loadbalancers/{lb_id}")
@router.patch("/v2/lbaas/loadbalancers/{lb_id}")
@router.patch("/v2.0/lbaas/loadbalancers/{lb_id}")
async def update_lb(
    lb_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_lb(lb_id, request, conn, ctx)


@router.put("/v2/lbaas/loadbalancers/{id}")
@router.put("/v2.0/lbaas/loadbalancers/{id}")
@router.patch("/v2/lbaas/loadbalancers/{id}")
@router.patch("/v2.0/lbaas/loadbalancers/{id}")
async def update_lb_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_lb(id, request, conn, ctx)


@router.delete("/v2/lbaas/loadbalancers/{lb_id}", status_code=204)
@router.delete("/v2.0/lbaas/loadbalancers/{lb_id}", status_code=204)
async def delete_lb(
    lb_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_loadbalancers WHERE id::text=$1 AND project_id=$2",
        lb_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("NotFound", "Load balancer not found", status_code=404)
    return Response(status_code=204)


@router.get("/v2/lbaas/listeners")
@router.get("/v2.0/lbaas/listeners")
@router.get("/v2/lbaas/pools")
@router.get("/v2.0/lbaas/pools")
@router.get("/v2/lbaas/healthmonitors")
@router.get("/v2.0/lbaas/healthmonitors")
@router.get("/v2/lbaas/providers")
@router.get("/v2.0/lbaas/providers")
@router.get("/v2/lbaas/flavors")
@router.get("/v2.0/lbaas/flavors")
async def octavia_extension_collections(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    """Serve Octavia side collections from demo/schema rows."""

    import json as _json

    key = request.url.path.rstrip("/").split("/")[-1]
    resource_type = {
        "listeners": "listener",
        "pools": "pool",
        "healthmonitors": "healthmonitor",
        "flavors": "flavor",
        "providers": "provider",
    }.get(key, key)
    rows = await conn.fetch(
        """SELECT id, name, status, data FROM os_api_objects
           WHERE service='octavia' AND resource_type=$1
             AND (project_id=$2 OR project_id IS NULL)
           ORDER BY created_at NULLS LAST, id""",
        resource_type,
        ctx.project_id,
    )
    items: list[dict[str, object]] = []
    for row in rows:
        data = row["data"] if isinstance(row["data"], dict) else _json.loads(row["data"] or "{}")
        item = {"id": str(row["id"]), "name": row["name"], **data}
        item["id"] = str(row["id"])
        items.append(item)
    return {key: items}
