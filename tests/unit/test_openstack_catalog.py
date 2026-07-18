"""OpenStack catalog helper tests."""

from app.openstack.catalog import build_catalog, public_base


def test_public_base() -> None:
    assert public_base("localhost", 5000) == "http://localhost:5000"


def test_build_catalog_includes_core_services() -> None:
    catalog = build_catalog("127.0.0.1")
    types = {item["type"] for item in catalog}
    assert {"identity", "compute", "network", "image", "volumev3", "placement"} <= types
    nova = next(item for item in catalog if item["type"] == "compute")
    assert nova["endpoints"][0]["url"].endswith(":8774/v2.1")
