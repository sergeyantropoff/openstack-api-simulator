"""Service catalog builders — loaded from PostgreSQL discovery seed."""

from __future__ import annotations

import json
from typing import Any

from asyncpg import Connection

from app.openstack.db_docs import require_doc
from app.openstack.errors import OpenStackError
from app.openstack.surface import catalog_entries


def public_base(host: str, port: int, *, scheme: str = "http") -> str:
    host = host.split("%")[0]
    return f"{scheme}://{host}:{port}"


def build_catalog(host: str, *, scheme: str = "http") -> list[dict[str, Any]]:
    """Sync helper for offline tests/tools (no DB). Runtime catalog uses DB only."""

    return catalog_entries(host, scheme=scheme)


async def build_catalog_from_db(
    conn: Connection,
    host: str,
    *,
    scheme: str = "http",
) -> list[dict[str, Any]]:
    """Render Keystone catalog from the seeded DB template."""

    doc = await require_doc(
        conn,
        service="keystone",
        resource_type="service_catalog_template",
        name="default",
    )
    catalog = doc.get("catalog") or doc.get("services") or []
    rendered = json.dumps(catalog).replace("__HOST__", host).replace("__SCHEME__", scheme)
    data = json.loads(rendered)
    if not isinstance(data, list):
        raise OpenStackError(
            "NotFound",
            "keystone/service_catalog_template/default has invalid catalog shape",
            status_code=404,
        )
    return data
