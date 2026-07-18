"""Build UI catalog / method payloads from OpenStack contract packs."""

from __future__ import annotations

import re
from typing import Any

from app.contracts.examples import path_param_example
from app.openstack.contract_loader import (
    ensure_loaded,
    load_series_pack,
    major_for_series,
    series_for_major,
)
from app.openstack.request_examples import body_fields_from_example, schema_example

_PATH_PARAM = re.compile(r"\{([^{}]+)\}")


def openstack_catalog_payload(major: int) -> dict[str, Any]:
    series = series_for_major(major)
    ensure_loaded(series)
    packs = load_series_pack(series)
    categories: list[dict[str, Any]] = []
    path_count = 0
    method_count = 0
    for name, pack in sorted(packs.items(), key=lambda item: item[0]):
        by_path: dict[str, list[dict[str, Any]]] = {}
        for op in pack.operations:
            by_path.setdefault(op.path, []).append(
                {
                    "verb": op.method,
                    "name": op.operation_id,
                    "description": op.notes or f"{op.kind} {op.resource_type}",
                    "protected": op.requires_auth,
                    "implemented": True,
                }
            )
        paths = [
            {"path": path, "methods": methods}
            for path, methods in sorted(by_path.items(), key=lambda item: item[0])
        ]
        path_count += len(paths)
        method_count += sum(len(item["methods"]) for item in paths)
        categories.append({"tag": name, "paths": paths})
    return {
        "major": major,
        "series": {
            "yoga": "Yoga",
            "antelope": "Antelope",
            "caracal": "Caracal",
            "dalmatian": "Dalmatian",
        }.get(series, series.title()),
        "source_version": f"openstack-{series}",
        "latest_version": series,
        "artifact_url": f"contracts/openstack/{series}",
        "bundled": True,
        "path_count": path_count,
        "method_count": method_count,
        "categories": categories,
        "catalog_kind": "openstack",
    }


def openstack_method_payload(
    *,
    major: int,
    path: str,
    verb: str,
    runtime_version: str | None,
) -> dict[str, Any]:
    series = series_for_major(major)
    packs = load_series_pack(series)
    verb_u = verb.upper()
    for pack in packs.values():
        for op in pack.operations:
            if op.path == path and op.method == verb_u:
                path_params = _PATH_PARAM.findall(path)
                path_fields = [
                    {
                        "name": name,
                        "type": "string",
                        "description": f"Path parameter {name}",
                        "optional": False,
                        "enum": [],
                        "example": path_param_example(name) or name,
                    }
                    for name in path_params
                ]
                body_fields: list[dict[str, Any]] = []
                body_example: dict[str, Any] = {}
                if op.method in {"POST", "PUT", "PATCH"}:
                    if op.request_schema:
                        example = schema_example(op.request_schema)
                        body_example = example if isinstance(example, dict) else {}
                        # PARAM drawer: nested leaves from body_example (oVirt-style).
                        body_fields = body_fields_from_example(body_example)
                    else:
                        # Schemas are required for write ops; keep a minimal
                        # envelope only as a last-resort safety net.
                        key = op.item_key or op.collection_key or "resource"
                        if op.kind == "action":
                            action = op.action_name or "os-start"
                            body_example = {action: None}
                            body_fields = body_fields_from_example(body_example)
                        else:
                            body_example = {key: {"name": "example"}}
                            body_fields = body_fields_from_example(body_example)
                return {
                    "major": major,
                    "series": series,
                    "path": path,
                    "verb": verb_u,
                    "name": op.operation_id,
                    "description": op.notes or f"{pack.name} {op.resource_type}",
                    "protected": op.requires_auth,
                    "implemented": True,
                    "runtime_version": runtime_version,
                    "path_fields": path_fields,
                    "query_fields": [
                        {
                            "name": "limit",
                            "type": "integer",
                            "description": "Max items",
                            "optional": True,
                            "enum": [],
                            "example": 25,
                        },
                        {
                            "name": "marker",
                            "type": "string",
                            "description": "Pagination marker (id)",
                            "optional": True,
                            "enum": [],
                            "example": "",
                        },
                    ]
                    if op.method == "GET" and op.kind in {"collection", "detail"}
                    else [],
                    "body_fields": body_fields,
                    "body_example": body_example,
                    "returns": {"type": "object"},
                    "permissions": [],
                    "service": pack.name,
                    "port": pack.port,
                }
    raise KeyError(f"{verb} {path}")


