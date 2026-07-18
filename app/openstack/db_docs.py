"""Read JSON documents stored in ``os_api_objects`` (discovery, schemas, catalog)."""

from __future__ import annotations

import json
from typing import Any

from asyncpg import Connection

from app.openstack.errors import OpenStackError
from app.openstack.ids import oid


async def fetch_doc(
    conn: Connection,
    *,
    service: str,
    resource_type: str,
    name: str = "default",
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """SELECT data FROM os_api_objects
           WHERE service=$1 AND resource_type=$2 AND name=$3
           ORDER BY updated_at DESC
           LIMIT 1""",
        service,
        resource_type,
        name,
    )
    if row is None:
        return None
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    return dict(data or {})


async def require_doc(
    conn: Connection,
    *,
    service: str,
    resource_type: str,
    name: str = "default",
) -> dict[str, Any]:
    doc = await fetch_doc(conn, service=service, resource_type=resource_type, name=name)
    if doc is None:
        raise OpenStackError(
            "NotFound",
            f"{service}/{resource_type}/{name} not seeded in database",
            status_code=404,
        )
    return doc


async def list_docs(
    conn: Connection,
    *,
    service: str,
    resource_type: str,
) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """SELECT id, name, status, data FROM os_api_objects
           WHERE service=$1 AND resource_type=$2
           ORDER BY created_at NULLS LAST, name""",
        service,
        resource_type,
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data or {})
        data.setdefault("id", str(row["id"]))
        data.setdefault("name", row["name"])
        data.setdefault("status", row["status"])
        items.append(data)
    return items


async def upsert_doc(
    conn: Connection,
    *,
    service: str,
    resource_type: str,
    name: str,
    data: dict[str, Any],
    project_id: Any | None = None,
    status: str = "ACTIVE",
) -> None:
    item_id = oid(f"doc:{service}:{resource_type}:{name}")
    payload = {"id": str(item_id), "name": name, **data}
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)
           ON CONFLICT (id) DO UPDATE SET
             data=EXCLUDED.data, status=EXCLUDED.status, updated_at=now()""",
        item_id,
        service,
        resource_type,
        project_id,
        name,
        status,
        json.dumps(payload),
    )
