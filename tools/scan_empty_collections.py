#!/usr/bin/env python3
"""Scan GET collection endpoints for empty list payloads across all series."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.openstack.contract_loader import list_series, load_series_pack  # noqa: E402
from app.openstack.surface_probe import (  # noqa: E402
    activate_series,
    fill_path,
    http_request,
    issue_token,
)


def _is_empty_list_payload(body: object) -> tuple[bool, str | None]:
    if not isinstance(body, dict):
        return False, None
    if body.get("data") == []:
        return True, "data"
    for key, value in body.items():
        if key in {"links", "metadata", "versions", "version", "id", "status"}:
            continue
        if isinstance(value, list) and len(value) == 0:
            return True, key
    return False, None


def _is_top_level_collection(op) -> bool:  # noqa: ANN001
    if op.method != "GET":
        return False
    if op.kind in {"collection", "detail"}:
        return "{" not in op.path or op.path.rstrip("/").endswith("/detail")
    if op.kind == "custom" and "{" not in op.path:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="http://api-gateway:5000")
    parser.add_argument("--series", action="append", default=[])
    args = parser.parse_args()
    host = args.host.rstrip("/")
    if args.series:
        series_list = args.series
    else:
        series_list = [str(item["series"]) for item in list_series()]

    token, _ = issue_token(host, user="admin", project="admin")
    empties: list[tuple[str, str, str, str, str | None, int, str | None]] = []
    checked = 0

    for series in series_list:
        activate_series(host, series)
        packs = load_series_pack(series)
        for name, pack in sorted(packs.items()):
            for op in pack.operations:
                if not _is_top_level_collection(op):
                    continue
                path = fill_path(op.path)
                status, body = http_request("GET", f"{host}{path}", token=token, service=name)
                checked += 1
                empty, key = _is_empty_list_payload(body)
                if empty:
                    empties.append(
                        (
                            series,
                            name,
                            op.path,
                            op.resource_type,
                            op.collection_key,
                            status,
                            key,
                        )
                    )

    by_path: dict[tuple[str, str, str, str | None], list[str]] = defaultdict(list)
    for series, svc, path, rtype, ckey, _status, _key in empties:
        by_path[(svc, rtype, path, ckey)].append(series)

    print(json.dumps({"checked": checked, "empty": len(empties), "unique": len(by_path)}, indent=2))
    print("\n=== EMPTY COLLECTIONS ===")
    for (svc, rtype, path, ckey), serieses in sorted(by_path.items()):
        print(
            f"{svc:12} {rtype:28} key={str(ckey):24} {path}  "
            f"series={','.join(sorted(set(serieses)))}"
        )
    return 0 if not by_path else 1


if __name__ == "__main__":
    raise SystemExit(main())
