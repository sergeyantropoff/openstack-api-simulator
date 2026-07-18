"""Glance Image API v2 (lab subset)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token, require_token
from app.openstack.errors import OpenStackError

router = APIRouter(tags=["Glance"])


def _image(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "status": row["status"],
        "visibility": row["visibility"],
        "size": row["size"],
        "disk_format": row["disk_format"],
        "container_format": row["container_format"],
        "min_disk": 0,
        "min_ram": 0,
        "protected": False,
        "checksum": None,
        "owner": str(row["owner_project_id"]) if row["owner_project_id"] else None,
        "created_at": row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": row["updated_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tags": [],
        "file": f"/v2/images/{row['id']}/file",
        "schema": "/v2/schemas/image",
    }


@router.get("/v2")
@router.get("/v2/")
async def glance_versions(conn: Annotated[Connection, Depends(get_conn)]) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(
        conn, service="glance", resource_type="discovery_version", name="default"
    )


@router.get("/v2/images")
async def list_images(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    name = request.query_params.get("name")
    if name:
        rows = list(
            await conn.fetch(
                """SELECT * FROM os_images
                   WHERE (visibility = 'public' OR owner_project_id = $1)
                     AND name = $2
                   ORDER BY created_at, id""",
                ctx.project_id,
                name,
            )
        )
    else:
        rows = list(
            await conn.fetch(
                """SELECT * FROM os_images
                   WHERE visibility = 'public'
                      OR owner_project_id = $1
                   ORDER BY created_at, id""",
                ctx.project_id,
            )
        )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {
        "images": [_image(r) for r in page],
        "first": "/v2/images",
        "schema": "/v2/schemas/images",
    }
    if links:
        body["images_links"] = links
    return body


async def _show_image(
    resource_id: str,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, Any]:
    row = await conn.fetchrow(
        """SELECT * FROM os_images
           WHERE (id::text = $1 OR name = $1)
             AND (visibility = 'public' OR owner_project_id = $2)
           ORDER BY CASE WHEN id::text = $1 THEN 0 ELSE 1 END
           LIMIT 1""",
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("ImageNotFound", "Image not found", status_code=404)
    return _image(row)


@router.get("/v2/images/{image_id}")
async def show_image(
    image_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    return await _show_image(image_id, conn, ctx)


@router.get("/v2/images/{id}")
async def show_image_by_id(
    id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    return await _show_image(id, conn, ctx)


async def _update_image(
    resource_id: str,
    request: Request,
    conn: Connection,
    ctx: TokenContext,
) -> dict[str, Any]:
    payload = await request.json()
    body = payload.get("image") if isinstance(payload.get("image"), dict) else payload
    row = await conn.fetchrow(
        """UPDATE os_images
           SET name = COALESCE($1, name), updated_at = now()
           WHERE id = $2::uuid AND owner_project_id = $3
           RETURNING *""",
        body.get("name") if isinstance(body, dict) else None,
        resource_id,
        ctx.project_id,
    )
    if row is None:
        raise OpenStackError("ImageNotFound", "Image not found", status_code=404)
    return _image(row)


@router.put("/v2/images/{image_id}")
@router.patch("/v2/images/{image_id}")
async def update_image(
    image_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, Any]:
    return await _update_image(image_id, request, conn, ctx)


@router.put("/v2/images/{id}")
@router.patch("/v2/images/{id}")
async def update_image_by_id(
    id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, Any]:
    return await _update_image(id, request, conn, ctx)


@router.post("/v2/images", status_code=201)
async def create_image(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import fetch_doc

    payload = await request.json()
    defaults = (
        await fetch_doc(conn, service="glance", resource_type="image_defaults", name="default")
        or {}
    )
    image_id = uuid4()
    row = await conn.fetchrow(
        """INSERT INTO os_images(id, name, status, visibility, size, disk_format,
               container_format, owner_project_id)
           VALUES($1, $2, 'queued', $3, 0, $4, $5, $6)
           RETURNING *""",
        image_id,
        payload.get("name") or defaults.get("name") or "image",
        payload.get("visibility") or defaults.get("visibility"),
        payload.get("disk_format") or defaults.get("disk_format"),
        payload.get("container_format") or defaults.get("container_format"),
        ctx.project_id,
    )
    return _image(row)


@router.get("/v2/images/{image_id}/file")
async def download_image_file(
    image_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    row = await conn.fetchrow(
        """SELECT id, size FROM os_images
           WHERE (id::text=$1 OR name=$1)
             AND (owner_project_id=$2 OR visibility='public')
           LIMIT 1""",
        image_id,
        ctx.project_id,
    )
    if row is None:
        # Materialize pack/schema image rows into os_images on first download.
        api = await conn.fetchrow(
            """SELECT id, name, data FROM os_api_objects
               WHERE service='glance' AND resource_type='image'
                 AND (id::text=$1 OR name=$1)
               LIMIT 1""",
            image_id,
        )
        if api is None:
            raise OpenStackError("ImageNotFound", f"image {image_id} not found", status_code=404)
        data = api["data"]
        if isinstance(data, str):
            import json as _json

            data = _json.loads(data or "{}")
        await conn.execute(
            """INSERT INTO os_images(id, name, status, visibility, size, disk_format,
                   container_format, owner_project_id)
               VALUES($1::uuid,$2,'active',$3,$4,$5,$6,$7)
               ON CONFLICT (id) DO UPDATE SET updated_at=now()""",
            api["id"],
            api["name"] or (data or {}).get("name") or "image",
            (data or {}).get("visibility") or "private",
            int((data or {}).get("size") or 0),
            (data or {}).get("disk_format") or "qcow2",
            (data or {}).get("container_format") or "bare",
            ctx.project_id,
        )
        size = int((data or {}).get("size") or 0)
    else:
        size = int(row["size"] or 0)
    # Lab payload is capped; Content-Length must match the bytes we actually send
    # (advertising the virtual image size breaks urllib/clients with IncompleteRead).
    content = b"\0" * min(size, 64) if size else b"probe-image"
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Length": str(len(content))},
    )


@router.put("/v2/images/{image_id}/file", status_code=204)
async def upload_image_file(
    image_id: str,
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    body = await request.body()
    result = await conn.execute(
        """UPDATE os_images
           SET status = 'active', size = $1, updated_at = now()
           WHERE (id::text = $2 OR name = $2) AND owner_project_id = $3""",
        len(body),
        image_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("ImageNotFound", "Image not found", status_code=404)
    return Response(status_code=204)


@router.delete("/v2/images/{image_id}", status_code=204)
async def delete_image(
    image_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> Response:
    result = await conn.execute(
        "DELETE FROM os_images WHERE id = $1::uuid AND owner_project_id = $2",
        image_id,
        ctx.project_id,
    )
    if result.endswith("0"):
        raise OpenStackError("ImageNotFound", "Image not found", status_code=404)
    return Response(status_code=204)


@router.get("/v2/info/stores")
async def glance_stores(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(conn, service="glance", resource_type="info_stores", name="default")


@router.get("/v2/info/import")
async def glance_import_info(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(conn, service="glance", resource_type="info_import", name="default")


@router.get("/v2/schemas/image")
async def glance_schema_image(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(conn, service="glance", resource_type="schema", name="image")


@router.get("/v2/schemas/images")
async def glance_schema_images(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_project_token)],
) -> dict[str, object]:
    from app.openstack.db_docs import require_doc

    return await require_doc(conn, service="glance", resource_type="schema", name="images")
