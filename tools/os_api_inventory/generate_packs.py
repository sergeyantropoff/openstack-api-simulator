#!/usr/bin/env python3
"""Generate contracts/openstack/<series> API packs from the inventory catalog."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running as script from repo root or tools dir.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from os_api_inventory.catalog import SERIES, SERVICES_META, build_all_operations  # noqa: E402
from os_api_inventory.series_deltas import (  # noqa: E402
    filter_ops_for_series,
    microversions_for,
)


def _dedupe(ops: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for op in ops:
        key = (op["method"], op["path"])
        if key in seen and op.get("kind") == "action" and op.get("action_name") not in {None, "*"}:
            continue
        if key in seen and op.get("kind") != "action":
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(op)
    return out


def _write_service(
    series_dir: Path,
    name: str,
    typ: str,
    port: int,
    version_path: str,
    default_mv: str | None,
    max_mv: str | None,
    ops: list[dict],
) -> dict:
    ops = _dedupe(ops)
    for op in ops:
        op.setdefault("requires_auth", True)
        op.setdefault("requires_project", True)
        op.setdefault("service", name)
        if default_mv:
            op.setdefault("microversion_min", "2.1" if name == "nova" else default_mv)
            op.setdefault("microversion_max", max_mv)
    payload = {
        "service": name,
        "type": typ,
        "port": port,
        "version_path": version_path,
        "default_microversion": default_mv,
        "max_microversion": max_mv,
        "operations": ops,
    }
    svc_dir = series_dir / name
    svc_dir.mkdir(parents=True, exist_ok=True)
    api_path = svc_dir / "api.json"
    raw = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    api_path.write_text(raw)
    checksum = hashlib.sha256(raw.encode()).hexdigest()
    return {
        "name": name,
        "type": typ,
        "port": port,
        "version_path": version_path,
        "default_microversion": default_mv,
        "max_microversion": max_mv,
        "operation_count": len(ops),
        "checksum": checksum,
    }


def generate(series: str, major: int, out_root: Path) -> Path:
    series_dir = out_root / series
    series_dir.mkdir(parents=True, exist_ok=True)
    all_ops = build_all_operations()
    services_info: list[dict] = []
    total = 0
    for name, typ, port, version_path, default_mv, max_mv in SERVICES_META:
        ops = filter_ops_for_series(all_ops.get(name, []), series)
        mv_min, mv_max = microversions_for(series, name, default_mv, max_mv)
        info = _write_service(series_dir, name, typ, port, version_path, mv_min, mv_max, ops)
        services_info.append(info)
        total += info["operation_count"]

    # Soften min gates for older trimmed series while keeping core identity/compute/network.
    min_core = {"keystone": 40, "nova": 70, "neutron": 70}
    if series == "yoga":
        min_core = {"keystone": 40, "nova": 70, "neutron": 60}

    manifest = {
        "series": series,
        "major": major,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "service_count": len(services_info),
        "operation_count": total,
        "services": services_info,
        "min_core_operations": min_core,
    }
    root = Path(__file__).resolve().parents[0]
    # Annotate series differentiation for operators.
    joined = "|".join(s["checksum"] for s in services_info)
    manifest["checksum"] = hashlib.sha256(joined.encode()).hexdigest()
    (series_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    by_name = {s["name"]: s for s in services_info}
    for svc, minimum in manifest["min_core_operations"].items():
        if by_name[svc]["operation_count"] < minimum:
            raise SystemExit(
                f"{series}/{svc}: {by_name[svc]['operation_count']} ops < required {minimum}"
            )
    _ = root
    return series_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "contracts" / "openstack",
        help="Output root for series packs",
    )
    parser.add_argument("--series", action="append", help="Limit to series (repeatable)")
    args = parser.parse_args()
    selected = {s.lower() for s in args.series} if args.series else None
    for series, major in SERIES:
        if selected and series not in selected:
            continue
        path = generate(series, major, args.out)
        man = json.loads((path / "manifest.json").read_text())
        print(
            f"{series}: {man['operation_count']} operations across {man['service_count']} services"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
