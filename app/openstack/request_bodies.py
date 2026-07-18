"""Load and resolve OpenStack request-body JSON Schemas.

Schemas live in ``contracts/openstack/request_bodies/<service>.json`` and are
merged onto ``OperationSpec`` at pack load time (shared across series).
"""

from __future__ import annotations

import json
from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.openstack.opspec import OperationSpec

_BODIES_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "openstack" / "request_bodies"


def request_bodies_root() -> Path:
    return _BODIES_ROOT


@lru_cache(maxsize=1)
def _load_all() -> dict[str, dict[str, Any]]:
    root = request_bodies_root()
    out: dict[str, dict[str, Any]] = {}
    if not root.is_dir():
        return out
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text())
        service = str(data.get("service") or path.stem)
        ops = data.get("operations") or {}
        by_path = data.get("by_path") or {}
        out[service] = {"operations": dict(ops), "by_path": dict(by_path)}
    return out


def clear_request_body_cache() -> None:
    _load_all.cache_clear()


def _path_key(method: str, path: str) -> str:
    return f"{method.upper()} {path}"


def lookup_request_schema(service: str, op: OperationSpec) -> dict[str, Any] | None:
    """Return the JSON Schema for an operation, or None if missing."""

    store = _load_all().get(service) or {}
    ops = store.get("operations") or {}
    schema = ops.get(op.operation_id)
    if schema is None:
        schema = (store.get("by_path") or {}).get(_path_key(op.method, op.path))
    if schema is None:
        return None
    return _resolve_schema(schema, microversion=op.microversion_max)


def _resolve_schema(schema: dict[str, Any], *, microversion: str | None) -> dict[str, Any]:
    """Pick a concrete schema from OpenStack oneOf discriminators when present."""

    if not isinstance(schema, dict):
        return {}
    if "oneOf" in schema and isinstance(schema["oneOf"], list):
        xos = schema.get("x-openstack") or {}
        discriminator = xos.get("discriminator")
        variants = [item for item in schema["oneOf"] if isinstance(item, dict)]
        if discriminator == "action":
            # Prefer first variant; callers match action via separate ops.
            chosen = variants[0] if variants else schema
            return _resolve_schema(chosen, microversion=microversion)
        if discriminator == "microversion" and microversion:
            best: dict[str, Any] | None = None
            for item in variants:
                meta = item.get("x-openstack") or {}
                min_ver = str(meta.get("min-ver") or "0")
                max_ver = meta.get("max-ver")
                if _mv_le(min_ver, microversion) and (
                    max_ver is None or _mv_le(microversion, str(max_ver))
                ):
                    best = item
            if best is not None:
                return _resolve_schema(best, microversion=microversion)
        if variants:
            return _resolve_schema(variants[-1], microversion=microversion)
    return schema


def _mv_le(left: str, right: str) -> bool:
    def parts(value: str) -> tuple[int, ...]:
        out: list[int] = []
        for piece in value.split("."):
            try:
                out.append(int(piece))
            except ValueError:
                out.append(0)
        return tuple(out)

    return parts(left) <= parts(right)


def attach_request_schemas(service: str, ops: list[OperationSpec]) -> list[OperationSpec]:
    """Return new OperationSpec list with ``request_schema`` filled where known."""

    attached: list[OperationSpec] = []
    for op in ops:
        schema = lookup_request_schema(service, op)
        if schema is None:
            attached.append(op)
            continue
        attached.append(replace(op, request_schema=schema))
    return attached


def missing_write_schemas(packs: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """List (service, method, path, operation_id) missing request schemas."""

    missing: list[tuple[str, str, str, str]] = []
    for name, pack in sorted(packs.items()):
        for op in pack.operations:
            if op.method not in {"POST", "PUT", "PATCH"}:
                continue
            if op.request_schema:
                continue
            missing.append((name, op.method, op.path, op.operation_id))
    return missing
