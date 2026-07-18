"""Seed discovery / catalog / schema documents into ``os_api_objects``."""

from __future__ import annotations

from typing import Any

from asyncpg import Connection

from app.openstack.db_docs import upsert_doc
from app.openstack.surface import SERVICES


def _version_doc(service: str, payload: dict[str, Any]) -> tuple[str, str, str, dict[str, Any]]:
    return service, "discovery_version", "default", payload


async def seed_discovery_documents(conn: Connection) -> dict[str, int]:
    """Persist API discovery documents so handlers never hardcode them."""

    docs: list[tuple[str, str, str, dict[str, Any]]] = [
        _version_doc(
            "keystone",
            {
                "versions": {
                    "values": [
                        {
                            "id": "v3.14",
                            "status": "stable",
                            "updated": "2024-07-01T00:00:00Z",
                            "links": [{"rel": "self", "href": "/v3/"}],
                            "media-types": [
                                {
                                    "base": "application/json",
                                    "type": "application/vnd.openstack.identity-v3+json",
                                }
                            ],
                        }
                    ]
                }
            },
        ),
        _version_doc(
            "nova",
            {
                "versions": [
                    {
                        "id": "v2.1",
                        "status": "CURRENT",
                        "version": "2.96",
                        "min_version": "2.1",
                        "links": [{"rel": "self", "href": "/v2.1/"}],
                    }
                ]
            },
        ),
        _version_doc(
            "neutron",
            {
                "versions": [
                    {
                        "id": "v2.0",
                        "status": "CURRENT",
                        "links": [{"rel": "self", "href": "/v2.0/"}],
                    }
                ]
            },
        ),
        _version_doc(
            "glance",
            {
                "versions": [
                    {"id": "v2.9", "status": "CURRENT", "links": [{"rel": "self", "href": "/v2/"}]}
                ]
            },
        ),
        _version_doc(
            "cinder",
            {
                "versions": [
                    {
                        "id": "v3.0",
                        "status": "CURRENT",
                        "version": "3.70",
                        "min_version": "3.0",
                        "links": [{"rel": "self", "href": "/v3/"}],
                    }
                ]
            },
        ),
        _version_doc(
            "placement",
            {
                "versions": [
                    {
                        "id": "v1.0",
                        "status": "CURRENT",
                        "min_version": "1.0",
                        "max_version": "1.39",
                        "links": [{"rel": "self", "href": "/"}],
                    }
                ]
            },
        ),
        _version_doc("swift", {"swift": {"version": "2.30.0"}}),
        _version_doc(
            "ironic",
            {
                "id": "v1",
                "version": {
                    "id": "1.90",
                    "status": "CURRENT",
                    "min_version": "1.1",
                    "version": "1.90",
                },
            },
        ),
        _version_doc(
            "octavia",
            {
                "versions": [
                    {"id": "v2.0", "status": "CURRENT", "links": [{"href": "/v2/", "rel": "self"}]}
                ]
            },
        ),
        _version_doc(
            "heat",
            {
                "versions": [
                    {"id": "v1.0", "status": "CURRENT", "links": [{"rel": "self", "href": "/v1/"}]}
                ]
            },
        ),
        (
            "swift",
            "info",
            "default",
            {
                "swift": {"version": "2.30.0", "max_file_size": 5368709122},
                "tempauth": {"user_groups": ["admin"]},
            },
        ),
        (
            "glance",
            "info_stores",
            "default",
            {
                "stores": [
                    {
                        "id": "fast",
                        "type": "file",
                        "description": "Local file store",
                        "default": True,
                    },
                    {"id": "cheap", "type": "file", "description": "Secondary file store"},
                ]
            },
        ),
        (
            "glance",
            "info_import",
            "default",
            {
                "import-methods": {
                    "type": "array",
                    "description": "Import methods available.",
                    "items": {"type": "string"},
                    "value": ["glance-direct", "web-download", "copy-image"],
                }
            },
        ),
        (
            "glance",
            "schema",
            "image",
            {
                "name": "image",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "status": {"type": "string"},
                    "visibility": {"type": "string"},
                    "disk_format": {"type": "string"},
                    "container_format": {"type": "string"},
                },
                "additionalProperties": True,
            },
        ),
        (
            "glance",
            "schema",
            "images",
            {
                "name": "images",
                "properties": {
                    "images": {"type": "array", "items": {"type": "object"}},
                    "first": {"type": "string"},
                    "next": {"type": "string"},
                    "schema": {"type": "string"},
                },
            },
        ),
        (
            "heat",
            "resource_type_list",
            "default",
            {
                "resource_types": [
                    "OS::Nova::Server",
                    "OS::Neutron::Net",
                    "OS::Neutron::Subnet",
                    "OS::Neutron::Port",
                    "OS::Cinder::Volume",
                    "OS::Glance::Image",
                    "OS::Heat::Stack",
                ]
            },
        ),
        (
            "zaqar",
            "ping",
            "default",
            {"ping": "pong"},
        ),
        (
            "zaqar",
            "health",
            "default",
            {"catalog": True, "storage": True, "operation_status": "UP"},
        ),
        (
            "cinder",
            "limits",
            "default",
            {
                "limits": {
                    "rate": [],
                    "absolute": {
                        "maxTotalVolumeGigabytes": 100000,
                        "maxTotalVolumes": 500,
                        "totalVolumesUsed": 0,
                        "totalGigabytesUsed": 0,
                    },
                }
            },
        ),
        (
            "keystone",
            "limits",
            "default",
            {
                "limits": [
                    {
                        "resource_name": "project",
                        "resource_limit": 100,
                        "region_id": None,
                    }
                ]
            },
        ),
        (
            "nova",
            "limits",
            "default",
            {
                "limits": {
                    "rate": [],
                    "absolute": {
                        "maxTotalInstances": 100,
                        "maxTotalCores": 200,
                        "maxTotalRAMSize": 512000,
                        "totalInstancesUsed": 0,
                        "totalCoresUsed": 0,
                        "totalRAMUsed": 0,
                    },
                }
            },
        ),
        (
            "nova",
            "console_template",
            "default",
            {
                "type": "novnc",
                "url": "https://127.0.0.1:6080/vnc_auto.html?token=__SERVER_ID__",
            },
        ),
        (
            "nova",
            "console_output_template",
            "default",
            {"output": "Booting...\nSimulator console\n"},
        ),
        (
            "nova",
            "server_metadata_defaults",
            "default",
            {"metadata": {"env": "lab"}},
        ),
        (
            "nova",
            "server_topology_template",
            "default",
            {
                "nodes": [
                    {
                        "vcpu_set": [0],
                        "siblings": [[0]],
                        "host_node": 0,
                        "memory_mb": 1024,
                        "cpu_pinning": {},
                    }
                ],
                "pagesize_kb": 4,
            },
        ),
        (
            "nova",
            "server_password_defaults",
            "default",
            {"password": ""},
        ),
        (
            "nova",
            "server_tag_defaults",
            "default",
            {"tags": ["lab", "env", "demo"]},
        ),
        (
            "nova",
            "keypair_defaults",
            "default",
            {
                "name": "default",
                "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC lab@simulator",
                "type": "ssh",
                "fingerprint_prefix": "https://example.invalid/",
            },
        ),
        (
            "nova",
            "server_group_defaults",
            "default",
            {"name": "group", "policies": ["soft-anti-affinity"]},
        ),
        (
            "placement",
            "allocation_defaults",
            "default",
            {
                "resources": {"VCPU": 1, "MEMORY_MB": 1024, "DISK_GB": 10},
                "consumer_generation": 0,
            },
        ),
        (
            "placement",
            "resource_provider_defaults",
            "default",
            {"generation": 1},
        ),
        (
            "ironic",
            "node_defaults",
            "default",
            {
                "driver": "ipmi",
                "resource_class": "baremetal",
                "properties": {"cpus": 32, "memory_mb": 131072, "local_gb": 1024},
                "power_state": "power on",
                "provision_state": "active",
            },
        ),
        (
            "glance",
            "image_defaults",
            "default",
            {
                "name": "image",
                "visibility": "private",
                "disk_format": "qcow2",
                "container_format": "bare",
            },
        ),
        (
            "cinder",
            "volume_defaults",
            "default",
            {"size": 1, "volume_type": "lvmdriver-1", "name": "volume"},
        ),
        (
            "heat",
            "stack_defaults",
            "default",
            {
                "template": {"heat_template_version": "2015-04-30", "resources": {}},
                "parameters": {},
            },
        ),
        (
            "octavia",
            "loadbalancer_defaults",
            "default",
            {"name": "lb", "vip_address": "10.0.0.50"},
        ),
        (
            "neutron",
            "network_defaults",
            "default",
            {"name": "net"},
        ),
        (
            "neutron",
            "router_defaults",
            "default",
            {"name": "router"},
        ),
        (
            "neutron",
            "security_group_defaults",
            "default",
            {"name": "default"},
        ),
        (
            "neutron",
            "security_group_rule_defaults",
            "default",
            {"direction": "ingress", "ethertype": "IPv4"},
        ),
        (
            "nova",
            "server_defaults",
            "default",
            {"name": "instance"},
        ),
        (
            "nova",
            "volume_attachment_defaults",
            "default",
            {"device": "/dev/vdb"},
        ),
        (
            "nova",
            "quota_set_defaults",
            "default",
            {
                "quota_set": {
                    "instances": 100,
                    "cores": 200,
                    "ram": 512000,
                    "floating_ips": 50,
                    "fixed_ips": -1,
                    "metadata_items": 128,
                    "injected_files": 5,
                    "injected_file_content_bytes": 10240,
                    "security_groups": 50,
                    "security_group_rules": 100,
                    "key_pairs": 100,
                    "server_groups": 10,
                    "server_group_members": 10,
                }
            },
        ),
        (
            "nova",
            "console_auth_token_defaults",
            "default",
            {
                "console_type": "novnc",
                "host": "127.0.0.1",
                "port": 6080,
                "internal_access_path": None,
            },
        ),
    ]

    from app.openstack.surface import catalog_entries

    # Persist catalog with placeholders so Keystone reads catalog only from DB.
    catalog_template = {
        "catalog": catalog_entries("__HOST__", scheme="__SCHEME__"),
    }
    docs.append(("keystone", "service_catalog_template", "default", catalog_template))

    # Generic version docs for remaining SERVICES not listed above.
    seeded_services = {d[0] for d in docs if d[1] == "discovery_version"}
    for spec in SERVICES:
        if spec.name in seeded_services:
            continue
        docs.append(
            _version_doc(
                spec.name,
                {
                    "versions": [
                        {
                            "id": spec.version_path.strip("/") or "v1",
                            "status": "CURRENT",
                            "links": [{"rel": "self", "href": spec.version_path or "/"}],
                            "service": spec.name,
                            "type": spec.typ,
                        }
                    ]
                },
            )
        )

    for service, rtype, name, data in docs:
        await upsert_doc(conn, service=service, resource_type=rtype, name=name, data=data)

    # Ironic drivers as listable rows (also used by /v1/drivers).
    for driver, payload in (
        ("ipmi", {"name": "ipmi", "hosts": ["simulator"], "type": "classic"}),
        ("redfish", {"name": "redfish", "hosts": ["simulator"], "type": "classic"}),
    ):
        await upsert_doc(conn, service="ironic", resource_type="driver", name=driver, data=payload)

    return {"documents": len(docs) + 2}
