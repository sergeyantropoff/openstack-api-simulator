"""HTTP pack coverage with completeness and non-empty body checks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from _lib.validate import payload_nonempty

# Methods that normally return a JSON body on success (DELETE / 204 may be empty).
_BODY_METHODS = frozenset({"GET", "POST", "PUT", "PATCH"})


def _expected_ops(packs: dict[str, Any], *, collections_only: bool) -> int:
    if not collections_only:
        return sum(len(p.operations) for p in packs.values())
    total = 0
    for pack in packs.values():
        for op in pack.operations:
            if op.method == "GET" and "{" not in op.path:
                total += 1
    return total


def _methods_breakdown(results: list[Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for r in results:
        method = getattr(r, "method", None) or (r.get("method") if isinstance(r, dict) else None)
        if method:
            counts[str(method).upper()] += 1
    return {m: counts.get(m, 0) for m in ("GET", "POST", "PUT", "PATCH", "DELETE")}


def _nonempty_from_lifecycle(report: Any) -> list[dict[str, Any]]:
    """Check succeeded lifecycle bodies (skip DELETE / 204 / 202 / no-body)."""
    failures: list[dict[str, Any]] = []
    for r in report.results:
        if not r.succeeded:
            continue
        if r.method == "DELETE" or r.status in {202, 204}:
            continue
        if r.method not in _BODY_METHODS:
            continue
        # OpenStack often returns 200/201 with an empty body (Swift PUT, tag put).
        if r.payload is None:
            continue
        if not payload_nonempty(r.payload, collection_key=r.collection_key, method=r.method):
            failures.append(
                {
                    "service": r.service,
                    "operation_id": r.operation_id,
                    "method": r.method,
                    "path": r.path,
                    "status": r.status,
                    "detail": "empty response body",
                    "ok": False,
                    "nonempty": False,
                }
            )
    return failures


def _nonempty_smoke_collections(
    series: str,
    *,
    host: str,
    packs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Re-check collection GET bodies for smoke mode (stable seed data)."""
    from app.openstack.surface_probe import (
        SUCCESS,
        fill_path,
        http_request,
        issue_token,
        _seed_context,
    )

    token, auth_body = issue_token(host)
    project_id = str(((auth_body.get("token") or {}).get("project") or {}).get("id") or "")
    ctx = _seed_context(host, token, project_id)
    failures: list[dict[str, Any]] = []
    for name in sorted(packs):
        pack = packs[name]
        for op in pack.operations:
            if "{" in op.path or op.method != "GET":
                continue
            path = fill_path(
                op.path,
                {
                    **ctx,
                    "project_id": project_id,
                    "project": project_id,
                    "tenant_id": project_id,
                    "account": project_id,
                },
            )
            url = f"{host.rstrip('/')}{path}"
            status, payload = http_request(op.method, url, token=token, service=pack.name)
            if status not in SUCCESS or status == 204:
                continue
            if not payload_nonempty(payload, collection_key=op.collection_key, method=op.method):
                failures.append(
                    {
                        "service": pack.name,
                        "operation_id": op.operation_id,
                        "method": op.method,
                        "path": op.path,
                        "status": status,
                        "detail": "empty response body",
                        "ok": False,
                        "nonempty": False,
                    }
                )
    return failures


def probe_pack_operations(
    series: str,
    *,
    host: str,
    collections_only: bool = False,
    require_nonempty: bool = True,
) -> dict[str, Any]:
    from app.openstack.contract_loader import load_series_pack
    from app.openstack.surface_probe import probe_series

    report = probe_series(
        series,
        host=host,
        collections_only=collections_only,
        lifecycle=not collections_only,
    )

    packs = load_series_pack(series)
    expected_ops = _expected_ops(packs, collections_only=collections_only)
    methods = _methods_breakdown(report.results)
    coverage_incomplete = len(report.results) != expected_ops

    nonempty_failures: list[dict[str, Any]] = []
    if require_nonempty:
        if collections_only:
            nonempty_failures = _nonempty_smoke_collections(series, host=host, packs=packs)
        else:
            nonempty_failures = _nonempty_from_lifecycle(report)

    probe_failures = [
        {
            "service": r.service,
            "operation_id": r.operation_id,
            "method": r.method,
            "path": r.path,
            "status": r.status,
            "detail": r.detail,
            "ok": False,
            "nonempty": True,
        }
        for r in report.failures
    ]

    coverage_failures: list[dict[str, Any]] = []
    if coverage_incomplete:
        coverage_failures.append(
            {
                "service": "_coverage",
                "operation_id": "coverage_incomplete",
                "method": "*",
                "path": "*",
                "status": 0,
                "detail": f"coverage_incomplete: total={len(report.results)} expected_ops={expected_ops}",
                "ok": False,
                "nonempty": True,
            }
        )

    return {
        "series": series,
        "host": host,
        "mode": report.mode,
        "total": len(report.results),
        "expected_ops": expected_ops,
        "coverage_incomplete": coverage_incomplete,
        "methods": methods,
        "ok_count": len(report.results) - len(report.failures),
        "fail_count": len(report.failures) + (1 if coverage_incomplete else 0),
        "nonempty_fail_count": len(nonempty_failures),
        "results": [
            {
                "service": r.service,
                "method": r.method,
                "path": r.path,
                "operation_id": r.operation_id,
                "status": r.status,
                "detail": r.detail,
                "mode": r.mode,
                "ok": r.ok,
                "succeeded": r.succeeded,
            }
            for r in report.results
        ],
        "failures": coverage_failures + probe_failures + nonempty_failures,
    }


def write_probe_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