def openstack_series_majors(runtime_version: str | None = None) -> dict[str, object]:
    from app.openstack.contract_loader import list_series

    series = list_series()
    return {
        "runtime_version": runtime_version,
        "majors": [
            {
                "major": item["major"],
                "series": str(item["series"]).title(),
                "latest_version": item["series"],
                "artifact_url": f"contracts/openstack/{item['series']}",
                "bundled": True,
                "operation_count": item["operation_count"],
                "microversions": item.get("microversions") or [],
            }
            for item in sorted(series, key=lambda row: row["major"])
        ],
    }


def openstack_compatibility_payload(
    major: int,
    *,
    runtime_version: str | None = None,
    schema_ops_mounted: int | None = None,
) -> dict[str, Any]:
    """Compatibility summary from OpenStack pack ops (surface-complete packs)."""

    series = series_for_major(major)
    packs = load_series_pack(series)
    # Count every pack operation (same basis as pack operation_count). Path+/verb
    # alone is not unique across services (e.g. GET /v1).
    method_names: list[str] = []
    groups: dict[str, dict[str, int]] = {}
    for name, pack in sorted(packs.items(), key=lambda item: item[0]):
        counters = groups.setdefault(name, {"declared": 0, "implemented": 0, "verified": 0})
        for op in pack.operations:
            method_names.append(f"{op.method.upper()} [{name}] {op.path}")
            counters["declared"] += 1
            # Pack operations are mounted via specialized routers + schema engine.
            counters["implemented"] += 1

    method_names.sort()
    total = len(method_names)
    score = 1.0 if total else 1.0
    mounted = schema_ops_mounted if schema_ops_mounted is not None else total

    methods_by_verb: dict[str, int] = {}
    for name, pack in packs.items():
        _ = name
        for op in pack.operations:
            verb = op.method.upper()
            methods_by_verb[verb] = methods_by_verb.get(verb, 0) + 1

    def _level(count: int, methods: list[str] | None = None) -> dict[str, Any]:
        return {
            "count": count,
            "score": (count / total) if total else 1.0,
            "methods": methods if methods is not None else [],
        }

    # Compact method samples for UI (full list is large).
    sample = method_names[:40]

    return {
        "source_version": f"openstack-{series}",
        "catalog_version": f"openstack-{series}",
        "latest_version": series,
        "major": major,
        "series": series,
        "catalog_kind": "openstack",
        "runtime_version": runtime_version or f"openstack-{series}",
        "evidence_scope": "catalog",
        "total_declared": total,
        "schema_ops_mounted": mounted,
        "service_count": len(packs),
        "methods_by_verb": dict(sorted(methods_by_verb.items())),
        "levels": {
            "declared": _level(total, sample),
            "schema_only": _level(0),
            "implemented": _level(total, sample),
            "observed": _level(0),
            "verified": _level(0),
        },
        "groups": dict(sorted(groups.items())),
        "dimension_groups": {},
        "classifications": {
            # Store counts only — length of full method lists is expensive in the UI.
            "fully_compatible_count": total,
            "partially_compatible_count": 0,
            "incompatible_count": 0,
            "regressions_count": 0,
            "unsupported_count": 0,
            "fully_compatible": [],
            "partially_compatible": [],
            "incompatible": [],
            "regressions": [],
            "unsupported": [],
        },
        "dimensions": {
            "route_method": {
                "count": total,
                "score": score,
                "methods": sample,
            }
        },
    }


# silence unused import warning helpers
_ = major_for_series
