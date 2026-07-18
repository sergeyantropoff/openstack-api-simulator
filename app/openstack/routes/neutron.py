"""Neutron Networking API v2.0 (lab subset)."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Neutron"])


def _net(row: Any) -> dict[str, Any]:
    # Lab convention: shared network named "public" is the external provider net.
    name = str(row["name"] or "")
    is_external = bool(row["shared"]) and name == "public"
    return {
        "id": str(row["id"]),
        "name": name,
        "status": row["status"],
        "shared": row["shared"],
        "admin_state_up": row["admin_state_up"],
        "tenant_id": str(row["project_id"]),
        "project_id": str(row["project_id"]),
        "router:external": is_external,
        "provider:network_type": "flat" if is_external else "vxlan",
        "mtu": 1500 if is_external else 1450,
    }


def _subnet(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "network_id": str(row["network_id"]),
        "tenant_id": str(row["project_id"]),
        "project_id": str(row["project_id"]),
        "ip_version": row["ip_version"],
        "cidr": row["cidr"],
        "gateway_ip": row["gateway_ip"],
        "enable_dhcp": True,
        "allocation_pools": [],
        "dns_nameservers": ["8.8.8.8"],
        "host_routes": [],
    }


def _port(row: Any) -> dict[str, Any]:
    fixed = row["fixed_ips"]
    if isinstance(fixed, str):
        fixed = json.loads(fixed)
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "admin_state_up": True,
        "network_id": str(row["network_id"]),
        "tenant_id": str(row["project_id"]),
        "project_id": str(row["project_id"]),
        "mac_address": row["mac_address"],
        "device_id": row["device_id"],
        "device_owner": row["device_owner"],
        "fixed_ips": fixed or [],
    }


def _router(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "admin_state_up": row["admin_state_up"],
        "project_id": str(row["project_id"]),
        "tenant_id": str(row["project_id"]),
        "external_gateway_info": row["external_gateway_info"],
    }


def _floatingip(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "floating_ip_address": row["floating_ip_address"],
        "floating_network_id": str(row["floating_network_id"])
        if row["floating_network_id"]
        else None,
        "port_id": str(row["port_id"]) if row["port_id"] else None,
        "fixed_ip_address": row["fixed_ip_address"],
        "status": row["status"],
        "project_id": str(row["project_id"]),
        "tenant_id": str(row["project_id"]),
    }


async def _security_group(conn: Connection, row: Any) -> dict[str, Any]:
    rules = await conn.fetch(
        "SELECT * FROM os_security_group_rules WHERE security_group_id=$1", row["id"]
    )
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "project_id": str(row["project_id"]),
        "tenant_id": str(row["project_id"]),
        "security_group_rules": [
            {
                "id": str(rule["id"]),
                "direction": rule["direction"],
                "ethertype": rule["ethertype"],
                "protocol": rule["protocol"],
                "port_range_min": rule["port_range_min"],
                "port_range_max": rule["port_range_max"],
                "remote_ip_prefix": rule["remote_ip_prefix"],
                "security_group_id": str(row["id"]),
            }
            for rule in rules
        ],
    }


@router.get("/v2.0")
@router.get("/v2.0/")
async def neutron_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="neutron", resource_type="discovery_version", name="default"
    )


@router.get("/v2.0/networks")
async def list_networks(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    name = request.query_params.get("name")
    net_id = request.query_params.get("id")
    clauses = ["(project_id = $1 OR shared = true)"]
    args: list[object] = [ctx.project_id]
    if name:
        args.append(name)
        clauses.append(f"name = ${len(args)}")
    if net_id:
        args.append(net_id)
        clauses.append(f"id::text = ${len(args)}")
    sql = f"""SELECT * FROM os_networks
              WHERE {" AND ".join(clauses)}
              ORDER BY created_at, id"""
    rows = list(await conn.fetch(sql, *args))
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"networks": [_net(r) for r in page]}
    if links:
        body["networks_links"] = links
    return body


@router.post("/v2.0/networks", status_code=201)
async def create_network(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    payload = (await request.json()).get("network") or {}
    defaults = (
        await fetch_doc(conn, service="neutron", resource_type="network_defaults", name="default")
        or {}
    )
    net_id = uuid4()
    row = await conn.fetchrow(
        """INSERT INTO os_networks(id, project_id, name, status, shared, admin_state_up)
           VALUES($1, $2, $3, 'ACTIVE', $4, $5) RETURNING *""",
        net_id,
        ctx.project_id,
        payload.get("name") or defaults.get("name") or "net",
        bool(payload.get("shared", False)),
        bool(payload.get("admin_state_up", True)),
    )
    return {"network": _net(row)}


@router.get("/v2.0/networks/{network_id}")
async def show_network(
    network_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        """SELECT * FROM os_networks
           WHERE (id::text = $1 OR name = $1)
             AND (project_id = $2 OR shared = true)
           ORDER BY CASE WHEN id::text = $1 THEN 0 ELSE 1 END
           LIMIT 1""",
        network_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NetworkNotFound", "Network not found", status_code=404)
    return {"network": _net(row)}


@router.get("/v2.0/networks/{id}")
async def show_network_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_network(id, conn, ctx)


async def _update_network(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("network") or {}
    row = await conn.fetchrow(
        """UPDATE os_networks
           SET name = COALESCE($1, name),
               shared = COALESCE($2, shared),
               admin_state_up = COALESCE($3, admin_state_up)
           WHERE id = $4::uuid AND (project_id = $5 OR shared = true)
           RETURNING *""",
        payload.get("name"),
        payload.get("shared"),
        payload.get("admin_state_up"),
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NetworkNotFound", "Network not found", status_code=404)
    return {"network": _net(row)}


@router.put("/v2.0/networks/{network_id}")
@router.patch("/v2.0/networks/{network_id}")
async def update_network(
    network_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_network(network_id, request, conn, ctx)


@router.put("/v2.0/networks/{id}")
@router.patch("/v2.0/networks/{id}")
async def update_network_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_network(id, request, conn, ctx)


@router.delete("/v2.0/networks/{network_id}", status_code=204)
async def delete_network(
    network_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_networks WHERE id = $1::uuid AND project_id = $2",
        network_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("NetworkNotFound", "Network not found", status_code=404)
    return Response(status_code=204)


@router.get("/v2.0/subnets")
async def list_subnets(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(
        await conn.fetch(
            "SELECT * FROM os_subnets WHERE project_id = $1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"subnets": [_subnet(r) for r in page]}
    if links:
        body["subnets_links"] = links
    return body


@router.post("/v2.0/subnets", status_code=201)
async def create_subnet(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    payload = (await request.json()).get("subnet") or {}
    network_id = payload.get("network_id")
    cidr = payload.get("cidr")
    if not network_id or not cidr:
        raise OpenStackError("BadRequest", "network_id and cidr are required", status_code=400)
    net = await conn.fetchrow(
        "SELECT id FROM os_networks WHERE id = $1::uuid AND project_id = $2",
        network_id,
        ctx.project_id,
    )
    if net is None:
        raise OpenStackError("NetworkNotFound", "Network not found", status_code=404)
    row = await conn.fetchrow(
        """INSERT INTO os_subnets(id, network_id, project_id, name, cidr, ip_version, gateway_ip)
           VALUES($1, $2, $3, $4, $5, $6, $7) RETURNING *""",
        uuid4(),
        net["id"],
        ctx.project_id,
        payload.get("name") or "",
        cidr,
        int(payload.get("ip_version") or 4),
        payload.get("gateway_ip"),
    )
    return {"subnet": _subnet(row)}


@router.get("/v2.0/subnets/{subnet_id}")
async def show_subnet(
    subnet_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_subnets WHERE id = $1::uuid AND project_id = $2",
        subnet_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("SubnetNotFound", "Subnet not found", status_code=404)
    return {"subnet": _subnet(row)}


@router.get("/v2.0/subnets/{id}")
async def show_subnet_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_subnet(id, conn, ctx)


async def _update_subnet(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("subnet") or {}
    row = await conn.fetchrow(
        """UPDATE os_subnets
           SET name = COALESCE($1, name),
               gateway_ip = COALESCE($2, gateway_ip)
           WHERE id = $3::uuid AND project_id = $4
           RETURNING *""",
        payload.get("name"),
        payload.get("gateway_ip"),
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("SubnetNotFound", "Subnet not found", status_code=404)
    return {"subnet": _subnet(row)}


@router.put("/v2.0/subnets/{subnet_id}")
@router.patch("/v2.0/subnets/{subnet_id}")
async def update_subnet(
    subnet_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_subnet(subnet_id, request, conn, ctx)


@router.put("/v2.0/subnets/{id}")
@router.patch("/v2.0/subnets/{id}")
async def update_subnet_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_subnet(id, request, conn, ctx)


async def _delete_subnet(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_subnets WHERE id = $1::uuid AND project_id = $2",
        resource_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("SubnetNotFound", "Subnet not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2.0/subnets/{subnet_id}", status_code=204)
async def delete_subnet(
    subnet_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_subnet(subnet_id, conn, ctx)


@router.delete("/v2.0/subnets/{id}", status_code=204)
async def delete_subnet_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_subnet(id, conn, ctx)


@router.get("/v2.0/ports")
async def list_ports(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(
        await conn.fetch(
            "SELECT * FROM os_ports WHERE project_id = $1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"ports": [_port(r) for r in page]}
    if links:
        body["ports_links"] = links
    return body


@router.post("/v2.0/ports", status_code=201)
async def create_port(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    payload = (await request.json()).get("port") or {}
    network_id = payload.get("network_id")
    if not network_id:
        raise OpenStackError("BadRequest", "network_id is required", status_code=400)
    port_id = uuid4()
    mac = (
        payload.get("mac_address")
        or f"fa:16:3e:{port_id.hex[0:2]}:{port_id.hex[2:4]}:{port_id.hex[4:6]}"
    )
    fixed = payload.get("fixed_ips") or [
        {"ip_address": f"10.0.0.{(port_id.int % 200) + 30}", "subnet_id": None}
    ]
    row = await conn.fetchrow(
        """INSERT INTO os_ports(id, network_id, project_id, name, status, mac_address,
               device_id, device_owner, fixed_ips)
           VALUES($1, $2::uuid, $3, $4, 'ACTIVE', $5, $6, $7, $8::jsonb)
           RETURNING *""",
        port_id,
        network_id,
        ctx.project_id,
        payload.get("name") or "",
        mac,
        payload.get("device_id") or "",
        payload.get("device_owner") or "",
        json.dumps(fixed),
    )
    return {"port": _port(row)}


@router.get("/v2.0/ports/{port_id}")
async def show_port(
    port_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_ports WHERE id = $1::uuid AND project_id = $2",
        port_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("PortNotFound", "Port not found", status_code=404)
    return {"port": _port(row)}


@router.get("/v2.0/ports/{id}")
async def show_port_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_port(id, conn, ctx)


async def _update_port(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("port") or {}
    fixed_ips = payload.get("fixed_ips")
    row = await conn.fetchrow(
        """UPDATE os_ports
           SET name = COALESCE($1, name),
               device_id = COALESCE($2, device_id),
               device_owner = COALESCE($3, device_owner),
               fixed_ips = COALESCE($4::jsonb, fixed_ips)
           WHERE id = $5::uuid AND project_id = $6
           RETURNING *""",
        payload.get("name"),
        payload.get("device_id"),
        payload.get("device_owner"),
        json.dumps(fixed_ips) if fixed_ips is not None else None,
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("PortNotFound", "Port not found", status_code=404)
    return {"port": _port(row)}


@router.put("/v2.0/ports/{port_id}")
@router.patch("/v2.0/ports/{port_id}")
async def update_port(
    port_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_port(port_id, request, conn, ctx)


@router.put("/v2.0/ports/{id}")
@router.patch("/v2.0/ports/{id}")
async def update_port_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_port(id, request, conn, ctx)


async def _delete_port(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_ports WHERE id = $1::uuid AND project_id = $2",
        resource_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("PortNotFound", "Port not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2.0/ports/{port_id}", status_code=204)
async def delete_port(
    port_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_port(port_id, conn, ctx)


@router.delete("/v2.0/ports/{id}", status_code=204)
async def delete_port_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_port(id, conn, ctx)


# ---- Expanded Neutron surface ----


@router.get("/v2.0/routers")
async def list_routers(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(
        await conn.fetch(
            "SELECT * FROM os_routers WHERE project_id=$1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {
        "routers": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "status": r["status"],
                "admin_state_up": r["admin_state_up"],
                "project_id": str(r["project_id"]),
                "tenant_id": str(r["project_id"]),
                "external_gateway_info": r["external_gateway_info"],
            }
            for r in page
        ]
    }
    if links:
        body["routers_links"] = links
    return body


@router.post("/v2.0/routers", status_code=201)
async def create_router(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from uuid import uuid4

    from app.openstack.db_docs import fetch_doc

    payload = (await request.json()).get("router") or {}
    defaults = (
        await fetch_doc(conn, service="neutron", resource_type="router_defaults", name="default")
        or {}
    )
    row = await conn.fetchrow(
        """INSERT INTO os_routers(id, project_id, name, status, admin_state_up, external_gateway_info)
           VALUES($1,$2,$3,'ACTIVE',$4,$5::jsonb) RETURNING *""",
        uuid4(),
        ctx.project_id,
        payload.get("name") or defaults.get("name") or "router",
        bool(payload.get("admin_state_up", True)),
        (
            __import__("json").dumps(payload.get("external_gateway_info"))
            if payload.get("external_gateway_info")
            else None
        ),
    )
    return {
        "router": {
            "id": str(row["id"]),
            "name": row["name"],
            "status": row["status"],
            "admin_state_up": row["admin_state_up"],
            "project_id": str(row["project_id"]),
            "tenant_id": str(row["project_id"]),
            "external_gateway_info": row["external_gateway_info"],
        }
    }


@router.get("/v2.0/routers/{router_id}")
async def show_router(
    router_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_routers WHERE id::text = $1 AND project_id = $2",
        router_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("RouterNotFound", "Router not found", status_code=404)
    return {"router": _router(row)}


@router.get("/v2.0/routers/{id}")
async def show_router_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_router(id, conn, ctx)


async def _update_router(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("router") or {}
    ext_gw = payload.get("external_gateway_info")
    row = await conn.fetchrow(
        """UPDATE os_routers
           SET name = COALESCE($1, name),
               admin_state_up = COALESCE($2, admin_state_up),
               external_gateway_info = COALESCE($3::jsonb, external_gateway_info)
           WHERE id::text = $4 AND project_id = $5
           RETURNING *""",
        payload.get("name"),
        payload.get("admin_state_up"),
        json.dumps(ext_gw) if ext_gw is not None else None,
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Router {resource_id} not found", status_code=404)
    return {"router": _router(row)}


@router.put("/v2.0/routers/{router_id}")
@router.patch("/v2.0/routers/{router_id}")
async def update_router(
    router_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_router(router_id, request, conn, ctx)


@router.put("/v2.0/routers/{id}")
@router.patch("/v2.0/routers/{id}")
async def update_router_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_router(id, request, conn, ctx)


async def _delete_router(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_routers WHERE id::text = $1 AND project_id = $2",
        resource_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("RouterNotFound", "Router not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2.0/routers/{router_id}", status_code=204)
async def delete_router(
    router_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_router(router_id, conn, ctx)


@router.delete("/v2.0/routers/{id}", status_code=204)
async def delete_router_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_router(id, conn, ctx)


@router.get("/v2.0/security-groups")
async def list_security_groups(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(
        await conn.fetch(
            "SELECT * FROM os_security_groups WHERE project_id=$1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    result = []
    for r in page:
        rules = await conn.fetch(
            "SELECT * FROM os_security_group_rules WHERE security_group_id=$1", r["id"]
        )
        result.append(
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r["description"],
                "project_id": str(r["project_id"]),
                "tenant_id": str(r["project_id"]),
                "security_group_rules": [
                    {
                        "id": str(rule["id"]),
                        "direction": rule["direction"],
                        "ethertype": rule["ethertype"],
                        "protocol": rule["protocol"],
                        "port_range_min": rule["port_range_min"],
                        "port_range_max": rule["port_range_max"],
                        "remote_ip_prefix": rule["remote_ip_prefix"],
                        "security_group_id": str(r["id"]),
                    }
                    for rule in rules
                ],
            }
        )
    body: dict[str, object] = {"security_groups": result}
    if links:
        body["security_groups_links"] = links
    return body


@router.post("/v2.0/security-groups", status_code=201)
async def create_security_group(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from uuid import uuid4

    from app.openstack.db_docs import fetch_doc

    payload = (await request.json()).get("security_group") or {}
    defaults = (
        await fetch_doc(
            conn, service="neutron", resource_type="security_group_defaults", name="default"
        )
        or {}
    )
    sg_name = str(payload.get("name") or defaults.get("name") or "default")
    sg_id = uuid4()
    await conn.execute(
        """INSERT INTO os_security_groups(id, project_id, name, description)
           VALUES($1,$2,$3,$4)""",
        sg_id,
        ctx.project_id,
        sg_name,
        payload.get("description") or "",
    )
    return {
        "security_group": {
            "id": str(sg_id),
            "name": sg_name,
            "description": payload.get("description") or "",
            "project_id": str(ctx.project_id),
            "tenant_id": str(ctx.project_id),
            "security_group_rules": [],
        }
    }


@router.get("/v2.0/security-groups/{security_group_id}")
async def show_security_group(
    security_group_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_security_groups WHERE id::text = $1 AND project_id = $2",
        security_group_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("SecurityGroupNotFound", "Security group not found", status_code=404)
    return {"security_group": await _security_group(conn, row)}


@router.get("/v2.0/security-groups/{id}")
async def show_security_group_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_security_group(id, conn, ctx)


async def _update_security_group(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("security_group") or {}
    row = await conn.fetchrow(
        """UPDATE os_security_groups
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
        raise OpenStackError("SecurityGroupNotFound", "Security group not found", status_code=404)
    return {"security_group": await _security_group(conn, row)}


