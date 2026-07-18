"""Ironic Bare Metal API v1."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Ironic"])


def _node(row: Any) -> dict[str, Any]:
    props = row["properties"]
    if isinstance(props, str):
        props = json.loads(props)
    return {
        "id": str(row["id"]),
        "uuid": str(row["id"]),
        "name": row["name"],
        "driver": row["driver"],
        "provision_state": row["provision_state"],
        "power_state": row["power_state"],
        "resource_class": row["resource_class"],
        "properties": props or {},
        "driver_info": row["driver_info"]
        if not isinstance(row["driver_info"], str)
        else json.loads(row["driver_info"]),
        "ports": row["ports"] if not isinstance(row["ports"], str) else json.loads(row["ports"]),
        "maintenance": False,
        "links": [{"rel": "self", "href": f"/v1/nodes/{row['id']}"}],
    }


@router.get("/v1")
@router.get("/v1/")
async def ironic_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="ironic", resource_type="discovery_version", name="default"
    )


@router.get("/v1/nodes")
async def list_nodes(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(await conn.fetch("SELECT * FROM os_nodes ORDER BY name, id"))
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"nodes": [_node(r) for r in page]}
    if links:
        body["nodes_links"] = links
    return body


@router.post("/v1/nodes", status_code=201)
async def create_node(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    payload = await request.json()
    defaults = (
        await fetch_doc(conn, service="ironic", resource_type="node_defaults", name="default") or {}
    )
    props = (
        payload.get("properties")
        if isinstance(payload.get("properties"), dict)
        else defaults.get("properties")
    )
    if not isinstance(props, dict):
        props = {}
    row = await conn.fetchrow(
        """INSERT INTO os_nodes(id, name, driver, provision_state, power_state, resource_class, properties, driver_info, ports)
           VALUES($1,$2,$3,'available','power off',$4,$5::jsonb,$6::jsonb,'[]'::jsonb) RETURNING *""",
        uuid4(),
        payload.get("name") or f"node-{uuid4().hex[:8]}",
        payload.get("driver") or defaults.get("driver"),
        payload.get("resource_class") or defaults.get("resource_class"),
        json.dumps(props),
        json.dumps(payload.get("driver_info") or {}),
    )
    return _node(row)


@router.get("/v1/nodes/{node_id}")
async def show_node(
    node_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    row = await conn.fetchrow("SELECT * FROM os_nodes WHERE id::text=$1 OR name=$1", node_id)
    if row is None:
        raise OpenStackError("NotFound", "Node not found", status_code=404)
    return _node(row)


async def _update_node(
    resource_id: str,
    request: Request,
    conn: Connection,
) -> dict[str, Any]:
    payload = await request.json()
    row = await conn.fetchrow(
        """UPDATE os_nodes
           SET name = COALESCE($1, name), updated_at = now()
           WHERE id::text = $2 OR name = $2
           RETURNING *""",
        payload.get("name"),
        resource_id,
    )
    if row is None:
        raise OpenStackError("NotFound", "Node not found", status_code=404)
    return _node(row)


@router.put("/v1/nodes/{node_id}")
@router.patch("/v1/nodes/{node_id}")
async def update_node(
    node_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    return await _update_node(node_id, request, conn)


@router.put("/v1/nodes/{id}")
@router.patch("/v1/nodes/{id}")
async def update_node_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    return await _update_node(id, request, conn)


@router.delete("/v1/nodes/{node_id}", status_code=204)
async def delete_node(
    node_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    result = await conn.execute("DELETE FROM os_nodes WHERE id::text=$1 OR name=$1", node_id)
    if result.endswith("0"):
        raise OpenStackError("NotFound", "Node not found", status_code=404)
    return Response(status_code=204)


@router.put("/v1/nodes/{node_id}/states/provision")
@router.put("/v1/nodes/{node_id}/states/power")
async def node_state(
    node_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> Response:
    from app.openstack.db_docs import fetch_doc

    payload = await request.json()
    target = payload.get("target") or payload.get("state")
    defaults = (
        await fetch_doc(conn, service="ironic", resource_type="node_defaults", name="default") or {}
    )
    row = await conn.fetchrow("SELECT id FROM os_nodes WHERE id::text=$1 OR name=$1", node_id)
    if row is None:
        raise OpenStackError("NotFound", "Node not found", status_code=404)
    if "power" in request.url.path:
        await conn.execute(
            "UPDATE os_nodes SET power_state=$1, updated_at=now() WHERE id=$2",
            target or defaults.get("power_state"),
            row["id"],
        )
    else:
        await conn.execute(
            "UPDATE os_nodes SET provision_state=$1, updated_at=now() WHERE id=$2",
            target or defaults.get("provision_state"),
            row["id"],
        )
    return Response(status_code=202)


@router.get("/v1/drivers")
async def list_drivers(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    import json as _json

    rows = await conn.fetch(
        """SELECT id, name, data FROM os_api_objects
           WHERE service='ironic' AND resource_type='driver'
           ORDER BY created_at NULLS LAST, name"""
    )
    drivers: list[dict[str, object]] = []
    for row in rows:
        data = row["data"] if isinstance(row["data"], dict) else _json.loads(row["data"] or "{}")
        drivers.append(
            {
                "name": row["name"] or data.get("name"),
                "hosts": list(data.get("hosts") or []),
                "type": data.get("type"),
            }
        )
    return {"drivers": drivers}


@router.get("/v1/nodes/{node_ident}/states")
async def node_states(
    node_ident: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT power_state, provision_state FROM os_nodes WHERE id::text=$1 OR name=$1",
        node_ident,
    )
    if row is None:
        raise OpenStackError("NotFound", f"node {node_ident} not found", status_code=404)
    return {
        "power": row["power_state"],
        "provision": row["provision_state"],
        "raid": None,
        "console": False,
        "boot_mode": None,
    }


@router.get("/v1/nodes/{node_ident}/vendor_passthru")
async def node_vendor_passthru(
    node_ident: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    exists = await conn.fetchval(
        "SELECT 1 FROM os_nodes WHERE id::text=$1 OR name=$1",
        node_ident,
    )
    if not exists:
        raise OpenStackError("NotFound", f"node {node_ident} not found", status_code=404)
    row = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='ironic' AND resource_type='vendor_passthru'
             AND (name=$1 OR data->>'node_id'=$1 OR data->>'node_uuid'=$1)
           ORDER BY updated_at DESC LIMIT 1""",
        node_ident,
    )
    if row is not None:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        methods = (data or {}).get("methods") or (data or {}).get("vendor_passthru") or data
        if isinstance(methods, dict) and methods:
            return {"vendor_passthru": methods}
        return {"vendor_passthru": {"heartbeat": {"http_methods": ["POST"], "async": True}}}
    # Persist empty methods doc so subsequent GETs are DB-backed.
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'ironic','vendor_passthru',NULL,$2,'ACTIVE',$3::jsonb)
           ON CONFLICT (id) DO NOTHING""",
        uuid4(),
        node_ident,
        json.dumps({"node_id": node_ident, "methods": {}}),
    )
    return {"vendor_passthru": {"heartbeat": {"http_methods": ["POST"], "async": True}}}
