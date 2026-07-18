"""Request-body schema store and coverage tests."""

from __future__ import annotations

from app.openstack.contract_loader import load_series_pack
from app.openstack.request_bodies import clear_request_body_cache, missing_write_schemas
from app.openstack.request_examples import (
    body_fields_from_example,
    flatten_schema_fields,
    schema_example,
    unflatten_body,
)
from app.openstack.singular import singular
from app.web.openstack_catalog import openstack_method_payload


def test_singular_status_not_statu() -> None:
    assert singular("status") == "status"
    assert singular("statuses") == "status"
    assert singular("networks") == "network"
    assert singular("addresses") == "address"


def test_all_series_write_ops_have_request_schemas() -> None:
    clear_request_body_cache()
    for series in ("yoga", "antelope", "caracal", "dalmatian"):
        packs = load_series_pack(series)
        missing = missing_write_schemas(packs)
        assert missing == [], f"{series} missing schemas: {missing[:10]}"


def test_vim_create_catalog_has_api_ref_fields() -> None:
    clear_request_body_cache()
    payload = openstack_method_payload(
        major=9,
        path="/v1.0/vims",
        verb="POST",
        runtime_version="openstack-dalmatian",
    )
    names = {field["name"] for field in payload["body_fields"]}
    assert "vim.type" in names
    assert "vim.auth_url" in names
    assert "vim.auth_cred.username" in names
    assert "vim.vim_project.name" in names
    example = payload["body_example"]
    assert example["vim"]["type"] == "openstack"
    assert "auth_cred" in example["vim"]
    assert example["vim"]["name"] == "example"


def test_status_create_uses_status_envelope() -> None:
    clear_request_body_cache()
    payload = openstack_method_payload(
        major=9,
        path="/v1/status",
        verb="POST",
        runtime_version="openstack-dalmatian",
    )
    assert "status" in payload["body_example"]
    assert "statu" not in payload["body_example"]
    names = {field["name"] for field in payload["body_fields"]}
    assert "status.service" in names or "status.status" in names


def test_server_create_expands_nested_network_fields() -> None:
    clear_request_body_cache()
    payload = openstack_method_payload(
        major=9,
        path="/v2.1/servers",
        verb="POST",
        runtime_version="openstack-dalmatian",
    )
    example = payload["body_example"]
    assert "server" in example
    assert "flavorRef" in example["server"]
    names = {field["name"] for field in payload["body_fields"]}
    assert "server.flavorRef" in names
    # Nested array object leaves from body_example (not a single JSON blob).
    assert "server.networks.0.uuid" in names or "server.networks" in names


def test_body_fields_from_example_walks_nested_leaves() -> None:
    fields = body_fields_from_example(
        {
            "vim": {
                "name": "example",
                "auth_cred": {"username": "admin", "password": "secret"},
                "tags": ["a", "b"],
            }
        }
    )
    names = {f["name"] for f in fields}
    assert "vim.name" in names
    assert "vim.auth_cred.username" in names
    assert "vim.auth_cred.password" in names
    assert "vim.tags.0" in names
    assert "vim.tags.1" in names


def test_flatten_and_unflatten_roundtrip() -> None:
    schema = {
        "type": "object",
        "required": ["vim"],
        "properties": {
            "vim": {
                "type": "object",
                "required": ["name", "type"],
                "properties": {
                    "name": {"type": "string", "example": "example"},
                    "type": {"type": "string", "example": "openstack"},
                    "auth_cred": {
                        "type": "object",
                        "properties": {
                            "username": {"type": "string", "example": "admin"},
                        },
                    },
                },
            }
        },
    }
    fields = flatten_schema_fields(schema)
    names = [f["name"] for f in fields]
    assert "vim.name" in names
    assert "vim.auth_cred.username" in names
    example = schema_example(schema)
    assert example["vim"]["name"] == "example"
    nested = unflatten_body(
        {
            "vim.name": "example",
            "vim.type": "openstack",
            "vim.auth_cred.username": "admin",
        }
    )
    assert nested == {
        "vim": {"name": "example", "type": "openstack", "auth_cred": {"username": "admin"}}
    }
