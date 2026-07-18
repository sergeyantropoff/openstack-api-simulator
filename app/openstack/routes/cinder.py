"""Cinder Block Storage API v3 (lab subset)."""

from __future__ import annotations

import json
from typing import Annotated, Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Cinder"])

_DEFAULT_QUOTA_SET: dict[str, object] = {
    "volumes": 100,
    "snapshots": 100,
    "gigabytes": 1000,
    "backups": 10,
    "backup_gigabytes": 1000,
    "groups": 10,
    "per_volume_gigabytes": -1,
}


def _volume(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "size": row["size"],
        "volume_type": row["volume_type"],
        "bootable": "true" if row["bootable"] else "false",
        "multiattach": False,
        "encrypted": False,
        "os-vol-tenant-attr:tenant_id": str(row["project_id"]),
        "metadata": {},
        "attachments": [],
        "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "updated_at": row["updated_at"].strftime("%Y-%m-%dT%H:%M:%S.%f"),
        "links": [
            {"rel": "self", "href": f"/v3/{row['project_id']}/volumes/{row['id']}"},
        ],
    }


@router.get("/v3")
@router.get("/v3/")
async def cinder_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="cinder", resource_type="discovery_version", name="default"
    )


async def _quota_set_for(
    conn: Connection,
    *,
    tenant_id: str,
    project_id: Any,
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    row = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service='cinder' AND resource_type='quota_set'
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
    defaults = (
        await fetch_doc(conn, service="cinder", resource_type="quota_set_defaults", name="default")
        or {}
    )
    quota = dict((defaults.get("quota_set") or _DEFAULT_QUOTA_SET))
    quota["id"] = tenant_id
    # Stable per-tenant id that does not collide with Nova's project-UUID quota rows.
    item_id = uuid5(NAMESPACE_URL, f"cinder:quota_set:{tenant_id}")
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'cinder','quota_set',$2,$3,'ACTIVE',$4::jsonb)
           ON CONFLICT (id) DO UPDATE SET data=EXCLUDED.data, updated_at=now()""",
        item_id,
        project_id,
        tenant_id,
        json.dumps({"id": tenant_id, "tenant_id": tenant_id, "quota_set": quota}),
    )
    return {"quota_set": quota}


@router.get("/v3/os-quota-sets/{tenant_id}")
@router.get("/v3/os-quota-sets/{id}")
@router.get("/v3/{project_id}/os-quota-sets/{tenant_id}")
@router.get("/v3/{project_id}/os-quota-sets/{id}")
async def show_quota_set(
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    tenant_id: str | None = None,
    id: str | None = None,
    project_id: str | None = None,
) -> dict[str, object]:
    _ = project_id
    return await _quota_set_for(
        conn, tenant_id=tenant_id or id or str(ctx.project_id), project_id=ctx.project_id
    )


@router.get("/v3/{project_id}/volumes")
@router.get("/v3/{project_id}/volumes/detail")
@router.get("/v3/volumes")
@router.get("/v3/volumes/detail")
async def list_volumes(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    _ = project_id  # path project_id ignored; token scope wins
    detail = request.url.path.rstrip("/").endswith("detail")
    rows = list(
        await conn.fetch(
            "SELECT * FROM os_volumes WHERE project_id = $1 ORDER BY created_at, id",
            ctx.project_id,
        )
    )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    if detail:
        body: dict[str, object] = {"volumes": [_volume(r) for r in page]}
    else:
        body = {
            "volumes": [
                {
                    "id": str(r["id"]),
                    "name": r["name"],
                    "links": [{"rel": "self", "href": f"/v3/{ctx.project_id}/volumes/{r['id']}"}],
                }
                for r in page
            ]
        }
    if links:
        body["volumes_links"] = links
    return body


@router.get("/v3/{project_id}/volumes/{volume_id}")
@router.get("/v3/volumes/{volume_id}")
async def show_volume(
    volume_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> dict[str, object]:
    _ = project_id
    # openstacksdk may probe GET /volumes/{name} before create
    row = await conn.fetchrow(
        """SELECT * FROM os_volumes
           WHERE project_id = $2
             AND (id::text = $1 OR name = $1)
           ORDER BY CASE WHEN id::text = $1 THEN 0 ELSE 1 END
           LIMIT 1""",
        volume_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("ItemNotFound", "Volume could not be found", status_code=404)
    return {"volume": _volume(row)}


async def _update_volume(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, object]:
    payload = (await request.json()).get("volume") or {}
    row = await conn.fetchrow(
        """UPDATE os_volumes
           SET name = COALESCE($1, name), updated_at = now()
           WHERE id = $2::uuid AND project_id = $3
           RETURNING *""",
        payload.get("name"),
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("ItemNotFound", "Volume could not be found", status_code=404)
    return {"volume": _volume(row)}


@router.put("/v3/{project_id}/volumes/{volume_id}")
@router.patch("/v3/{project_id}/volumes/{volume_id}")
@router.put("/v3/volumes/{volume_id}")
@router.patch("/v3/volumes/{volume_id}")
async def update_volume(
    volume_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> dict[str, object]:
    _ = project_id
    return await _update_volume(volume_id, request, conn, ctx)


@router.put("/v3/{project_id}/volumes/{id}")
@router.patch("/v3/{project_id}/volumes/{id}")
@router.put("/v3/volumes/{id}")
@router.patch("/v3/volumes/{id}")
async def update_volume_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> dict[str, object]:
    _ = project_id
    return await _update_volume(id, request, conn, ctx)


@router.post("/v3/{project_id}/volumes", status_code=202)
@router.post("/v3/volumes", status_code=202)
async def create_volume(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    _ = project_id
    payload = (await request.json()).get("volume") or {}
    defaults = (
        await fetch_doc(conn, service="cinder", resource_type="volume_defaults", name="default")
        or {}
    )
    size = int(
        payload.get("size") if payload.get("size") is not None else defaults.get("size") or 1
    )
    row = await conn.fetchrow(
        """INSERT INTO os_volumes(id, project_id, name, status, size, volume_type, bootable)
           VALUES($1, $2, $3, 'available', $4, $5, $6)
           RETURNING *""",
        uuid4(),
        ctx.project_id,
        payload.get("name") if payload.get("name") is not None else defaults.get("name") or "",
        size,
        payload.get("volume_type") or defaults.get("volume_type"),
        bool(payload.get("bootable", False)),
    )
    return {"volume": _volume(row)}


@router.delete("/v3/{project_id}/volumes/{volume_id}", status_code=202)
@router.delete("/v3/volumes/{volume_id}", status_code=202)
async def delete_volume(
    volume_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> Response:
    _ = project_id
    result = await conn.execute(
        "DELETE FROM os_volumes WHERE id = $1::uuid AND project_id = $2",
        volume_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("ItemNotFound", "Volume could not be found", status_code=404)
    return Response(status_code=202)


@router.post("/v3/{project_id}/volumes/{volume_id}/action", status_code=202)
@router.post("/v3/volumes/{volume_id}/action", status_code=202)
async def volume_action(
    volume_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
    project_id: str | None = None,
) -> Response:
    """Lab subset of Cinder volume actions (os-extend, etc.)."""
    _ = project_id
    payload = await request.json()
    row = await conn.fetchrow(
        "SELECT * FROM os_volumes WHERE id = $1::uuid AND project_id = $2",
        volume_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("ItemNotFound", "Volume could not be found", status_code=404)

    if "os-extend" in payload:
        new_size = int((payload.get("os-extend") or {}).get("new_size") or 0)
        if new_size <= int(row["size"]):
            raise OpenStackError(
                "InvalidInput",
                "new_size must be greater than current size",
                status_code=400,
            )
        await conn.execute(
            """UPDATE os_volumes
               SET size = $1, updated_at = now()
               WHERE id = $2::uuid AND project_id = $3""",
            new_size,
            volume_id,
            ctx.project_id,
        )
        return Response(status_code=202)

    # Persist any other recognized lab action against the volume in PostgreSQL.
    import json
    from uuid import uuid4

    action = next(iter(payload.keys()), "action") if isinstance(payload, dict) else "action"
    status_map = {
        "os-reserve": "in-use",
        "os-unreserve": "available",
        "os-attach": "in-use",
        "os-detach": "available",
        "os-begin_detaching": "in-use",
        "os-roll_detaching": "in-use",
        "os-force_detach": "available",
        "os-reset_status": str(
            ((payload.get("os-reset_status") or {}) if isinstance(payload, dict) else {}).get(
                "status"
            )
            or row["status"]
        ),
        "os-set_bootable": row["status"],
        "os-retype": row["status"],
        "os-migrate_volume": row["status"],
        "os-start": row["status"],
        "os-stop": row["status"],
    }
    new_status = status_map.get(str(action), row["status"])
    await conn.execute(
        "UPDATE os_volumes SET status=$1, updated_at=now() WHERE id=$2::uuid AND project_id=$3",
        new_status,
        volume_id,
        ctx.project_id,
    )
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'cinder','volume_action',$2,$3,'DONE',$4::jsonb)""",
        uuid4(),
        ctx.project_id,
        f"{volume_id}:{action}",
        json.dumps({"volume_id": volume_id, "action": action, "payload": payload}),
    )
    return Response(status_code=202)
