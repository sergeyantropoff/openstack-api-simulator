"""Placement API (lab subset + demo inventory)."""

from __future__ import annotations

import json
from typing import Annotated, Any

from asyncpg import Connection
from fastapi import APIRouter, Depends

from app.openstack.auth import TokenContext
from app.openstack.db_docs import fetch_doc
from app.openstack.deps import get_conn, require_token

router = APIRouter(tags=["Placement"])


@router.get("/resource_providers")
async def list_resource_providers(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    defaults = await fetch_doc(
        conn, service="placement", resource_type="resource_provider_defaults", name="default"
    )
    default_generation = int((defaults or {}).get("generation") or 0)
    rows = await conn.fetch(
        """SELECT * FROM os_api_objects
           WHERE service='placement' AND resource_type='resource_provider'
           ORDER BY created_at, name"""
    )
    providers: list[dict[str, Any]] = []
    for row in rows:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data or {})
        providers.append(
            {
                "id": str(row["id"]),
                "uuid": str(row["id"]),
                "name": row["name"] or data.get("name") or str(row["id"]),
                "generation": int(
                    data.get("generation")
                    if data.get("generation") is not None
                    else default_generation
                ),
                "parent_provider_uuid": data.get("parent_provider_uuid"),
            }
        )
    return {"resource_providers": providers}


@router.get("/allocations/{consumer_uuid}")
async def show_allocations(
    consumer_uuid: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    defaults = await fetch_doc(
        conn, service="placement", resource_type="allocation_defaults", name="default"
    )
    default_resources = dict((defaults or {}).get("resources") or {})
    consumer_generation = int((defaults or {}).get("consumer_generation") or 0)
    rows = await conn.fetch(
        """SELECT * FROM os_api_objects
           WHERE service='placement' AND resource_type='allocation'
             AND (data->>'consumer_uuid'=$1 OR id::text=$1 OR name=$1)
           ORDER BY created_at""",
        consumer_uuid,
    )
    allocations: dict[str, Any] = {}
    for row in rows:
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = dict(data or {})
        rp = str(data.get("resource_provider") or data.get("resource_provider_id") or row["id"])
        resources = (
            data.get("resources") if isinstance(data.get("resources"), dict) else default_resources
        )
        allocations[rp] = {"resources": resources}
        if data.get("consumer_generation") is not None:
            consumer_generation = int(data["consumer_generation"])
    if not allocations and default_resources:
        allocations["00000000-0000-0000-0000-000000000001"] = {"resources": default_resources}
    elif not allocations:
        allocations["00000000-0000-0000-0000-000000000001"] = {
            "resources": {"VCPU": 1, "MEMORY_MB": 512}
        }
    return {"allocations": allocations, "consumer_generation": consumer_generation}
