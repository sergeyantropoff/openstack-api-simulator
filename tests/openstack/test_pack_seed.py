"""Pack-driven surface seed covers every contract resource_type."""

from __future__ import annotations

from app.openstack.pack_seed import iter_pack_resource_types


def test_iter_pack_resource_types_covers_schema_services() -> None:
    types = iter_pack_resource_types()
    assert len(types) >= 200
    expected = {
        ("barbican", "secret"),
        ("barbican", "container"),
        ("manila", "share"),
        ("manila", "share_type"),
        ("watcher", "goal"),
        ("zun", "host"),
        ("cloudkitty", "dataframes"),
        ("designate", "zone"),
    }
    missing = expected - types
    assert not missing, missing
