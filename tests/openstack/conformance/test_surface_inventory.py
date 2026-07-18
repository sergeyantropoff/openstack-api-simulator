"""Conformance: every pack operation has method+path and core services are complete."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.openstack.contract_loader import contracts_root, load_series_pack

CORE = ("keystone", "nova", "neutron", "glance", "cinder", "placement")
EXTRA = ("heat", "swift", "ironic", "octavia")
REMAINING = (
    "barbican",
    "manila",
    "designate",
    "magnum",
    "zun",
    "trove",
    "mistral",
    "aodh",
    "cloudkitty",
    "freezer",
    "blazar",
    "vitrage",
    "masakari",
    "tacker",
    "adjutant",
    "heat-cfn",
    "watcher",
    "zaqar",
)


@pytest.mark.parametrize("series", ["yoga", "antelope", "caracal", "dalmatian"])
def test_pack_operations_are_well_formed(series: str) -> None:
    packs = load_series_pack(series)
    for name, pack in packs.items():
        assert pack.port > 0
        assert pack.operations, name
        seen: set[tuple[str, str]] = set()
        for op in pack.operations:
            assert op.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"}
            assert op.path.startswith("/"), op.path
            assert op.operation_id
            key = (op.method, op.path)
            # duplicate method+path only allowed if both are actions collapsing
            if key in seen:
                assert op.kind == "action"
            seen.add(key)


@pytest.mark.parametrize("service", CORE)
def test_core_services_have_nested_or_actions(service: str) -> None:
    pack = load_series_pack("dalmatian")[service]
    paths = {op.path for op in pack.operations}
    assert any("{" in p for p in paths) or service == "keystone"
    if service == "nova":
        assert "/v2.1/servers/{id}/action" in paths
    if service == "neutron":
        assert "/v2.0/routers/{id}/add_router_interface" in paths or any(
            "add_router_interface" in p for p in paths
        )


@pytest.mark.parametrize("service", EXTRA + REMAINING)
def test_extended_services_present(service: str) -> None:
    packs = load_series_pack("dalmatian")
    assert service in packs
    assert packs[service].operation_count() >= 3


def test_coverage_doc_matches_manifest() -> None:
    man = json.loads((contracts_root() / "dalmatian" / "manifest.json").read_text())
    doc = Path(__file__).resolve().parents[3] / "docs" / "api_coverage.md"
    if not doc.is_file():
        pytest.skip("docs/api_coverage.md not generated yet")
    text = doc.read_text()
    assert str(man["operation_count"]) in text
    assert "nova" in text
