#!/usr/bin/env python3
"""Write docs/api_coverage.md from OpenStack contract packs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    series = sys.argv[1] if len(sys.argv) > 1 else "dalmatian"
    pack_root = ROOT / "contracts" / "openstack"
    man_path = pack_root / series / "manifest.json"
    if not man_path.is_file():
        print(f"missing {man_path}", file=sys.stderr)
        return 1
    man = json.loads(man_path.read_text())

    series_rows: list[str] = []
    for path in sorted(pack_root.glob("*/manifest.json")):
        other = json.loads(path.read_text())
        series_rows.append(
            f"| {str(other['series']).title()} | {other['major']} | {other['operation_count']} |"
        )

    lines = [
        f"# OpenStack API coverage — {man['series']}",
        "",
        f"Generated from `contracts/openstack/{series}/manifest.json`.",
        "",
        f"- **Services:** {man['service_count']}",
        f"- **Operations:** {man['operation_count']}",
        f"- **Checksum:** `{man['checksum']}`",
        f"- **Generated at:** {man.get('generated_at', '')}",
        "",
        "## Series deltas",
        "",
        "| Series | Major | Operations |",
        "|---|---:|---:|",
        *series_rows,
        "",
        "Older series omit paths introduced later (`tools/os_api_inventory/series_deltas.py`)",
        "and use lower microversion ceilings. Apply a pack in the Environment drawer to hot-swap.",
        "",
        "Surface-complete means every operation in the pack is mounted by the schema engine",
        "(specialized routers still win on overlapping stateful paths).",
        "",
        "| Service | Type | Port | Operations | Microversions |",
        "|---|---|---:|---:|---|",
    ]
    for svc in sorted(man["services"], key=lambda s: s["name"]):
        mv = ""
        if svc.get("default_microversion"):
            mv = f"{svc['default_microversion']}–{svc.get('max_microversion') or '?'}"
        lines.append(
            f"| {svc['name']} | {svc['type']} | {svc['port']} | {svc['operation_count']} | {mv or '—'} |"
        )
    lines.extend(
        [
            "",
            "## Core minimums",
            "",
            "| Service | Required | Actual |",
            "|---|---:|---:|",
        ]
    )
    by_name = {s["name"]: s for s in man["services"]}
    for svc, required in (man.get("min_core_operations") or {}).items():
        actual = by_name.get(svc, {}).get("operation_count", 0)
        status = "OK" if actual >= required else "GAP"
        lines.append(f"| {svc} | {required} | {actual} ({status}) |")
    lines.append("")
    out = ROOT / "docs" / "api_coverage.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out} ({man['operation_count']} ops)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
