"""Nova Compute API v2.1 (lab subset)."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import UUID, uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Nova"])


def _public_server_metadata(metadata: Any) -> dict[str, str]:
    """Nova metadata is map[string]string; hide internal keys (e.g. _tags)."""
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    if not isinstance(metadata, dict):
        return {}
    public: dict[str, str] = {}
    for key, value in metadata.items():
        if str(key).startswith("_"):
            continue
        if isinstance(value, (list, dict)):
            continue
        public[str(key)] = "" if value is None else str(value)
    return public


def _server_dict(row: Any) -> dict[str, Any]:
    addresses = row["addresses"]
    if isinstance(addresses, str):
        addresses = json.loads(addresses)
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "tenant_id": str(row["project_id"]),
        "user_id": str(row["user_id"]),
        "flavor": {"id": row["flavor_id"]},
        "image": {"id": str(row["image_id"])} if row["image_id"] else "",
        "addresses": addresses or {},
        "metadata": _public_server_metadata(row["metadata"]),
        "created": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated": row["updated_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "OS-EXT-STS:vm_state": "active" if row["status"] == "ACTIVE" else row["status"].lower(),
        "OS-EXT-STS:power_state": 1 if row["status"] == "ACTIVE" else 4,
        "OS-EXT-AZ:availability_zone": row["availability_zone"]
        if "availability_zone" in row.keys()
        else "nova",
        "OS-EXT-SRV-ATTR:host": row["host"] if "host" in row.keys() else None,
        "accessIPv4": "",
        "accessIPv6": "",
        "links": [
            {"rel": "self", "href": f"/v2.1/servers/{row['id']}"},
            {"rel": "bookmark", "href": f"/servers/{row['id']}"},
        ],
    }


@router.get("/v2.1")
@router.get("/v2.1/")
async def nova_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="nova", resource_type="discovery_version", name="default"
    )


@router.get("/v2.1/servers")
@router.get("/v2.1/servers/detail")
async def list_servers(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    detail = request.url.path.rstrip("/").endswith("detail")
    rows = list(
        await conn.fetch(
            """SELECT * FROM os_servers WHERE project_id = $1 ORDER BY created_at, id""",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    if detail:
        body: dict[str, object] = {"servers": [_server_dict(r) for r in page]}
    else:
        body = {
            "servers": [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "links": [{"rel": "self", "href": f"/v2.1/servers/{r['id']}"}],
                }
                for r in page
            ]
        }
    if links:
        body["servers_links"] = links
    return body


async def _show_server(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    # openstacksdk / ansible may probe GET /servers/{name} before create.
    row = await conn.fetchrow(
        """SELECT * FROM os_servers
           WHERE project_id = $2
             AND (id::text = $1 OR name = $1)
           ORDER BY CASE WHEN id::text = $1 THEN 0 ELSE 1 END
           LIMIT 1""",
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError(
            "computeFault",
            f"Instance '{resource_id}' could not be found",
            status_code=404,
        )
    return {"server": _server_dict(row)}


@router.get("/v2.1/servers/{server_id}")
async def show_server(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_server(server_id, conn, ctx)


@router.get("/v2.1/servers/{id}")
async def show_server_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_server(id, conn, ctx)


async def _update_server(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("server") or {}
    row = await conn.fetchrow(
        """UPDATE os_servers
           SET name = COALESCE($1, name), updated_at = now()
           WHERE id = $2::uuid AND project_id = $3
           RETURNING *""",
        payload.get("name"),
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError(
            "computeFault",
            f"Instance '{resource_id}' could not be found",
            status_code=404,
        )
    return {"server": _server_dict(row)}


@router.put("/v2.1/servers/{server_id}")
@router.patch("/v2.1/servers/{server_id}")
async def update_server(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_server(server_id, request, conn, ctx)


@router.put("/v2.1/servers/{id}")
@router.patch("/v2.1/servers/{id}")
async def update_server_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_server(id, request, conn, ctx)


@router.post("/v2.1/servers", status_code=202)
async def create_server(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    payload = await request.json()
    server = payload.get("server") or {}
    server_defaults = (
        await fetch_doc(conn, service="nova", resource_type="server_defaults", name="default") or {}
    )
    name = server.get("name") or server_defaults.get("name") or "instance"
    flavor_ref = str(server.get("flavorRef") or server.get("flavor_id") or "2")
    image_ref = server.get("imageRef") or server.get("image_id")
    flavor = await conn.fetchrow("SELECT id FROM os_flavors WHERE id = $1 OR name = $1", flavor_ref)
    if flavor is None:
        raise OpenStackError(
            "badRequest", f"Flavor {flavor_ref} could not be found", status_code=400
        )
    image_id = None
    if image_ref:
        image = await conn.fetchrow(
            "SELECT id FROM os_images WHERE id::text = $1 OR name = $1", str(image_ref)
        )
        if image is None:
            raise OpenStackError(
                "badRequest", f"Image {image_ref} could not be found", status_code=400
            )
        image_id = image["id"]
    server_id = uuid4()
    net = await conn.fetchrow(
        """SELECT name FROM os_networks
           WHERE project_id=$1 OR project_id IS NULL
           ORDER BY CASE WHEN project_id=$1 THEN 0 ELSE 1 END, created_at
           LIMIT 1""",
        ctx.project_id,
    )
    net_name = str(net["name"]) if net else "private"
    addresses = {
        net_name: [
            {
                "OS-EXT-IPS-MAC:mac_addr": f"fa:16:3e:{server_id.hex[0:2]}:{server_id.hex[2:4]}:{server_id.hex[4:6]}",
                "version": 4,
                "addr": f"10.0.0.{(server_id.int % 200) + 20}",
                "OS-EXT-IPS:type": "fixed",
            }
        ]
    }
    from app.openstack.db_docs import fetch_doc

    meta = server.get("metadata") if isinstance(server.get("metadata"), dict) else None
    if not meta:
        defaults = await fetch_doc(
            conn, service="nova", resource_type="server_metadata_defaults", name="default"
        )
        meta = (defaults or {}).get("metadata") if defaults else {}
        if not isinstance(meta, dict):
            meta = {}
    tag_defaults = await fetch_doc(
        conn, service="nova", resource_type="server_tag_defaults", name="default"
    )
    default_tags = list((tag_defaults or {}).get("tags") or [])
    if default_tags:
        meta = {**meta, "_tags": default_tags}
    row = await conn.fetchrow(
        """INSERT INTO os_servers(id, project_id, user_id, name, status, flavor_id, image_id, addresses, metadata)
           VALUES($1, $2, $3, $4, 'ACTIVE', $5, $6, $7::jsonb, $8::jsonb)
           RETURNING *""",
        server_id,
        ctx.project_id,
        ctx.user_id,
        name,
        flavor["id"],
        image_id,
        json.dumps(addresses),
        json.dumps(meta),
    )
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'nova','instance_action',$2,'create','DONE',$3::jsonb)""",
        uuid4(),
        ctx.project_id,
        json.dumps(
            {
                "action": "create",
                "instance_uuid": str(server_id),
                "server_id": str(server_id),
                "request_id": f"req-{server_id.hex[:12]}",
                "message": None,
            }
        ),
    )
    return {"server": _server_dict(row)}