@router.put("/v2.0/security-groups/{security_group_id}")
@router.patch("/v2.0/security-groups/{security_group_id}")
async def update_security_group(
    security_group_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_security_group(security_group_id, request, conn, ctx)


@router.put("/v2.0/security-groups/{id}")
@router.patch("/v2.0/security-groups/{id}")
async def update_security_group_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_security_group(id, request, conn, ctx)


async def _delete_security_group(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_security_groups WHERE id::text = $1 AND project_id = $2",
        resource_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("SecurityGroupNotFound", "Security group not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2.0/security-groups/{security_group_id}", status_code=204)
async def delete_security_group(
    security_group_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_security_group(security_group_id, conn, ctx)


@router.delete("/v2.0/security-groups/{id}", status_code=204)
async def delete_security_group_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_security_group(id, conn, ctx)


def _security_group_rule(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "direction": row["direction"],
        "ethertype": row["ethertype"],
        "protocol": row["protocol"],
        "port_range_min": row["port_range_min"],
        "port_range_max": row["port_range_max"],
        "remote_ip_prefix": row["remote_ip_prefix"],
        "security_group_id": str(row["security_group_id"]),
        "project_id": str(row["project_id"]),
        "tenant_id": str(row["project_id"]),
    }


@router.get("/v2.0/security-group-rules")
async def list_sg_rules(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch(
        "SELECT * FROM os_security_group_rules WHERE project_id=$1", ctx.project_id
    )
    return {"security_group_rules": [_security_group_rule(r) for r in rows]}


@router.post("/v2.0/security-group-rules", status_code=201)
async def create_sg_rule(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from uuid import uuid4

    payload = (await request.json()).get("security_group_rule") or {}
    sg_id = payload.get("security_group_id")
    if not sg_id:
        sg_id = await conn.fetchval(
            """SELECT id FROM os_security_groups
               WHERE project_id=$1 ORDER BY name LIMIT 1""",
            ctx.project_id,
        )
    if not sg_id:
        raise OpenStackError(
            "BadRequest",
            "security_group_id is required",
            status_code=400,
        )
    # Validate parent exists (invalid UUID / missing group → 404, not 500).
    exists = await conn.fetchval(
        "SELECT 1 FROM os_security_groups WHERE id=$1::uuid AND project_id=$2",
        sg_id,
        ctx.project_id,
    )
    if not exists:
        raise OpenStackError("SecurityGroupNotFound", "Security group not found", status_code=404)
    from app.openstack.db_docs import fetch_doc

    rule_defaults = (
        await fetch_doc(
            conn, service="neutron", resource_type="security_group_rule_defaults", name="default"
        )
        or {}
    )
    rule_id = uuid4()
    direction = payload.get("direction") or rule_defaults.get("direction") or "ingress"
    ethertype = payload.get("ethertype") or rule_defaults.get("ethertype") or "IPv4"
    protocol = payload.get("protocol")
    port_min = payload.get("port_range_min")
    port_max = payload.get("port_range_max")
    remote = payload.get("remote_ip_prefix")
    await conn.execute(
        """INSERT INTO os_security_group_rules(
               id, security_group_id, project_id, direction, ethertype, protocol,
               port_range_min, port_range_max, remote_ip_prefix)
           VALUES($1,$2::uuid,$3,$4,$5,$6,$7,$8,$9)""",
        rule_id,
        sg_id,
        ctx.project_id,
        direction,
        ethertype,
        protocol,
        port_min,
        port_max,
        remote,
    )
    return {
        "security_group_rule": {
            "id": str(rule_id),
            "security_group_id": str(sg_id),
            "direction": direction,
            "ethertype": ethertype,
            "protocol": protocol,
            "port_range_min": port_min,
            "port_range_max": port_max,
            "remote_ip_prefix": remote,
            "project_id": str(ctx.project_id),
            "tenant_id": str(ctx.project_id),
        }
    }


@router.get("/v2.0/security-group-rules/{security_group_rule_id}")
async def show_sg_rule(
    security_group_rule_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_security_group_rules WHERE id::text = $1 AND project_id = $2",
        security_group_rule_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError(
            "SecurityGroupRuleNotFound", "Security group rule not found", status_code=404
        )
    return {"security_group_rule": _security_group_rule(row)}


@router.get("/v2.0/security-group-rules/{id}")
async def show_sg_rule_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_sg_rule(id, conn, ctx)


async def _delete_sg_rule(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_security_group_rules WHERE id::text = $1 AND project_id = $2",
        resource_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError(
            "SecurityGroupRuleNotFound", "Security group rule not found", status_code=404
        )
    return Response(status_code=204)


@router.delete("/v2.0/security-group-rules/{security_group_rule_id}", status_code=204)
async def delete_sg_rule(
    security_group_rule_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_sg_rule(security_group_rule_id, conn, ctx)


@router.delete("/v2.0/security-group-rules/{id}", status_code=204)
async def delete_sg_rule_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_sg_rule(id, conn, ctx)


@router.put("/v2.0/routers/{router_id}/add_router_interface")
async def add_router_interface(
    router_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    import json
    from uuid import uuid4

    payload = await request.json()
    subnet_id = payload.get("subnet_id")
    port_id = payload.get("port_id")
    row = await conn.fetchrow(
        "SELECT * FROM os_routers WHERE id::text=$1 AND project_id=$2",
        router_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Router {router_id} not found", status_code=404)

    network_id: str | None = None
    if subnet_id:
        subnet = await conn.fetchrow(
            "SELECT * FROM os_subnets WHERE id::text=$1 AND project_id=$2",
            str(subnet_id),
            ctx.project_id,
        )
        if subnet is None:
            raise OpenStackError("NotFound", f"Subnet {subnet_id} not found", status_code=404)
        network_id = str(subnet["network_id"])

    # Provider waits on GET /ports/{port_id} → ACTIVE|DOWN; must be a real port.
    if not port_id:
        if not network_id:
            raise OpenStackError("BadRequest", "subnet_id or port_id required", status_code=400)
        new_port_id = uuid4()
        mac = f"fa:16:3e:{new_port_id.hex[0:2]}:{new_port_id.hex[2:4]}:{new_port_id.hex[4:6]}"
        fixed = [
            {"subnet_id": str(subnet_id), "ip_address": f"10.88.0.{(new_port_id.int % 200) + 1}"}
        ]
        await conn.execute(
            """INSERT INTO os_ports(id, network_id, project_id, name, status, mac_address,
                   device_id, device_owner, fixed_ips)
               VALUES($1, $2::uuid, $3, $4, 'ACTIVE', $5, $6, 'network:router_interface', $7::jsonb)""",
            new_port_id,
            network_id,
            ctx.project_id,
            f"router-interface-{router_id[:8]}",
            mac,
            router_id,
            json.dumps(fixed),
        )
        port_id = str(new_port_id)
    else:
        existing = await conn.fetchrow(
            "SELECT * FROM os_ports WHERE id = $1::uuid AND project_id = $2",
            str(port_id),
            ctx.project_id,
        )
        if existing is None:
            raise OpenStackError("PortNotFound", "Port not found", status_code=404)
        network_id = str(existing["network_id"])
        await conn.execute(
            """UPDATE os_ports
               SET device_id=$1, device_owner='network:router_interface', status='ACTIVE'
               WHERE id=$2::uuid AND project_id=$3""",
            router_id,
            str(port_id),
            ctx.project_id,
        )

    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1::uuid,'neutron','router_interface',$2,$3,'ACTIVE',$4::jsonb)
           ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()""",
        port_id,
        ctx.project_id,
        f"rif-{router_id[:8]}",
        json.dumps(
            {
                "id": str(port_id),
                "router_id": router_id,
                "subnet_id": subnet_id,
                "port_id": str(port_id),
                "network_id": network_id,
                "tenant_id": str(ctx.project_id),
                "project_id": str(ctx.project_id),
            }
        ),
    )
    return {
        "id": router_id,
        "subnet_id": subnet_id,
        "port_id": str(port_id),
        "tenant_id": str(ctx.project_id),
        "project_id": str(ctx.project_id),
        "network_id": network_id,
    }


@router.put("/v2.0/routers/{router_id}/remove_router_interface")
async def remove_router_interface(
    router_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    payload = await request.json()
    port_id = payload.get("port_id")
    subnet_id = payload.get("subnet_id")
    row = await conn.fetchrow(
        "SELECT * FROM os_routers WHERE id::text=$1 AND project_id=$2",
        router_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Router {router_id} not found", status_code=404)

    # Resolve port_id from subnet when only subnet_id is provided.
    if not port_id and subnet_id:
        iface = await conn.fetchrow(
            """SELECT id, data FROM os_api_objects
               WHERE service='neutron' AND resource_type='router_interface'
                 AND project_id=$1
                 AND data->>'router_id'=$2
                 AND data->>'subnet_id'=$3
               LIMIT 1""",
            ctx.project_id,
            router_id,
            str(subnet_id),
        )
        if iface is not None:
            port_id = str(iface["id"])

    if port_id:
        await conn.execute(
            """DELETE FROM os_api_objects
               WHERE service='neutron' AND resource_type='router_interface'
                 AND id::text=$1 AND project_id=$2""",
            str(port_id),
            ctx.project_id,
        )
        # Provider polls until port is gone (404 → DELETED).
        await conn.execute(
            "DELETE FROM os_ports WHERE id=$1::uuid AND project_id=$2",
            str(port_id),
            ctx.project_id,
        )
    elif subnet_id:
        await conn.execute(
            """DELETE FROM os_api_objects
               WHERE service='neutron' AND resource_type='router_interface'
                 AND project_id=$1
                 AND data->>'router_id'=$2
                 AND data->>'subnet_id'=$3""",
            ctx.project_id,
            router_id,
            str(subnet_id),
        )
        await conn.execute(
            """DELETE FROM os_ports
               WHERE project_id=$1 AND device_id=$2
                 AND device_owner='network:router_interface'
                 AND fixed_ips @> $3::jsonb""",
            ctx.project_id,
            router_id,
            json.dumps([{"subnet_id": str(subnet_id)}]),
        )
    return {
        "id": router_id,
        "tenant_id": str(ctx.project_id),
        "project_id": str(ctx.project_id),
        "port_id": str(port_id) if port_id else None,
        "subnet_id": subnet_id,
    }


@router.get("/v2.0/floatingips")
async def list_floating_ips(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    rows = list(
        await conn.fetch(
            "SELECT * FROM os_floating_ips WHERE project_id=$1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {
        "floatingips": [
            {
                "id": str(r["id"]),
                "floating_ip_address": r["floating_ip_address"],
                "floating_network_id": str(r["floating_network_id"])
                if r["floating_network_id"]
                else None,
                "port_id": str(r["port_id"]) if r["port_id"] else None,
                "fixed_ip_address": r["fixed_ip_address"],
                "status": r["status"],
                "project_id": str(r["project_id"]),
                "tenant_id": str(r["project_id"]),
            }
            for r in page
        ]
    }
    if links:
        body["floatingips_links"] = links
    return body


@router.post("/v2.0/floatingips", status_code=201)
async def create_floating_ip(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from uuid import uuid4

    payload = (await request.json()).get("floatingip") or {}
    fip_id = uuid4()
    addr = payload.get("floating_ip_address") or f"203.0.113.{(fip_id.int % 200) + 10}"
    await conn.execute(
        """INSERT INTO os_floating_ips(id, project_id, floating_ip_address, floating_network_id, port_id, status)
           VALUES($1,$2,$3,$4::uuid,$5::uuid,'DOWN')""",
        fip_id,
        ctx.project_id,
        addr,
        payload.get("floating_network_id"),
        payload.get("port_id"),
    )
    return {
        "floatingip": {
            "id": str(fip_id),
            "floating_ip_address": addr,
            "floating_network_id": payload.get("floating_network_id"),
            "port_id": payload.get("port_id"),
            "status": "DOWN",
            "project_id": str(ctx.project_id),
            "tenant_id": str(ctx.project_id),
        }
    }


@router.get("/v2.0/floatingips/{floatingip_id}")
async def show_floatingip(
    floatingip_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_floating_ips WHERE id::text = $1 AND project_id = $2",
        floatingip_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("FloatingIPNotFound", "Floating IP not found", status_code=404)
    return {"floatingip": _floatingip(row)}


@router.get("/v2.0/floatingips/{id}")
async def show_floatingip_pack_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_floatingip(id, conn, ctx)


async def _update_floatingip(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("floatingip") or {}
    row = await conn.fetchrow(
        """UPDATE os_floating_ips
           SET port_id = COALESCE($1::uuid, port_id),
               fixed_ip_address = COALESCE($2, fixed_ip_address),
               status = COALESCE($3, status)
           WHERE id::text = $4 AND project_id = $5
           RETURNING *""",
        payload.get("port_id"),
        payload.get("fixed_ip_address"),
        payload.get("status"),
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", "Floating IP not found", status_code=404)
    return {"floatingip": _floatingip(row)}


@router.put("/v2.0/floatingips/{floatingip_id}")
@router.patch("/v2.0/floatingips/{floatingip_id}")
async def update_floatingip(
    floatingip_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_floatingip(floatingip_id, request, conn, ctx)


@router.put("/v2.0/floatingips/{id}")
@router.patch("/v2.0/floatingips/{id}")
async def update_floatingip_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_floatingip(id, request, conn, ctx)


async def _delete_floatingip(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_floating_ips WHERE id::text = $1 AND project_id = $2",
        resource_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("FloatingIPNotFound", "Floating IP not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2.0/floatingips/{floatingip_id}", status_code=204)
async def delete_floatingip(
    floatingip_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_floatingip(floatingip_id, conn, ctx)


@router.delete("/v2.0/floatingips/{id}", status_code=204)
async def delete_floatingip_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_floatingip(id, conn, ctx)


@router.get("/v2.0/agents")
async def list_agents(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    import json as _json

    rows = await conn.fetch(
        """SELECT id, name, status, data FROM os_api_objects
           WHERE service='neutron' AND resource_type='agent'
             AND (project_id=$1 OR project_id IS NULL)
           ORDER BY created_at NULLS LAST, id""",
        ctx.project_id,
    )
    agents: list[dict[str, object]] = []
    for row in rows:
        data = row["data"] if isinstance(row["data"], dict) else _json.loads(row["data"] or "{}")
        agents.append(
            {
                "id": str(row["id"]),
                "agent_type": data.get("agent_type") or row["name"],
                "host": data.get("host"),
                "alive": bool(data.get("alive", True)),
                "admin_state_up": bool(data.get("admin_state_up", True)),
                **{k: v for k, v in data.items() if k not in {"id"}},
            }
        )
    return {"agents": agents}


@router.get("/v2.0/qos/policies")
@router.get("/v2.0/trunks")
@router.get("/v2.0/rbac-policies")
@router.get("/v2.0/address-scopes")
@router.get("/v2.0/subnetpools")
async def neutron_extension_collections(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    """Serve Neutron extension collections from demo/schema rows."""

    import json as _json

    leaf = request.url.path.rstrip("/").split("/")[-1]
    # path leaf -> (response_key, resource_type in os_api_objects)
    mapping = {
        "policies": ("policies", "qos_policy"),
        "trunks": ("trunks", "trunk"),
        "rbac-policies": ("rbac_policies", "rbac_policy"),
        "address-scopes": ("address_scopes", "address_scope"),
        "subnetpools": ("subnetpools", "subnetpool"),
    }
    response_key, resource_type = mapping.get(
        leaf, (leaf.replace("-", "_"), leaf.replace("-", "_"))
    )
    rows = await conn.fetch(
        """SELECT id, name, status, data FROM os_api_objects
           WHERE service='neutron' AND resource_type=$1
             AND (project_id=$2 OR project_id IS NULL)
           ORDER BY created_at NULLS LAST, id""",
        resource_type,
        ctx.project_id,
    )
    items: list[dict[str, object]] = []
    for row in rows:
        data = row["data"] if isinstance(row["data"], dict) else _json.loads(row["data"] or "{}")
        item = {
            "id": str(row["id"]),
            "name": row["name"],
            "status": row["status"] or "ACTIVE",
            **data,
        }
        item["id"] = str(row["id"])
        items.append(item)
    return {response_key: items}
