"""Compare simulator packs with published OpenStack 2024.2 API surface expectations."""

from __future__ import annotations

import json
from pathlib import Path

from app.openstack.contract_loader import contracts_root, load_series_pack

# Services listed on https://docs.openstack.org/2024.2/api/index.html
DALMATIAN_API_INDEX_SERVICES = {
    "ironic",
    "cinder",
    "nova",
    "magnum",
    "zun",
    "trove",
    "designate",
    "keystone",
    "glance",
    "watcher",
    "masakari",
    "barbican",
    "octavia",
    "zaqar",
    "neutron",
    "tacker",
    "swift",
    "heat",
    "placement",
    "cloudkitty",
    "blazar",
    "manila",
}


def test_dalmatian_covers_official_2024_2_api_index_services() -> None:
    packs = load_series_pack("dalmatian")
    missing = sorted(DALMATIAN_API_INDEX_SERVICES - set(packs))
    assert missing == [], f"missing official 2024.2 API index services: {missing}"


def test_dalmatian_surface_beats_prior_baseline() -> None:
    """Baseline before watcher/zaqar + neutron/nova expansion was 1144 / 26."""

    man = json.loads((contracts_root() / "dalmatian" / "manifest.json").read_text())
    assert man["service_count"] >= 28
    assert man["operation_count"] >= 1300


def test_neutron_and_nova_closer_to_api_ref_counts() -> None:
    """Public Neutron API-ref lists ~315 unique method+path pairs; Nova ~200+.

    Packs are surface-complete CRUD expansions (not every microversion quirk),
    so we assert meaningful floors rather than bit-identical counts.
    """

    packs = load_series_pack("dalmatian")
    assert packs["neutron"].operation_count() >= 280
    assert packs["nova"].operation_count() >= 120
    neutron_paths = {op.path for op in packs["neutron"].operations}
    assert "/v2.0/address-groups" in neutron_paths
    assert "/v2.0/bgp-speakers" in neutron_paths
    assert "/v2.0/segments" in neutron_paths


def test_coverage_doc_lists_new_services() -> None:
    doc = Path(__file__).resolve().parents[2] / "docs" / "api_coverage.md"
    man = json.loads((contracts_root() / "dalmatian" / "manifest.json").read_text())
    text = doc.read_text()
    assert "watcher" in text
    assert "zaqar" in text
    assert str(man["operation_count"]) in text
