"""Path-based OpenStack service dispatch (WebUI on Keystone port)."""

from __future__ import annotations

from app.openstack.dispatch import resolve_service, resolve_service_from_path


def test_path_maps_core_services() -> None:
    assert resolve_service_from_path("/v2.1/servers") == "nova"
    assert resolve_service_from_path("/v2.0/networks") == "neutron"
    assert resolve_service_from_path("/v2/images") == "glance"
    assert resolve_service_from_path("/v3/volumes") == "cinder"
    assert resolve_service_from_path("/v3/auth/tokens") == "keystone"
    assert resolve_service_from_path("/v3/projects") == "keystone"
    assert resolve_service_from_path("/v1/nodes") == "ironic"
    assert resolve_service_from_path("/v2/lbaas/loadbalancers") == "octavia"
    assert resolve_service_from_path("/resource_providers") == "placement"


def test_keystone_port_overrides_to_nova_path() -> None:
    service = resolve_service(
        {"x-openstack-service": "keystone", "x-forwarded-port": "5000"},
        "/v2.1/servers/detail",
    )
    assert service == "nova"


def test_route_service_header_wins() -> None:
    service = resolve_service(
        {
            "x-openstack-service": "keystone",
            "x-openstack-route-service": "cinder",
            "x-forwarded-port": "5000",
        },
        "/v3/limits",
    )
    assert service == "cinder"


def test_auth_path_ignores_stale_route_service() -> None:
    service = resolve_service(
        {
            "x-openstack-service": "keystone",
            "x-openstack-route-service": "cinder",
            "x-forwarded-port": "5000",
        },
        "/v3/auth/tokens",
    )
    assert service == "keystone"


def test_dedicated_nova_port_keeps_nova() -> None:
    service = resolve_service(
        {"x-openstack-service": "nova", "x-forwarded-port": "8774"},
        "/v2.1/servers",
    )
    assert service == "nova"
