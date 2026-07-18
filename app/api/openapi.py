"""OpenAPI tag metadata for the OpenStack simulator.

Legacy Proxmox path→tag helpers remain for optional ``CONTRACT_SNAPSHOT`` mode;
they are not pre-declared in Swagger (see ``openapi_tag_metadata``).
"""

from __future__ import annotations

_NODE_SECTION_LABELS: dict[str, str] = {
    "qemu": "QEMU",
    "lxc": "LXC",
    "ceph": "Ceph",
    "storage": "Storage",
    "sdn": "SDN",
    "firewall": "Firewall",
    "apt": "APT",
    "certificates": "Certificates",
    "scan": "Scan",
    "network": "Network",
    "services": "Services",
    "capabilities": "Capabilities",
    "hardware": "Hardware",
    "replication": "Replication",
    "tasks": "Tasks",
    "subscription": "Subscription",
    "vzdump": "Backup",
    "disks": "Disks",
    "config": "Config",
    "dns": "DNS",
    "hosts": "Hosts",
    "status": "Status",
    "time": "Time",
    "aplinfo": "Appliance",
}

_CLUSTER_SECTION_LABELS: dict[str, str] = {
    "sdn": "SDN",
    "firewall": "Firewall",
    "notifications": "Notifications",
    "ha": "HA",
    "mapping": "Mapping",
    "acme": "ACME",
    "config": "Config",
    "ceph": "Ceph",
    "jobs": "Jobs",
    "metrics": "Metrics",
    "qemu": "QEMU",
    "backup": "Backup",
    "bulk-action": "Bulk Action",
    "replication": "Replication",
    "backup-info": "Backup Info",
    "options": "Options",
    "log": "Log",
    "nextid": "Next ID",
    "resources": "Resources",
    "status": "Status",
    "tasks": "Tasks",
}

# Friendly Swagger tag names for OpenStack service packs.
_SERVICE_TAG_LABELS: dict[str, str] = {
    "keystone": "Keystone",
    "nova": "Nova",
    "neutron": "Neutron",
    "glance": "Glance",
    "cinder": "Cinder",
    "placement": "Placement",
    "heat": "Heat",
    "heat-cfn": "Heat CFN",
    "swift": "Swift",
    "ironic": "Ironic",
    "octavia": "Octavia",
    "barbican": "Barbican",
    "manila": "Manila",
    "designate": "Designate",
    "magnum": "Magnum",
    "zun": "Zun",
    "trove": "Trove",
    "mistral": "Mistral",
    "aodh": "Aodh",
    "freezer": "Freezer",
    "blazar": "Blazar",
    "vitrage": "Vitrage",
    "masakari": "Masakari",
    "tacker": "Tacker",
    "adjutant": "Adjutant",
    "cloudkitty": "CloudKitty",
    "watcher": "Watcher",
    "zaqar": "Zaqar",
}

_SERVICE_TAG_DESCRIPTIONS: dict[str, str] = {
    "OpenStack": "Root discovery and service catalog helpers.",
    "Keystone": "Identity API v3 — auth, projects, users, roles, and domains.",
    "Nova": "Compute API — servers, flavors, keypairs, and related actions.",
    "Neutron": "Networking API — networks, subnets, ports, routers, and security groups.",
    "Glance": "Image API — images and image members.",
    "Cinder": "Block Storage API — volumes, snapshots, and types.",
    "Placement": "Placement API — resource providers and inventories.",
    "Heat": "Orchestration API — stacks and resources.",
    "Heat CFN": "CloudFormation-compatible Heat API.",
    "Swift": "Object Storage API — accounts, containers, and objects.",
    "Ironic": "Bare Metal API — nodes and ports.",
    "Octavia": "Load Balancer API — load balancers, listeners, and pools.",
    "Barbican": "Key Manager API — secrets and containers.",
    "Manila": "Shared File Systems API.",
    "Designate": "DNS-as-a-Service API.",
    "Magnum": "Container Infrastructure Management API.",
    "Zun": "Containers API.",
    "Trove": "Database-as-a-Service API.",
    "Mistral": "Workflow API.",
    "Aodh": "Alarming API.",
    "Freezer": "Backup API.",
    "Blazar": "Reservation API.",
    "Vitrage": "Root Cause Analysis API.",
    "Masakari": "Instance High Availability API.",
    "Tacker": "NFV Orchestration API.",
    "Adjutant": "Admin Automation API.",
    "CloudKitty": "Rating API.",
    "Watcher": "Infrastructure Optimization API.",
    "Zaqar": "Messaging API.",
    "Simulator": "Health checks, catalog UI, and simulator administration.",
}


def service_openapi_tag(service: str) -> str:
    """Swagger tag for an OpenStack service pack (matches specialized router tags)."""

    key = (service or "").strip().lower()
    if key in _SERVICE_TAG_LABELS:
        return _SERVICE_TAG_LABELS[key]
    return key.replace("-", " ").title() or "OpenStack"


def contract_openapi_tag(path: str) -> str:
    """Map a semantic contract path to a category (legacy Proxmox contracts)."""

    parts = [part for part in path.strip("/").split("/") if part]
    if not parts or parts == ["version"]:
        return "Core"
    root = parts[0]
    if root == "access":
        return "Access"
    if root == "nodes":
        if len(parts) >= 3 and parts[1] == "{node}":
            section = parts[2]
            label = _NODE_SECTION_LABELS.get(section, section.replace("-", " ").title())
            return f"Nodes · {label}"
        return "Nodes"
    if root == "cluster":
        if len(parts) >= 2:
            section = parts[1]
            label = _CLUSTER_SECTION_LABELS.get(section, section.replace("-", " ").title())
            return f"Cluster · {label}"
        return "Cluster"
    if root == "storage":
        return "Storage"
    if root == "pools":
        return "Pools"
    return root.replace("-", " ").title()


def contract_openapi_tags(path: str, renderer: str) -> list[str]:
    """Return OpenAPI tags for a legacy Proxmox contract route."""

    renderer_label = "API2 JSON" if renderer == "json" else "API2 ExtJS"
    return [contract_openapi_tag(path), renderer_label]


def openapi_tag_metadata() -> list[dict[str, str]]:
    """Descriptions shown in Swagger UI for each OpenStack tag group."""

    from app.openstack.surface import SERVICES

    descriptions = dict(_SERVICE_TAG_DESCRIPTIONS)
    for spec in SERVICES:
        tag = service_openapi_tag(spec.name)
        descriptions.setdefault(
            tag,
            f"{spec.typ.title()} API ({spec.name}) on port {spec.port}.",
        )
    return [{"name": name, "description": text} for name, text in sorted(descriptions.items())]
