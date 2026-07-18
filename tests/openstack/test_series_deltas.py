"""Series packs must differ across Yoga → Dalmatian."""

from __future__ import annotations

from tools.os_api_inventory.catalog import build_all_operations
from tools.os_api_inventory.series_deltas import filter_ops_for_series, series_index


def test_series_operation_counts_increase() -> None:
    all_ops = build_all_operations()
    flat = [op for ops in all_ops.values() for op in ops]
    counts = {
        series: len(filter_ops_for_series(flat, series))
        for series in ("yoga", "antelope", "caracal", "dalmatian")
    }
    assert counts["yoga"] < counts["antelope"] < counts["caracal"] < counts["dalmatian"]


def test_dalmatian_includes_yoga() -> None:
    nova = build_all_operations()["nova"]
    yoga_ids = {op["operation_id"] for op in filter_ops_for_series(nova, "yoga")}
    dal_ids = {op["operation_id"] for op in filter_ops_for_series(nova, "dalmatian")}
    assert yoga_ids <= dal_ids
    assert series_index("yoga") < series_index("dalmatian")
