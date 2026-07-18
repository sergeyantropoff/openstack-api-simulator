"""Seed ``os_api_objects`` rows for every contract pack resource_type.

Ensures list GETs across all OpenStack series have persistent DB rows
(so list/show handlers serve PostgreSQL rows only).
"""

from __future__ import annotations

import json
from typing import Any

from asyncpg import Connection

from app.openstack.contract_loader import list_series, load_series_pack
from app.openstack.ids import oid


def _default_payload(service: str, resource_type: str, name: str, index: int) -> dict[str, Any]:
    """Reasonable lab JSON per resource family."""

    base: dict[str, Any] = {
        "name": name,
        "status": "ACTIVE",
        "enabled": True,
        "description": f"lab {service} {resource_type} {index}",
        "index": index,
    }
    # Light resource-specific hints for common clients.
    if resource_type in {"share", "volume", "backup", "share_snapshot"}:
        base.update({"size": 10, "status": "available"})
    elif resource_type in {"zone", "tld"}:
        base.update({"email": "hostmaster@lab.example", "ttl": 3600, "type": "PRIMARY"})
    elif resource_type in {"alarm"}:
        base.update({"type": "threshold", "state": "ok"})
    elif resource_type in {"queue"}:
        base.update({"_default_message_ttl": 3600})
    elif resource_type in {"cluster"}:
        base.update({"coe": "kubernetes", "status": "CREATE_COMPLETE", "node_count": 2})
    elif resource_type in {"container"} and service == "zun":
        base.update({"image": "cirros", "status": "Running"})
    elif resource_type in {"container"} and service == "barbican":
        base.update({"type": "generic", "status": "ACTIVE"})
    elif resource_type in {"secret"}:
        base.update({"secret_type": "passphrase", "payload_content_type": "text/plain"})
    elif resource_type in {"datastore"}:
        base.update({"type": "mysql", "version": "8.0"})
    elif resource_type in {"instance"} and service == "trove":
        base.update({"datastore": {"type": "mysql", "version": "8.0"}, "status": "ACTIVE"})
    elif resource_type in {"workflow", "workbook"}:
        base.update({"definition": "version: '2.0'\ndemo:\n  tasks: {}"})
    elif resource_type in {"dataframes"}:
        base.update({"period": "3600"})
    elif resource_type in {"quota", "quota_set"}:
        base.update({"limit": 100, "in_use": index})
    elif resource_type in {"status", "service_status", "health"}:
        base.update({"status": "UP", "state": "up", "service": service})
    elif resource_type == "ping":
        base.update({"ping": "pong", "ok": True})
    elif resource_type == "driver" and service == "ironic":
        base.update({"hosts": ["simulator"], "type": "classic"})
    elif resource_type == "agent" and service == "neutron":
        base.update(
            {
                "agent_type": "L3 agent",
                "host": f"network-{index}",
                "alive": True,
                "admin_state_up": True,
            }
        )
    elif resource_type == "console_output":
        base.update({"output": "Booting...\nSimulator console\n"})
    elif resource_type == "console":
        base.update(
            {"type": "novnc", "url": "https://127.0.0.1:6080/vnc_auto.html?token=simulator"}
        )
    return base


def iter_pack_resource_types(*, series: str | None = None) -> set[tuple[str, str]]:
    """Return ``{(service, resource_type)}`` declared by GET collection/detail/custom ops."""

    series_names = [series] if series else [str(item["series"]) for item in list_series()]
    found: set[tuple[str, str]] = set()
    for name in series_names:
        packs = load_series_pack(name)
        for pack in packs.values():
            for op in pack.operations:
                if op.method != "GET":
                    continue
                if op.kind not in {"collection", "detail", "custom"}:
                    continue
                if not op.resource_type or op.resource_type in {"version", "ping"}:
                    continue
                found.add((pack.name, op.resource_type))
    return found


async def seed_pack_surface_samples(
    conn: Connection,
    *,
    series: str | None = None,
    per_type: int = 3,
    project_id: Any | None = None,
) -> dict[str, int]:
    """Insert lab rows for every pack resource_type (idempotent via stable oid)."""

    types = iter_pack_resource_types(series=series)
    inserted = 0
    for service, resource_type in sorted(types):
        for index in range(per_type):
            name = f"{resource_type}-{index}"
            item_id = oid(f"packseed:{service}:{resource_type}:{name}")
            payload = _default_payload(service, resource_type, name, index)
            payload["id"] = str(item_id)
            status = str(payload.get("status") or "ACTIVE")
            result = await conn.execute(
                """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                   VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)
                   ON CONFLICT (id) DO NOTHING""",
                item_id,
                service,
                resource_type,
                project_id,
                name,
                status,
                json.dumps(payload),
            )
            # asyncpg: "INSERT 0 1" on insert, "INSERT 0 0" on conflict skip
            if result.split()[-1] == "1":
                inserted += 1
    return {"resource_types": len(types), "rows_inserted": inserted, "per_type": per_type}
