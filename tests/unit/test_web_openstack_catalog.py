"""OpenStack UI catalog payload tests."""

from app.openstack.request_bodies import clear_request_body_cache
from app.web.openstack_catalog import openstack_method_payload


def test_collection_create_body_uses_request_schema() -> None:
    clear_request_body_cache()
    payload = openstack_method_payload(
        major=9,
        path="/v1/status",
        verb="POST",
        runtime_version="openstack-dalmatian",
    )
    assert payload["service"] == "adjutant"
    assert payload["body_fields"]
    assert payload["body_example"]
    # Must not be the old stub-only envelope.
    assert payload["body_example"] != {"statu": {"name": "example"}}
    assert "status" in payload["body_example"]


def test_action_body_example_uses_action_name() -> None:
    clear_request_body_cache()
    payload = openstack_method_payload(
        major=9,
        path="/v2.1/servers/{id}/action",
        verb="POST",
        runtime_version="openstack-dalmatian",
    )
    assert payload["body_fields"]
    assert payload["body_example"]
    # Wildcard server actions default to os-start in the schema catalog.
    assert "os-start" in payload["body_example"]
