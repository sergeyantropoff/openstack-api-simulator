#!/usr/bin/env python3
"""Probe every pack operation for Yoga → Dalmatian against the live gateway."""

from __future__ import annotations

import argparse
import os
import sys

# Allow `python examples/python/openstack_surface_probe.py` from repo / container.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.openstack.surface_probe import format_report, probe_series  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("OS_HOST", "http://127.0.0.1:5000"))
    parser.add_argument(
        "--series",
        action="append",
        help="Limit to series (repeatable). Default: all four.",
    )
    parser.add_argument(
        "--collections-only",
        action="store_true",
        help="Only GET endpoints without path parameters (faster smoke).",
    )
    parser.add_argument(
        "--no-lifecycle",
        action="store_true",
        help="Random-UUID shallow probe (accepts 404) instead of create→CRUD lifecycle.",
    )
    parser.add_argument(
        "--methods",
        default="",
        help="Comma-separated methods filter (e.g. GET,POST)",
    )
    args = parser.parse_args()
    series_list = args.series or ["yoga", "antelope", "caracal", "dalmatian"]
    methods = frozenset(m.strip().upper() for m in args.methods.split(",") if m.strip()) or None
    failed = 0
    for series in series_list:
        report = probe_series(
            series,
            host=args.host,
            methods=methods,
            collections_only=args.collections_only,
            lifecycle=not args.no_lifecycle and not args.collections_only,
        )
        print(format_report(report))
        failed += len(report.failures)
    if failed:
        print(f"FAILED total={failed}")
        return 1
    print("OK all probed operations returned acceptable statuses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