@router.delete("/v2.1/servers/{server_id}", status_code=204)
async def delete_server(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_servers WHERE id = $1::uuid AND project_id = $2",
        server_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError(
            "computeFault",
            f"Instance '{server_id}' could not be found",
            status_code=404,
        )
    return Response(status_code=204)


@router.post("/v2.1/servers/{server_id}/action")
async def server_action(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    row = await conn.fetchrow(
        "SELECT * FROM os_servers WHERE id = $1::uuid AND project_id = $2",
        server_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError(
            "computeFault",
            f"Instance '{server_id}' could not be found",
            status_code=404,
        )
    from fastapi.responses import JSONResponse

    action = await request.json()
    if not isinstance(action, dict) or not action:
        raise OpenStackError("badRequest", "Action body required", status_code=400)
    name = next(iter(action.keys()))
    if name in {"os-getConsoleOutput"}:
        from app.openstack.db_docs import require_doc

        console_row = await conn.fetchrow(
            """SELECT data FROM os_api_objects
               WHERE service='nova' AND resource_type='console_output'
                 AND (name=$1 OR data->>'server_id'=$1)
               ORDER BY updated_at DESC LIMIT 1""",
            server_id,
        )
        if console_row is not None:
            data = console_row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            output = str((data or {}).get("output") or "")
        else:
            template = await require_doc(
                conn, service="nova", resource_type="console_output_template", name="default"
            )
            output = str(template.get("output") or "")
            await conn.execute(
                """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                   VALUES($1,'nova','console_output',$2,$3,'ACTIVE',$4::jsonb)""",
                uuid4(),
                ctx.project_id,
                server_id,
                json.dumps({"server_id": server_id, "output": output}),
            )
        return JSONResponse({"output": output})
    if name in {"os-getVNCConsole", "os-getSPICEConsole", "os-getRDPConsole", "remote-consoles"}:
        from app.openstack.db_docs import require_doc

        console_row = await conn.fetchrow(
            """SELECT data FROM os_api_objects
               WHERE service='nova' AND resource_type='console'
                 AND (name=$1 OR data->>'server_id'=$1)
               ORDER BY updated_at DESC LIMIT 1""",
            server_id,
        )
        if console_row is not None:
            data = console_row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            console_type = str((data or {}).get("type") or "")
            console_url = str((data or {}).get("url") or "")
        else:
            template = await require_doc(
                conn, service="nova", resource_type="console_template", name="default"
            )
            console_type = str(template.get("type") or "")
            console_url = str(template.get("url") or "").replace("__SERVER_ID__", server_id)
            await conn.execute(
                """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                   VALUES($1,'nova','console',$2,$3,'ACTIVE',$4::jsonb)""",
                uuid4(),
                ctx.project_id,
                server_id,
                json.dumps({"server_id": server_id, "type": console_type, "url": console_url}),
            )
        return JSONResponse({"console": {"type": console_type, "url": console_url}})
    if name == "createImage":
        from uuid import uuid4

        image_id = uuid4()
        body = action.get("createImage") if isinstance(action.get("createImage"), dict) else {}
        image_name = str(body.get("name") or f"snapshot-{server_id[:8]}")
        await conn.execute(
            """INSERT INTO os_images(id, name, status, visibility, size, disk_format,
                   container_format, owner_project_id)
               VALUES($1,$2,'active','private',0,'qcow2','bare',$3)""",
            image_id,
            image_name,
            ctx.project_id,
        )
        return JSONResponse({"image_id": str(image_id)}, status_code=202)

    status_map = {
        "os-start": "ACTIVE",
        "osStart": "ACTIVE",
        "reboot": "ACTIVE",
        "unshelve": "ACTIVE",
        "resume": "ACTIVE",
        "unpause": "ACTIVE",
        "unrescue": "ACTIVE",
        "os-stop": "SHUTOFF",
        "osStop": "SHUTOFF",
        "shelve": "SHELVED",
        "shelveOffload": "SHELVED_OFFLOADED",
        "pause": "PAUSED",
        "suspend": "SUSPENDED",
        "rescue": "RESCUE",
        "resize": "VERIFY_RESIZE",
        "confirmResize": "ACTIVE",
        "revertResize": "ACTIVE",
        "lock": row["status"],
        "unlock": row["status"],
        "rebuild": "ACTIVE",
        "migrate": "MIGRATING",
        "liveMigrate": "MIGRATING",
        "evacuate": "ACTIVE",
        "changePassword": row["status"],
        "addFloatingIp": row["status"],
        "removeFloatingIp": row["status"],
        "addSecurityGroup": row["status"],
        "removeSecurityGroup": row["status"],
        "createBackup": row["status"],
        "resetState": action.get("resetState", {}).get("state", "active").upper(),
        "trigger_crash_dump": row["status"],
    }
    if name not in status_map:
        # Accept unknown actions as 202 no-ops for surface-complete clients.
        return Response(status_code=202)
    status = status_map[name]
    await conn.execute(
        "UPDATE os_servers SET status = $1, updated_at = now() WHERE id = $2",
        status,
        row["id"],
    )
    return Response(status_code=202)


@router.get("/v2.1/flavors")
@router.get("/v2.1/flavors/detail")
async def list_flavors(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    detail = request.url.path.rstrip("/").endswith("detail")
    rows = await conn.fetch("SELECT * FROM os_flavors ORDER BY id")
    if detail:
        return {
            "flavors": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "vcpus": r["vcpus"],
                    "ram": r["ram"],
                    "disk": r["disk"],
                    "OS-FLV-EXT-DATA:ephemeral": 0,
                    "swap": "",
                    "rxtx_factor": 1.0,
                    "os-flavor-access:is_public": r["is_public"],
                }
                for r in rows
            ]
        }
    return {"flavors": [{"id": r["id"], "name": r["name"]} for r in rows]}


async def _show_flavor(
    flavor_id: str,
    conn: Connection,
) -> dict[str, object]:
    r = await conn.fetchrow(
        "SELECT * FROM os_flavors WHERE id::text = $1 OR name = $1",
        flavor_id,
    )
    if r is None:
        raise OpenStackError("computeFault", "Flavor not found", status_code=404)
    return {
        "flavor": {
            "id": r["id"],
            "name": r["name"],
            "vcpus": r["vcpus"],
            "ram": r["ram"],
            "disk": r["disk"],
            "os-flavor-access:is_public": r["is_public"],
        }
    }


@router.post("/v2.1/flavors", status_code=200)
async def create_flavor(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    payload = (await request.json()).get("flavor") or {}
    flavor_id = str(payload.get("id") or uuid4())
    name = str(payload.get("name") or f"flavor-{flavor_id[:8]}")
    await conn.execute(
        """INSERT INTO os_flavors(id, name, vcpus, ram, disk, is_public)
           VALUES($1,$2,$3,$4,$5,$6)
           ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, vcpus=EXCLUDED.vcpus,
             ram=EXCLUDED.ram, disk=EXCLUDED.disk, is_public=EXCLUDED.is_public""",
        flavor_id,
        name,
        int(payload.get("vcpus") or 1),
        int(payload.get("ram") or 512),
        int(payload.get("disk") or 1),
        bool(payload.get("os-flavor-access:is_public", True)),
    )
    return await _show_flavor(flavor_id, conn)


@router.delete("/v2.1/flavors/{flavor_id}", status_code=202)
async def delete_flavor(
    flavor_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute("DELETE FROM os_flavors WHERE id::text=$1 OR name=$1", flavor_id)
    if result.endswith("0"):
        raise OpenStackError("computeFault", "Flavor not found", status_code=404)
    return Response(status_code=202)


@router.delete("/v2.1/flavors/{id}", status_code=202)
async def delete_flavor_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await delete_flavor(id, conn, _ctx)


@router.get("/v2.1/flavors/{flavor_id}")
async def show_flavor(
    flavor_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_flavor(flavor_id, conn)


@router.get("/v2.1/flavors/{id}")
async def show_flavor_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_flavor(id, conn)


# ---- Expanded Nova surface ----


@router.get("/v2.1/os-keypairs")
async def list_keypairs(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch("SELECT * FROM os_keypairs WHERE user_id=$1 ORDER BY name", ctx.user_id)
    return {
        "keypairs": [
            {
                "keypair": {
                    "name": r["name"],
                    "public_key": r["public_key"],
                    "fingerprint": r["fingerprint"],
                    "type": r["type"],
                }
            }
            for r in rows
        ]
    }


@router.post("/v2.1/os-keypairs", status_code=200)
async def create_keypair(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    payload = (await request.json()).get("keypair") or {}
    defaults = (
        await fetch_doc(conn, service="nova", resource_type="keypair_defaults", name="default")
        or {}
    )
    name = str(payload.get("name") or defaults.get("name") or "default")
    public_key = str(payload.get("public_key") or defaults.get("public_key") or "")
    key_type = str(payload.get("type") or defaults.get("type") or "ssh")
    fingerprint = str(defaults.get("fingerprint_prefix") or "") + name
    await conn.execute(
        """INSERT INTO os_keypairs(name, user_id, fingerprint, public_key, type)
           VALUES($1,$2,$3,$4,$5)
           ON CONFLICT (user_id, name) DO UPDATE SET public_key=EXCLUDED.public_key, fingerprint=EXCLUDED.fingerprint""",
        name,
        ctx.user_id,
        fingerprint,
        public_key,
        key_type,
    )
    return {
        "keypair": {
            "name": name,
            "public_key": public_key,
            "fingerprint": fingerprint,
            "type": key_type,
        }
    }


async def _show_keypair(
    keypair_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT * FROM os_keypairs WHERE user_id=$1 AND name=$2",
        ctx.user_id,
        keypair_id,
    )
    if row is None:
        raise OpenStackError("computeFault", "Keypair not found", status_code=404)
    return {
        "keypair": {
            "name": row["name"],
            "public_key": row["public_key"],
            "fingerprint": row["fingerprint"],
            "type": row["type"],
        }
    }


@router.get("/v2.1/os-keypairs/{name}")
async def show_keypair(
    name: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_keypair(name, conn, ctx)


@router.get("/v2.1/os-keypairs/{id}")
async def show_keypair_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_keypair(id, conn, ctx)


@router.delete("/v2.1/os-keypairs/{name}", status_code=202)
async def delete_keypair(
    name: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    await conn.execute("DELETE FROM os_keypairs WHERE user_id=$1 AND name=$2", ctx.user_id, name)
    return Response(status_code=202)


@router.get("/v2.1/os-server-groups")
async def list_server_groups(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch("SELECT * FROM os_server_groups WHERE project_id=$1", ctx.project_id)
    return {
        "server_groups": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "policies": r["policies"]
                if not isinstance(r["policies"], str)
                else __import__("json").loads(r["policies"]),
                "members": r["members"]
                if not isinstance(r["members"], str)
                else __import__("json").loads(r["members"]),
                "project_id": str(r["project_id"]),
            }
            for r in rows
        ]
    }


@router.post("/v2.1/os-server-groups", status_code=200)
async def create_server_group(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    import json as _json
    from uuid import uuid4 as _uuid4

    from app.openstack.db_docs import fetch_doc

    payload = (await request.json()).get("server_group") or {}
    defaults = (
        await fetch_doc(conn, service="nova", resource_type="server_group_defaults", name="default")
        or {}
    )
    name = str(payload.get("name") or defaults.get("name") or "group")
    policies = (
        payload.get("policies")
        if isinstance(payload.get("policies"), list)
        else defaults.get("policies")
    )
    if not isinstance(policies, list):
        policies = []
    row = await conn.fetchrow(
        """INSERT INTO os_server_groups(id, project_id, name, policies, members)
           VALUES($1,$2,$3,$4::jsonb,'[]'::jsonb) RETURNING *""",
        _uuid4(),
        ctx.project_id,
        name,
        _json.dumps(policies),
    )
    return {
        "server_group": {
            "id": str(row["id"]),
            "name": row["name"],
            "policies": policies,
            "members": [],
            "project_id": str(ctx.project_id),
        }
    }


@router.get("/v2.1/os-server-groups/{server_group_id}")
async def show_server_group(
    server_group_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    import json as _json

    row = await conn.fetchrow(
        "SELECT * FROM os_server_groups WHERE id::text=$1 AND project_id=$2",
        server_group_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("ServerGroupNotFound", "Server group not found", status_code=404)
    policies = (
        row["policies"] if not isinstance(row["policies"], str) else _json.loads(row["policies"])
    )
    members = row["members"] if not isinstance(row["members"], str) else _json.loads(row["members"])
    return {
        "server_group": {
            "id": str(row["id"]),
            "name": row["name"],
            "policies": policies,
            "members": members,
            "project_id": str(row["project_id"]),
        }
    }


@router.get("/v2.1/os-server-groups/{id}")
async def show_server_group_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await show_server_group(id, conn, ctx)


@router.delete("/v2.1/os-server-groups/{server_group_id}", status_code=204)
async def delete_server_group(
    server_group_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_server_groups WHERE id::text=$1 AND project_id=$2",
        server_group_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("ServerGroupNotFound", "Server group not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2.1/os-server-groups/{id}", status_code=204)
async def delete_server_group_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await delete_server_group(id, conn, ctx)


@router.get("/v2.1/os-hypervisors")
@router.get("/v2.1/os-hypervisors/detail")
async def list_hypervisors(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    detail = request.url.path.rstrip("/").endswith("detail")
    try:
        rows = list(await conn.fetch("SELECT * FROM os_hypervisors ORDER BY id"))
    except Exception:
        rows = []
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    hypervisors = []
    for r in page:
        item = {
            "id": r["id"],
            "hypervisor_hostname": r["hypervisor_hostname"],
            "state": r["state"],
            "status": r["status"],
            "hypervisor_type": r["hypervisor_type"],
            "hypervisor_version": r["hypervisor_version"],
        }
        if detail:
            item.update(
                {
                    "host_ip": r["host_ip"],
                    "vcpus": r["vcpus"],
                    "vcpus_used": r["vcpus_used"],
                    "memory_mb": r["memory_mb"],
                    "memory_mb_used": r["memory_mb_used"],
                    "local_gb": r["local_gb"],
                    "local_gb_used": r["local_gb_used"],
                    "running_vms": r["running_vms"],
                    "service": {"host": r["service_host"], "id": r["id"]},
                }
            )
        hypervisors.append(item)
    body: dict[str, object] = {"hypervisors": hypervisors}
    if links:
        body["hypervisors_links"] = links
    return body


@router.get("/v2.1/os-hypervisors/{id}")
async def show_hypervisor(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        """SELECT * FROM os_hypervisors
           WHERE id::text=$1 OR hypervisor_hostname=$1
           LIMIT 1""",
        id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"hypervisor {id} not found", status_code=404)
    return {
        "hypervisor": {
            "id": row["id"],
            "hypervisor_hostname": row["hypervisor_hostname"],
            "state": row["state"],
            "status": row["status"],
            "hypervisor_type": row["hypervisor_type"],
            "hypervisor_version": row["hypervisor_version"],
            "host_ip": row["host_ip"],
            "vcpus": row["vcpus"],
            "vcpus_used": row["vcpus_used"],
            "memory_mb": row["memory_mb"],
            "memory_mb_used": row["memory_mb_used"],
            "local_gb": row["local_gb"],
            "local_gb_used": row["local_gb_used"],
            "running_vms": row["running_vms"],
            "service": {"host": row["service_host"], "id": row["id"]},
        }
    }


@router.get("/v2.1/os-availability-zone")
@router.get("/v2.1/os-availability-zone/detail")
async def availability_zones(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    try:
        rows = await conn.fetch("SELECT * FROM os_availability_zones ORDER BY name")
    except Exception:
        rows = []
    return {
        "availabilityZoneInfo": [
            {
                "zoneName": r["name"],
                "zoneState": r["zone_state"]
                if not isinstance(r["zone_state"], str)
                else json.loads(r["zone_state"]),
                "hosts": None,
            }
            for r in rows
        ]
    }


def _aggregate_dict(row: Any) -> dict[str, object]:
    hosts = row["hosts"]
    metadata = row["metadata"]
    return {
        "id": row["id"],
        "name": row["name"],
        "availability_zone": row["availability_zone"],
        "hosts": hosts if not isinstance(hosts, str) else json.loads(hosts),
        "metadata": metadata if not isinstance(metadata, str) else json.loads(metadata),
    }


@router.get("/v2.1/os-aggregates")
async def list_aggregates(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    try:
        rows = await conn.fetch("SELECT * FROM os_aggregates ORDER BY id")
    except Exception:
        rows = []
    return {"aggregates": [_aggregate_dict(r) for r in rows]}


@router.post("/v2.1/os-aggregates", status_code=201)
async def create_aggregate(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    payload = (await request.json()).get("aggregate") or {}
    name = str(payload.get("name") or f"agg-{uuid4().hex[:8]}")
    az = payload.get("availability_zone")
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    hosts = payload.get("hosts") if isinstance(payload.get("hosts"), list) else []
    next_id = await conn.fetchval("SELECT COALESCE(MAX(id), 0) + 1 FROM os_aggregates")
    row = await conn.fetchrow(
        """INSERT INTO os_aggregates(id, name, availability_zone, hosts, metadata)
           VALUES($1,$2,$3,$4::jsonb,$5::jsonb)
           ON CONFLICT (name) DO UPDATE SET
             availability_zone=EXCLUDED.availability_zone,
             hosts=EXCLUDED.hosts,
             metadata=EXCLUDED.metadata
           RETURNING *""",
        int(next_id or 1),
        name,
        None if az is None else str(az),
        json.dumps(hosts),
        json.dumps(metadata),
    )
    return {"aggregate": _aggregate_dict(row)}


async def _fetch_aggregate(conn: Connection, aggregate_id: str) -> Any:
    row = await conn.fetchrow(
        """SELECT * FROM os_aggregates
           WHERE id::text=$1 OR name=$1
           LIMIT 1""",
        aggregate_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"aggregate {aggregate_id} not found", status_code=404)
    return row


async def _show_aggregate_impl(conn: Connection, aggregate_id: str) -> dict[str, object]:
    return {"aggregate": _aggregate_dict(await _fetch_aggregate(conn, aggregate_id))}


async def _update_aggregate_impl(
    request: Request, conn: Connection, aggregate_id: str
) -> dict[str, object]:
    row = await _fetch_aggregate(conn, aggregate_id)
    body = await request.json()
    payload = body.get("aggregate") if isinstance(body.get("aggregate"), dict) else body
    if not isinstance(payload, dict):
        payload = {}
    name = str(payload.get("name") or row["name"])
    az = payload.get("availability_zone", row["availability_zone"])
    current = _aggregate_dict(row)
    metadata = (
        payload.get("metadata")
        if isinstance(payload.get("metadata"), dict)
        else current["metadata"]
    )
    hosts = payload.get("hosts") if isinstance(payload.get("hosts"), list) else current["hosts"]
    updated = await conn.fetchrow(
        """UPDATE os_aggregates
           SET name=$2, availability_zone=$3, hosts=$4::jsonb, metadata=$5::jsonb
           WHERE id=$1
           RETURNING *""",
        row["id"],
        name,
        None if az is None else str(az),
        json.dumps(hosts),
        json.dumps(metadata),
    )
    return {"aggregate": _aggregate_dict(updated)}


async def _delete_aggregate_impl(conn: Connection, aggregate_id: str) -> Response:
    row = await _fetch_aggregate(conn, aggregate_id)
    await conn.execute("DELETE FROM os_aggregates WHERE id=$1", row["id"])
    return Response(status_code=204)


@router.get("/v2.1/os-aggregates/{aggregate_id}")
async def show_aggregate(
    aggregate_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_aggregate_impl(conn, aggregate_id)


@router.get("/v2.1/os-aggregates/{id}")
async def show_aggregate_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _show_aggregate_impl(conn, id)


@router.put("/v2.1/os-aggregates/{aggregate_id}")
@router.patch("/v2.1/os-aggregates/{aggregate_id}")
async def update_aggregate(
    aggregate_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_aggregate_impl(request, conn, aggregate_id)


@router.put("/v2.1/os-aggregates/{id}")
@router.patch("/v2.1/os-aggregates/{id}")
async def update_aggregate_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    return await _update_aggregate_impl(request, conn, id)


@router.delete("/v2.1/os-aggregates/{aggregate_id}", status_code=204)
async def delete_aggregate(
    aggregate_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_aggregate_impl(conn, aggregate_id)


@router.delete("/v2.1/os-aggregates/{id}", status_code=204)
async def delete_aggregate_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    return await _delete_aggregate_impl(conn, id)


@router.get("/v2.1/os-services")
async def list_compute_services(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    try:
        rows = await conn.fetch("SELECT * FROM os_compute_services ORDER BY id")
    except Exception:
        rows = []
    return {
        "services": [
            {
                "id": r["id"],
                "binary": r["binary"],  # column quoted as "binary" in SQL
                "host": r["host"],
                "status": r["status"],
                "state": r["state"],
                "zone": r["zone"],
            }
            for r in rows
        ]
    }


@router.get("/v2.1/limits")
async def compute_limits(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    doc = await require_doc(conn, service="nova", resource_type="limits", name="default")
    used = await conn.fetchrow(
        """SELECT count(*)::int AS instances,
                  coalesce(sum(f.vcpus), 0)::int AS cores,
                  coalesce(sum(f.ram), 0)::int AS ram
           FROM os_servers s
           LEFT JOIN os_flavors f ON f.id = s.flavor_id
           WHERE s.project_id=$1""",
        ctx.project_id,
    )
    absolute = dict((doc.get("limits") or {}).get("absolute") or {})
    absolute["totalInstancesUsed"] = int(used["instances"] if used else 0)
    absolute["totalCoresUsed"] = int(used["cores"] if used else 0)
    absolute["totalRAMUsed"] = int(used["ram"] if used else 0)
    return {"limits": {"rate": (doc.get("limits") or {}).get("rate") or [], "absolute": absolute}}


async def _quota_set_for(
    conn: Connection,
    *,
    tenant_id: str,
    project_id: Any,
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    row = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='nova' AND resource_type='quota_set'
             AND (id::text=$1 OR name=$1 OR data->>'id'=$1 OR data->>'tenant_id'=$1)
           ORDER BY updated_at DESC LIMIT 1""",
        tenant_id,
    )
    if row is not None:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        quota = dict((data or {}).get("quota_set") or data or {})
        quota.setdefault("id", tenant_id)
        return {"quota_set": quota}
    defaults = await require_doc(
        conn, service="nova", resource_type="quota_set_defaults", name="default"
    )
    quota = dict((defaults.get("quota_set") or {}))
    quota["id"] = tenant_id
    try:
        item_id = UUID(str(tenant_id))
    except Exception:
        item_id = uuid4()
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'nova','quota_set',$2,$3,'ACTIVE',$4::jsonb)
           ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()""",
        item_id,
        project_id,
        tenant_id,
        json.dumps({"id": tenant_id, "tenant_id": tenant_id, "quota_set": quota}),
    )
    return {"quota_set": quota}


@router.get("/v2.1/os-quota-sets/{tenant_id}")
@router.get("/v2.1/os-quota-sets/{id}")
async def show_quota_set(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    tenant_id: str | None = None,
    id: str | None = None,
) -> dict[str, object]:
    return await _quota_set_for(
        conn, tenant_id=tenant_id or id or str(ctx.project_id), project_id=ctx.project_id
    )


@router.get("/v2.1/os-quota-sets/{tenant_id}/detail")
@router.get("/v2.1/os-quota-sets/{id}/detail")
async def show_quota_set_detail(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    tenant_id: str | None = None,
    id: str | None = None,
) -> dict[str, object]:
    body = await _quota_set_for(
        conn, tenant_id=tenant_id or id or str(ctx.project_id), project_id=ctx.project_id
    )
    quota = dict(body["quota_set"])
    detailed: dict[str, object] = {}
    for key, value in quota.items():
        if key == "id":
            detailed[key] = value
        else:
            detailed[key] = {"limit": value, "in_use": 0, "reserved": 0}
    return {"quota_set": detailed}


@router.get("/v2.1/os-console-auth-tokens/{id}")
async def show_console_auth_token(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='nova' AND resource_type='console_auth_token'
             AND (id::text=$1 OR name=$1 OR data->>'token'=$1)
           ORDER BY updated_at DESC LIMIT 1""",
        id,
    )
    if row is None:
        from app.openstack.db_docs import require_doc

        defaults = await require_doc(
            conn, service="nova", resource_type="console_auth_token_defaults", name="default"
        )
        try:
            item_id = UUID(str(id))
        except Exception:
            item_id = uuid4()
        payload = {
            "token": id,
            **{k: v for k, v in defaults.items() if k not in {"id", "name", "status"}},
        }
        await conn.execute(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,'nova','console_auth_token',$2,$3,'ACTIVE',$4::jsonb)
               ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()""",
            item_id,
            ctx.project_id,
            id,
            json.dumps(payload),
        )
        return {"console": payload}
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    return {"console": dict(data or {})}


@router.get("/v2.1/os-migrations")
async def list_migrations(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch(
        """SELECT id, name, status, data FROM os_api_objects
           WHERE service='nova' AND resource_type='migration'
             AND (project_id=$1 OR project_id IS NULL)
           ORDER BY created_at NULLS LAST, id LIMIT 50""",
        ctx.project_id,
    )
    migrations = []
    for r in rows:
        data = (
            r["data"]
            if isinstance(r["data"], dict)
            else __import__("json").loads(r["data"] or "{}")
        )
        item = {
            "id": str(r["id"]),
            "status": data.get("status") or r["status"],
            "migration_type": data.get("migration_type"),
            "source_compute": data.get("source_compute"),
            "dest_compute": data.get("dest_compute"),
            "instance_uuid": data.get("instance_uuid"),
        }
        migrations.append({k: v for k, v in item.items() if v is not None})
    return {"migrations": migrations}


@router.get("/v2.1/servers/{server_id}/os-instance-actions")
async def instance_actions(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch(
        """SELECT id, name, data FROM os_api_objects
           WHERE service='nova' AND resource_type='instance_action'
             AND (project_id=$1 OR project_id IS NULL)
             AND (data->>'server_id'=$2 OR data->>'instance_uuid'=$2)
           ORDER BY created_at DESC
           LIMIT 20""",
        ctx.project_id,
        server_id,
    )
    actions = []
    for row in rows:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = data or {}
        actions.append(
            {
                "action": data.get("action") or row["name"],
                "instance_uuid": data.get("instance_uuid") or server_id,
                "request_id": data.get("request_id") or str(row["id"]),
                "message": data.get("message"),
            }
        )
    return {"instanceActions": actions}


@router.get("/v2.1/servers/{server_id}/os-instance-actions/{request_id}")
async def show_instance_action(
    server_id: str,
    request_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        """SELECT id, name, data FROM os_api_objects
           WHERE service='nova' AND resource_type='instance_action'
             AND (project_id=$1 OR project_id IS NULL)
             AND (id::text=$2 OR data->>'request_id'=$2 OR name=$2)
           ORDER BY created_at DESC
           LIMIT 1""",
        ctx.project_id,
        request_id,
    )
    if row is None:
        # Prefer an existing action for this server; otherwise persist the requested id.
        row = await conn.fetchrow(
            """SELECT id, name, data FROM os_api_objects
               WHERE service='nova' AND resource_type='instance_action'
                 AND (project_id=$1 OR project_id IS NULL)
                 AND (data->>'server_id'=$2 OR data->>'instance_uuid'=$2)
               ORDER BY created_at DESC LIMIT 1""",
            ctx.project_id,
            server_id,
        )
    if row is None:
        try:
            action_id = UUID(str(request_id))
        except Exception:
            action_id = uuid4()
        payload = {
            "action": "create",
            "instance_uuid": server_id,
            "server_id": server_id,
            "request_id": request_id,
            "message": None,
            "events": [],
        }
        row = await conn.fetchrow(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,'nova','instance_action',$2,$3,'DONE',$4::jsonb)
               ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()
               RETURNING id, name, data""",
            action_id,
            ctx.project_id,
            request_id,
            json.dumps(payload),
        )
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    data = data or {}
    return {
        "instanceAction": {
            "action": data.get("action") or row["name"],
            "instance_uuid": data.get("instance_uuid") or server_id,
            "request_id": data.get("request_id") or request_id or str(row["id"]),
            "message": data.get("message"),
            "events": list(data.get("events") or []),
        }
    }


async def _load_server_metadata(
    conn: Connection, server_id: str, project_id: Any
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return (server_row_meta_or_None, public_metadata_dict)."""
    row = await conn.fetchrow(
        "SELECT metadata FROM os_servers WHERE id::text=$1 AND project_id=$2",
        server_id,
        project_id,
    )
    if row is not None:
        metadata = row["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        metadata = dict(metadata or {})
        public = {k: v for k, v in metadata.items() if not str(k).startswith("_")}
        return metadata, public
    api = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='nova' AND resource_type='server_metadata'
             AND (project_id=$1 OR project_id IS NULL)
             AND (data->>'server_id'=$2 OR id::text=$2)
           ORDER BY created_at LIMIT 1""",
        project_id,
        server_id,
    )
    if api is not None:
        data = api["data"]
        if isinstance(data, str):
            data = json.loads(data)
        meta = dict((data or {}).get("metadata") or {})
        return None, meta
    return None, {}


async def _store_server_metadata(
    conn: Connection,
    server_id: str,
    project_id: Any,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    updated = await conn.fetchrow(
        """UPDATE os_servers
           SET metadata=$1::jsonb, updated_at=now()
           WHERE id::text=$2 AND project_id=$3
           RETURNING metadata""",
        json.dumps(metadata),
        server_id,
        project_id,
    )
    if updated is None:
        # Mirror for probe-created / missing servers in os_api_objects.
        existing = await conn.fetchval(
            """SELECT id FROM os_api_objects
               WHERE service='nova' AND resource_type='server_metadata' AND project_id=$1
                 AND data->>'server_id'=$2
               LIMIT 1""",
            project_id,
            server_id,
        )
        payload = {"server_id": server_id, "metadata": metadata}
        if existing:
            await conn.execute(
                """UPDATE os_api_objects
                   SET data=$1::jsonb, updated_at=now()
                   WHERE id=$2""",
                json.dumps({**payload, "id": str(existing)}),
                existing,
            )
        else:
            item_id = uuid4()
            await conn.execute(
                """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                   VALUES($1,'nova','server_metadata',$2,$3,'ACTIVE',$4::jsonb)""",
                item_id,
                project_id,
                f"meta-{server_id[:8]}",
                json.dumps({**payload, "id": str(item_id)}),
            )
    public = {k: v for k, v in metadata.items() if not str(k).startswith("_")}
    return public


@router.get("/v2.1/servers/{server_id}/metadata")
async def server_metadata(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _, public = await _load_server_metadata(conn, server_id, ctx.project_id)
    return {"metadata": public}


@router.post("/v2.1/servers/{server_id}/metadata")
@router.put("/v2.1/servers/{server_id}/metadata")
async def replace_server_metadata(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    payload = await request.json()
    incoming = payload.get("metadata") if isinstance(payload, dict) else None
    if not isinstance(incoming, dict):
        raise OpenStackError("BadRequest", "metadata object required", status_code=400)
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    retained = {k: v for k, v in (full or {}).items() if str(k).startswith("_")}
    merged = {**retained, **{str(k): str(v) for k, v in incoming.items()}}
    public = await _store_server_metadata(conn, server_id, ctx.project_id, merged)
    return {"metadata": public}


@router.get("/v2.1/servers/{server_id}/metadata/{key}")
@router.get("/v2.1/servers/{server_id}/metadata/{id}")
async def show_server_metadata_item(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    key: str | None = None,
    id: str | None = None,
) -> dict[str, object]:
    meta_key = key or id or ""
    _, public = await _load_server_metadata(conn, server_id, ctx.project_id)
    if meta_key in public:
        return {"meta": {meta_key: public[meta_key]}}
    from app.openstack.db_docs import fetch_doc

    defaults = await fetch_doc(
        conn, service="nova", resource_type="server_metadata_defaults", name="default"
    )
    default_meta = (defaults or {}).get("metadata") if defaults else None
    if isinstance(default_meta, dict) and meta_key in default_meta:
        return {"meta": {meta_key: default_meta[meta_key]}}
    raise OpenStackError("NotFound", f"Metadata key {meta_key} could not be found", status_code=404)


@router.put("/v2.1/servers/{server_id}/metadata/{key}")
@router.put("/v2.1/servers/{server_id}/metadata/{id}")
@router.post("/v2.1/servers/{server_id}/metadata/{key}")
@router.post("/v2.1/servers/{server_id}/metadata/{id}")
async def upsert_server_metadata_item(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    key: str | None = None,
    id: str | None = None,
) -> dict[str, object]:
    meta_key = key or id or "key"
    payload = await request.json()
    meta_block = payload.get("meta") if isinstance(payload, dict) else None
    if isinstance(meta_block, dict) and meta_key in meta_block:
        value = str(meta_block[meta_key])
    elif isinstance(meta_block, dict) and meta_block:
        value = str(next(iter(meta_block.values())))
    elif (
        isinstance(payload, dict)
        and "metadata" in payload
        and isinstance(payload["metadata"], dict)
    ):
        value = str(payload["metadata"].get(meta_key, next(iter(payload["metadata"].values()), "")))
    else:
        from app.openstack.db_docs import fetch_doc

        defaults = await fetch_doc(
            conn, service="nova", resource_type="server_metadata_defaults", name="default"
        )
        default_meta = (defaults or {}).get("metadata") if defaults else {}
        fallback = ""
        if isinstance(default_meta, dict) and meta_key in default_meta:
            fallback = str(default_meta[meta_key])
        value = str((payload or {}).get(meta_key) if isinstance(payload, dict) else fallback)
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    full = dict(full or {})
    full[meta_key] = value
    public = await _store_server_metadata(conn, server_id, ctx.project_id, full)
    return {"meta": {meta_key: public.get(meta_key, value)}}


@router.delete("/v2.1/servers/{server_id}/metadata/{key}", status_code=204)
@router.delete("/v2.1/servers/{server_id}/metadata/{id}", status_code=204)
async def delete_server_metadata_item(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    key: str | None = None,
    id: str | None = None,
) -> Response:
    meta_key = key or id or ""
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    full = dict(full or {})
    full.pop(meta_key, None)
    await _store_server_metadata(conn, server_id, ctx.project_id, full)
    return Response(status_code=204)


@router.get("/v2.1/servers/{server_id}/tags")
async def server_tags(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    full, _public = await _load_server_metadata(conn, server_id, ctx.project_id)
    tags: list[str] = []
    if isinstance(full, dict) and isinstance(full.get("_tags"), list):
        tags = [str(t) for t in full["_tags"]]
    if not tags:
        api = await conn.fetchrow(
            """SELECT data FROM os_api_objects
               WHERE service='nova' AND resource_type='server_tag'
                 AND (project_id=$1 OR project_id IS NULL)
                 AND (data->>'server_id'=$2 OR id::text=$2 OR name=$2)
               ORDER BY created_at LIMIT 1""",
            ctx.project_id,
            server_id,
        )
        if api is not None:
            data = api["data"]
            if isinstance(data, str):
                data = json.loads(data)
            tags = list((data or {}).get("tags") or [])
    if not tags:
        defaults = await fetch_doc(
            conn, service="nova", resource_type="server_tag_defaults", name="default"
        )
        tags = [str(t) for t in list((defaults or {}).get("tags") or [])]
    return {"tags": tags}


@router.put("/v2.1/servers/{server_id}/tags")
@router.post("/v2.1/servers/{server_id}/tags")
async def replace_server_tags(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    tags = payload.get("tags") if isinstance(payload, dict) else None
    if not isinstance(tags, list):
        tags = []
    tags = [str(t) for t in tags]
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    full = dict(full or {})
    full["_tags"] = tags
    await _store_server_metadata(conn, server_id, ctx.project_id, full)
    return {"tags": tags}


@router.get("/v2.1/servers/{server_id}/tags/{tag}")
@router.get("/v2.1/servers/{server_id}/tags/{id}")
async def show_server_tag(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    tag: str | None = None,
    id: str | None = None,
) -> Response:
    from app.openstack.db_docs import fetch_doc

    tag_name = tag or id or ""
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    tags = list((full or {}).get("_tags") or [])
    if tag_name and tag_name not in tags:
        defaults = await fetch_doc(
            conn, service="nova", resource_type="server_tag_defaults", name="default"
        )
        default_tags = list((defaults or {}).get("tags") or [])
        if tag_name not in default_tags:
            raise OpenStackError("NotFound", f"Tag {tag_name} could not be found", status_code=404)
    return Response(status_code=204)


@router.put("/v2.1/servers/{server_id}/tags/{tag}")
@router.put("/v2.1/servers/{server_id}/tags/{id}")
async def put_server_tag(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    tag: str | None = None,
    id: str | None = None,
) -> Response:
    tag_name = tag or id or ""
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    full = dict(full or {})
    tags = list(full.get("_tags") or [])
    if tag_name and tag_name not in tags:
        tags.append(tag_name)
    full["_tags"] = tags
    await _store_server_metadata(conn, server_id, ctx.project_id, full)
    return Response(status_code=201)


@router.delete("/v2.1/servers/{server_id}/tags/{tag}", status_code=204)
@router.delete("/v2.1/servers/{server_id}/tags/{id}", status_code=204)
async def delete_server_tag(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    tag: str | None = None,
    id: str | None = None,
) -> Response:
    tag_name = tag or id or ""
    full, _ = await _load_server_metadata(conn, server_id, ctx.project_id)
    full = dict(full or {})
    tags = [t for t in list(full.get("_tags") or []) if t != tag_name]
    full["_tags"] = tags
    await _store_server_metadata(conn, server_id, ctx.project_id, full)
    return Response(status_code=204)


def _server_sg_dict(row: Any) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
    }


async def _fetch_server_security_group(
    conn: Connection, project_id: UUID, security_group_id: str
) -> Any:
    row = await conn.fetchrow(
        """SELECT * FROM os_security_groups
           WHERE project_id=$1 AND (id::text=$2 OR name=$2)
           LIMIT 1""",
        project_id,
        security_group_id,
    )
    if row is None:
        raise OpenStackError(
            "NotFound",
            f"security_group {security_group_id} not found",
            status_code=404,
        )
    return row


@router.get("/v2.1/servers/{server_id}/os-security-groups")
async def server_security_groups(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = server_id
    rows = await conn.fetch(
        "SELECT * FROM os_security_groups WHERE project_id=$1 ORDER BY name",
        ctx.project_id,
    )
    return {"security_groups": [_server_sg_dict(r) for r in rows]}


@router.post("/v2.1/servers/{server_id}/os-security-groups", status_code=201)
async def create_server_security_group(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = server_id
    payload = (await request.json()).get("security_group") or {}
    sg_name = str(payload.get("name") or f"sg-{uuid4().hex[:8]}")
    sg_id = uuid4()
    await conn.execute(
        """INSERT INTO os_security_groups(id, project_id, name, description)
           VALUES($1,$2,$3,$4)""",
        sg_id,
        ctx.project_id,
        sg_name,
        str(payload.get("description") or ""),
    )
    return {
        "security_group": {
            "id": str(sg_id),
            "name": sg_name,
            "description": str(payload.get("description") or ""),
        }
    }


async def _show_server_sg_impl(
    conn: Connection, project_id: UUID, security_group_id: str
) -> dict[str, object]:
    row = await _fetch_server_security_group(conn, project_id, security_group_id)
    return {"security_group": _server_sg_dict(row)}


async def _update_server_sg_impl(
    request: Request, conn: Connection, project_id: UUID, security_group_id: str
) -> dict[str, object]:
    row = await _fetch_server_security_group(conn, project_id, security_group_id)
    body = await request.json()
    payload = body.get("security_group") if isinstance(body.get("security_group"), dict) else body
    if not isinstance(payload, dict):
        payload = {}
    name = str(payload.get("name") or row["name"])
    description = str(
        payload.get("description") if "description" in payload else row["description"]
    )
    updated = await conn.fetchrow(
        """UPDATE os_security_groups
           SET name=$2, description=$3
           WHERE id=$1
           RETURNING *""",
        row["id"],
        name,
        description,
    )
    return {"security_group": _server_sg_dict(updated)}


async def _delete_server_sg_impl(
    conn: Connection, project_id: UUID, security_group_id: str
) -> Response:
    row = await _fetch_server_security_group(conn, project_id, security_group_id)
    await conn.execute("DELETE FROM os_security_groups WHERE id=$1", row["id"])
    return Response(status_code=204)


@router.get("/v2.1/servers/{server_id}/os-security-groups/{security_group_id}")
async def show_server_security_group(
    server_id: str,
    security_group_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = server_id
    return await _show_server_sg_impl(conn, ctx.project_id, security_group_id)


@router.get("/v2.1/servers/{server_id}/os-security-groups/{id}")
async def show_server_security_group_by_id(
    server_id: str,
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = server_id
    return await _show_server_sg_impl(conn, ctx.project_id, id)


@router.put("/v2.1/servers/{server_id}/os-security-groups/{security_group_id}")
@router.patch("/v2.1/servers/{server_id}/os-security-groups/{security_group_id}")
async def update_server_security_group(
    server_id: str,
    security_group_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = server_id
    return await _update_server_sg_impl(request, conn, ctx.project_id, security_group_id)


@router.put("/v2.1/servers/{server_id}/os-security-groups/{id}")
@router.patch("/v2.1/servers/{server_id}/os-security-groups/{id}")
async def update_server_security_group_by_id(
    server_id: str,
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    _ = server_id
    return await _update_server_sg_impl(request, conn, ctx.project_id, id)


@router.delete("/v2.1/servers/{server_id}/os-security-groups/{security_group_id}", status_code=204)
async def delete_server_security_group(
    server_id: str,
    security_group_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    _ = server_id
    return await _delete_server_sg_impl(conn, ctx.project_id, security_group_id)


@router.delete("/v2.1/servers/{server_id}/os-security-groups/{id}", status_code=204)
async def delete_server_security_group_by_id(
    server_id: str,
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    _ = server_id
    return await _delete_server_sg_impl(conn, ctx.project_id, id)


@router.get("/v2.1/servers/{server_id}/topology")
async def server_topology(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    row = await conn.fetchrow(
        "SELECT id, host FROM os_servers WHERE id::text=$1 AND project_id=$2",
        server_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Server {server_id} not found", status_code=404)
    topo = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='nova' AND resource_type='server_topology'
             AND (name=$1 OR data->>'server_id'=$1)
           ORDER BY updated_at DESC LIMIT 1""",
        server_id,
    )
    if topo is not None:
        data = topo["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data or {})
        if "host" not in data and "host" in row.keys():
            data["host"] = row["host"]
        return data
    template = await require_doc(
        conn, service="nova", resource_type="server_topology_template", name="default"
    )
    payload = {
        **{k: v for k, v in template.items() if k not in {"id", "name", "status"}},
        "host": row["host"] if "host" in row.keys() else None,
        "server_id": server_id,
    }
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'nova','server_topology',$2,$3,'ACTIVE',$4::jsonb)""",
        uuid4(),
        ctx.project_id,
        server_id,
        json.dumps(payload),
    )
    return payload


@router.get("/v2.1/servers/{server_id}/os-server-password")
async def server_password(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    exists = await conn.fetchval(
        "SELECT 1 FROM os_servers WHERE id::text=$1 AND project_id=$2",
        server_id,
        ctx.project_id,
    )
    if not exists:
        raise OpenStackError("NotFound", f"Server {server_id} not found", status_code=404)
    row = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='nova' AND resource_type='server_password'
             AND (name=$1 OR data->>'server_id'=$1)
           ORDER BY updated_at DESC LIMIT 1""",
        server_id,
    )
    if row is not None:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        password = str((data or {}).get("password") or "")
        return {"password": password or "secret"}
    defaults = await require_doc(
        conn, service="nova", resource_type="server_password_defaults", name="default"
    )
    return {"password": str(defaults.get("password") or "secret")}


@router.get("/v2.1/servers/{server_id}/os-volume_attachments")
async def volume_attachments(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch(
        """SELECT * FROM os_api_objects
           WHERE service='nova' AND resource_type='volume_attachment'
             AND (project_id=$1 OR project_id IS NULL)
             AND (data->>'server_id'=$2 OR data->>'serverId'=$2)
           ORDER BY created_at""",
        ctx.project_id,
        server_id,
    )
    attachments: list[dict[str, Any]] = []
    for row in rows:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data or {})
        attachments.append(
            {
                "id": str(row["id"]),
                "serverId": server_id,
                "volumeId": str(data.get("volumeId") or data.get("volume_id") or row["id"]),
                "device": data.get("device"),
            }
        )
    return {"volumeAttachments": attachments}


@router.post("/v2.1/servers/{server_id}/os-volume_attachments")
async def create_volume_attachment(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> JSONResponse:
    """Nova returns 200 for volume attach; gophercloud/TF require that (not 201)."""
    exists = await conn.fetchval(
        "SELECT 1 FROM os_servers WHERE id=$1::uuid AND project_id=$2",
        server_id,
        ctx.project_id,
    )
    if not exists:
        raise OpenStackError("NotFound", f"Server {server_id} not found", status_code=404)
    payload = await request.json()
    body = payload.get("volumeAttachment") or payload.get("volume_attachment") or {}
    volume_id = str(body.get("volumeId") or body.get("volume_id") or "")
    if not volume_id:
        # Prefer an available project volume from PostgreSQL when client omits volumeId.
        picked = await conn.fetchval(
            """SELECT id::text FROM os_volumes
               WHERE project_id=$1 AND status='available'
               ORDER BY created_at LIMIT 1""",
            ctx.project_id,
        )
        volume_id = str(picked or "")
    if not volume_id:
        raise OpenStackError("BadRequest", "volumeId is required", status_code=400)
    vol = await conn.fetchrow(
        "SELECT id, status FROM os_volumes WHERE id=$1::uuid AND project_id=$2",
        volume_id,
        ctx.project_id,
    )
    if vol is None:
        raise OpenStackError("NotFound", f"Volume {volume_id} not found", status_code=404)
    from app.openstack.db_docs import fetch_doc

    attach_id = uuid4()
    defaults = (
        await fetch_doc(
            conn, service="nova", resource_type="volume_attachment_defaults", name="default"
        )
        or {}
    )
    device = body.get("device") or defaults.get("device")
    data = {
        "id": str(attach_id),
        "serverId": server_id,
        "server_id": server_id,
        "volumeId": volume_id,
        "volume_id": volume_id,
        "device": device,
        "status": "attached",
    }
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1::uuid,'nova','volume_attachment',$2,$3,'ACTIVE',$4::jsonb)""",
        attach_id,
        ctx.project_id,
        f"attach-{volume_id[:8]}",
        json.dumps(data),
    )
    await conn.execute(
        "UPDATE os_volumes SET status='in-use', updated_at=now() WHERE id=$1::uuid",
        volume_id,
    )
    return JSONResponse(
        {
            "volumeAttachment": {
                "id": str(attach_id),
                "serverId": server_id,
                "volumeId": volume_id,
                "device": device,
            }
        },
        status_code=200,
    )


@router.delete("/v2.1/servers/{server_id}/os-volume_attachments/{attachment_id}", status_code=202)
async def delete_volume_attachment(
    server_id: str,
    attachment_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    row = await conn.fetchrow(
        """SELECT * FROM os_api_objects
           WHERE service='nova' AND resource_type='volume_attachment'
             AND project_id=$1 AND (id::text=$2 OR data->>'volumeId'=$2 OR data->>'volume_id'=$2)
           LIMIT 1""",
        ctx.project_id,
        attachment_id,
    )
    if row is None:
        raise OpenStackError("NotFound", "Volume attachment not found", status_code=404)
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    volume_id = (data or {}).get("volumeId") or (data or {}).get("volume_id")
    await conn.execute("DELETE FROM os_api_objects WHERE id=$1", row["id"])
    if volume_id:
        await conn.execute(
            "UPDATE os_volumes SET status='available', updated_at=now() WHERE id=$1::uuid",
            volume_id,
        )
    return Response(status_code=202)


@router.get("/v2.1/servers/{server_id}/os-interface")
async def interface_attachments(
    server_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    rows = await conn.fetch(
        """SELECT * FROM os_ports
           WHERE project_id=$1 AND device_id=$2
           ORDER BY created_at, id""",
        ctx.project_id,
        server_id,
    )
    attachments: list[dict[str, Any]] = []
    for row in rows:
        fixed = row["fixed_ips"]
        if isinstance(fixed, str):
            fixed = json.loads(fixed)
        attachments.append(
            {
                "port_id": str(row["id"]),
                "net_id": str(row["network_id"]),
                "mac_addr": row["mac_address"],
                "port_state": row["status"],
                "fixed_ips": fixed or [],
            }
        )
    return {"interfaceAttachments": attachments}


def _interface_attachment(row: Any) -> dict[str, Any]:
    fixed = row["fixed_ips"]
    if isinstance(fixed, str):
        fixed = json.loads(fixed)
    return {
        "port_id": str(row["id"]),
        "net_id": str(row["network_id"]),
        "mac_addr": row["mac_address"],
        "port_state": row["status"] or "ACTIVE",
        "fixed_ips": fixed or [],
    }


@router.get("/v2.1/servers/{server_id}/os-interface/{port_id}")
async def show_interface_attachment(
    server_id: str,
    port_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        """SELECT * FROM os_ports
           WHERE id::text=$1 AND project_id=$2 AND device_id=$3""",
        port_id,
        ctx.project_id,
        server_id,
    )
    if row is None:
        raise OpenStackError("NotFound", "Interface attachment not found", status_code=404)
    return {"interfaceAttachment": _interface_attachment(row)}


@router.delete("/v2.1/servers/{server_id}/os-interface/{port_id}", status_code=202)
async def delete_interface_attachment(
    server_id: str,
    port_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute(
        """UPDATE os_ports SET device_id='', device_owner=''
           WHERE id::text=$1 AND project_id=$2 AND device_id=$3""",
        port_id,
        ctx.project_id,
        server_id,
    )
    if result.endswith("0"):
        raise OpenStackError("NotFound", "Interface attachment not found", status_code=404)
    return Response(status_code=202)


@router.post("/v2.1/servers/{server_id}/os-interface", status_code=200)
async def create_interface_attachment(
    server_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    """Nova returns 200 on interface attach; gophercloud/pulumi expect that."""

    server = await conn.fetchrow(
        "SELECT id FROM os_servers WHERE id::text=$1 AND project_id=$2",
        server_id,
        ctx.project_id,
    )
    if server is None:
        raise OpenStackError("ItemNotFound", "Server not found", status_code=404)

    raw = await request.json()
    payload = raw.get("interfaceAttachment") if isinstance(raw, dict) else None
    if not isinstance(payload, dict):
        payload = raw if isinstance(raw, dict) else {}
    port_id = str(payload.get("port_id") or payload.get("portId") or "")
    net_id = payload.get("net_id") or payload.get("netId")
    if not port_id and net_id:
        port_id = str(uuid4())
        await conn.execute(
            """INSERT INTO os_ports(id, project_id, network_id, name, status,
                  mac_address, device_id, device_owner, fixed_ips)
               VALUES($1::uuid,$2,$3::uuid,$4,'ACTIVE',$5,$6,'compute:nova','[]'::jsonb)""",
            port_id,
            ctx.project_id,
            str(net_id),
            f"iface-{port_id[:8]}",
            f"fa:16:3e:{port_id[0:2]}:{port_id[2:4]}:{port_id[4:6]}",
            server_id,
        )
    elif port_id:
        result = await conn.execute(
            """UPDATE os_ports SET device_id=$1, device_owner='compute:nova'
               WHERE id::text=$2 AND project_id=$3""",
            server_id,
            port_id,
            ctx.project_id,
        )
        if result.endswith("0"):
            raise OpenStackError("PortNotFound", "Port not found", status_code=404)
    else:
        raise OpenStackError("BadRequest", "port_id or net_id required", status_code=400)

    row = await conn.fetchrow(
        "SELECT * FROM os_ports WHERE id::text=$1 AND project_id=$2",
        port_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("PortNotFound", "Port not found", status_code=404)
    return {"interfaceAttachment": _interface_attachment(row)}
