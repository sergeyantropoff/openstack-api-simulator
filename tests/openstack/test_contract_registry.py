"""Per-path OpenStack contract registration (Proxmox-style)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.openstack.contract_loader import ensure_loaded, load_series_pack
from app.openstack.mount import build_openstack_handlers, mount_openstack_routes
from app.openstack.registry import (
    HandlerRegistry,
    normalize_path_template,
    register_specialized_handlers,
)
from app.openstack.routes import nova
from app.openstack.schema_engine import remount_schema_services


def test_normalize_path_template_collapses_param_names() -> None:
    assert normalize_path_template("/v2.1/servers/{id}") == normalize_path_template(
        "/v2.1/servers/{server_id}"
    )
    assert normalize_path_template("/v1/{account}/{container}/{object}") == normalize_path_template(
        "/v1/{account}/{container}/{object_name:path}"
    )


def test_swift_object_handler_resolves_from_contract_path() -> None:
    registry = build_openstack_handlers()
    assert registry.get("swift", "/v1/{account}/{container}/{object}", "GET") is not None
    assert registry.get("swift", "/v1/{account}/{container}/{object}", "PUT") is not None


def test_handler_registry_structural_lookup() -> None:
    registry = HandlerRegistry()

    async def handler(request):  # noqa: ANN001
        return request

    registry.register("nova", "/v2.1/servers/{server_id}", "GET", handler)
    found = registry.get("nova", "/v2.1/servers/{id}", "GET")
    assert found is handler


def test_specialized_handlers_imported_from_nova_router() -> None:
    registry = HandlerRegistry()
    count = register_specialized_handlers(registry, "nova", nova.router)
    assert count > 0
    assert registry.get("nova", "/v2.1/servers", "GET") is not None
    assert registry.get("nova", "/v2.1/servers/{id}", "GET") is not None


def test_mount_registers_one_route_per_unique_method_path() -> None:
    app = FastAPI()
    mount_openstack_routes(app, series="dalmatian")

    packs = load_series_pack("dalmatian")
    expected = 0
    for pack in packs.values():
        expected += len({(op.method, op.path) for op in pack.operations})

    contract_routes = [
        route
        for route in app.router.routes
        if isinstance(route, APIRoute)
        and isinstance(route.name, str)
        and route.name.startswith("os-contract:")
    ]
    # Contract paths plus specialized-only aliases (trailing slash, PUT tags, …).
    assert len(contract_routes) >= expected
    assert app.state.openstack_schema_ops == len(contract_routes)
    # name format: os-contract:{service}:{METHOD}:{path}
    mounted_ops = set()
    for route in contract_routes:
        rest = route.name[len("os-contract:") :]
        _service, _, remainder = rest.partition(":")
        method, _, path = remainder.partition(":")
        mounted_ops.add((method, path))
    for pack in packs.values():
        for op in pack.operations:
            assert (op.method, op.path) in mounted_ops
    # No legacy schema-* route names.
    assert not any(
        isinstance(getattr(r, "name", None), str) and str(r.name).startswith("schema-")
        for r in app.router.routes
    )


def test_remount_preserves_handlers_and_route_count() -> None:
    app = FastAPI()
    mount_openstack_routes(app, series="dalmatian")
    handlers = app.state.openstack_handlers
    assert isinstance(handlers, HandlerRegistry)
    before = app.state.openstack_schema_ops

    ensure_loaded("caracal")
    summary = remount_schema_services(app, "caracal")
    assert app.state.openstack_handlers is handlers
    assert summary["routes_mounted"] == app.state.openstack_schema_ops
    assert app.state.openstack_schema_ops > 0
    # Switching series rebuilds routes; count may differ by series deltas.
    assert isinstance(before, int)


def test_build_openstack_handlers_covers_core_services() -> None:
    registry = build_openstack_handlers()
    for service in ("keystone", "nova", "neutron", "glance", "cinder"):
        keys = [k for k in registry.keys() if k[0] == service]
        assert keys, f"expected handlers for {service}"
