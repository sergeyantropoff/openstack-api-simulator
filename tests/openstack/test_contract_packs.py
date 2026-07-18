"""Unit tests for OpenStack contract packs and loader."""

from __future__ import annotations

import json
from pathlib import Path

from app.openstack.contract_loader import (
    contracts_root,
    list_series,
    load_series_pack,
    major_for_series,
)


def test_all_series_packs_exist() -> None:
    series = {s["series"] for s in list_series()}
    assert {"yoga", "antelope", "caracal", "dalmatian"} <= series


def test_dalmatian_core_minimums() -> None:
    man = json.loads((contracts_root() / "dalmatian" / "manifest.json").read_text())
    by_name = {s["name"]: s for s in man["services"]}
    for svc, minimum in man["min_core_operations"].items():
        assert by_name[svc]["operation_count"] >= minimum
    assert man["operation_count"] >= 1300
    assert man["service_count"] == 28
    by_name = {s["name"]: s for s in man["services"]}
    assert "watcher" in by_name
    assert "zaqar" in by_name
    assert by_name["neutron"]["operation_count"] >= 250
    assert by_name["nova"]["operation_count"] >= 110


def test_load_series_pack_operations() -> None:
    packs = load_series_pack("dalmatian")
    assert "nova" in packs
    assert "neutron" in packs
    assert "watcher" in packs
    assert "zaqar" in packs
    nova = packs["nova"]
    methods = {(op.method, op.path) for op in nova.operations}
    assert ("GET", "/v2.1/servers") in methods
    assert ("POST", "/v2.1/servers/{id}/action") in methods
    assert ("GET", "/v2.1/extensions") in methods
    assert ("GET", "/v2.0/address-groups") in {
        (op.method, op.path) for op in packs["neutron"].operations
    }
    assert nova.max_microversion is not None


def test_major_mapping() -> None:
    assert major_for_series("dalmatian") == 9
    assert major_for_series("yoga") == 6


def test_api_json_files_present() -> None:
    root = contracts_root() / "dalmatian"
    services = [p for p in root.iterdir() if p.is_dir()]
    assert len(services) == 28
    for svc in services:
        assert (svc / "api.json").is_file()
