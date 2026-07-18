"""OpenAPI tag categorization tests."""

from app.api.openapi import openapi_tag_metadata


def test_openapi_tag_metadata_is_openstack_only() -> None:
    names = [entry["name"] for entry in openapi_tag_metadata()]
    assert names == sorted(names)
    assert "Simulator" in names
    assert "Keystone" in names
    assert "Nova" in names
    assert "API2 JSON" not in names
    assert "API2 ExtJS" not in names
    assert "Core" not in names
    assert "Access" not in names
    assert "Nodes" not in names
    assert "Pools" not in names
    assert not any(name.startswith("Nodes ·") for name in names)
    assert not any(name.startswith("Cluster ·") for name in names)
