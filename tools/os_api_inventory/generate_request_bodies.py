#!/usr/bin/env python3
"""Generate contracts/openstack/request_bodies/*.json for all pack write ops."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from os_api_inventory.request_body_catalog import schema_for_operation  # noqa: E402

SERIES_DEFAULT = "dalmatian"
OUT_DIR = ROOT / "contracts" / "openstack" / "request_bodies"


def _load_ops(series: str) -> dict[str, list[dict]]:
    series_dir = ROOT / "contracts" / "openstack" / series
    by_service: dict[str, list[dict]] = {}
    for api in sorted(series_dir.glob("*/api.json")):
        data = json.loads(api.read_text())
        service = str(data["service"])
        writes = [
            op
            for op in data.get("operations") or []
            if op.get("method") in {"POST", "PUT", "PATCH"}
        ]
        by_service[service] = writes
    return by_service


def generate(series: str, out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    # Merge ops across series for max coverage of operation_ids.
    merged: dict[str, dict[str, dict]] = defaultdict(dict)
    for series_name in ("yoga", "antelope", "caracal", "dalmatian"):
        if series and series != "all" and series_name != series:
            continue
        for service, ops in _load_ops(series_name).items():
            for op in ops:
                oid = op["operation_id"]
                path_key = f"{op['method']} {op['path']}"
                merged[service][oid] = op
                # also keep path index later
                _ = path_key

    for service, by_oid in sorted(merged.items()):
        operations: dict[str, dict] = {}
        by_path: dict[str, dict] = {}
        for oid, op in sorted(by_oid.items()):
            schema = schema_for_operation(op)
            operations[oid] = schema
            by_path[f"{op['method']} {op['path']}"] = schema
        payload = {
            "service": service,
            "source": "generated-from-api-ref-catalog",
            "operations": operations,
            "by_path": by_path,
        }
        path = out_dir / f"{service}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        counts[service] = len(operations)
    return counts


def coverage_report(series: str) -> int:
    from app.openstack.contract_loader import load_series_pack
    from app.openstack.request_bodies import clear_request_body_cache, missing_write_schemas

    clear_request_body_cache()
    packs = load_series_pack(series)
    missing = missing_write_schemas(packs)
    print(f"series={series} missing={len(missing)}")
    for service, method, path, oid in missing[:50]:
        print(f"  {service} {method} {path} ({oid})")
    if len(missing) > 50:
        print(f"  ... and {len(missing) - 50} more")
    return len(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", default="all", help="Series to scan or 'all'")
    parser.add_argument("--coverage", action="store_true", help="Report missing schemas only")
    parser.add_argument(
        "--coverage-series",
        default=SERIES_DEFAULT,
        help="Series for coverage check (default: dalmatian)",
    )
    args = parser.parse_args()
    if args.coverage:
        missing = coverage_report(args.coverage_series)
        return 1 if missing else 0
    series = None if args.series == "all" else args.series
    counts = generate(series or "all", OUT_DIR)
    total = sum(counts.values())
    print(f"Wrote {len(counts)} services, {total} operation schemas → {OUT_DIR}")
    for name, count in sorted(counts.items()):
        print(f"  {name}: {count}")
    if args.series == "all":
        # Coverage check requires the project venv (Python 3.13 dataclasses).
        print("Run coverage with: python tools/os_api_inventory/generate_request_bodies.py --coverage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
