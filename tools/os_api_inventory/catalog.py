"""Canonical OpenStack service metadata + API-ref-style resource expansions.

Used by generate_packs.py to emit contracts/openstack/<series> packs.
Paths follow OpenStack API-ref conventions (Dalmatian baseline).
"""

from __future__ import annotations

from typing import Any

# name, type, port, version_path, default_mv, max_mv
SERVICES_META: list[tuple[str, str, int, str, str | None, str | None]] = [
    ("keystone", "identity", 5000, "/v3/", None, None),
    ("nova", "compute", 8774, "/v2.1/", "2.1", "2.96"),
    ("neutron", "network", 9696, "/v2.0/", None, None),
    ("glance", "image", 9292, "/v2/", None, None),
    ("cinder", "volumev3", 8776, "/v3/", "3.0", "3.70"),
    ("placement", "placement", 8003, "/", "1.0", "1.39"),
    ("heat", "orchestration", 8004, "/v1/", None, None),
    ("heat-cfn", "cloudformation", 8000, "/v1/", None, None),
    ("swift", "object-store", 8080, "/v1/", None, None),
    ("ironic", "baremetal", 6385, "/", "1.1", "1.90"),
    ("octavia", "load-balancer", 9876, "/v2/", None, None),
    ("barbican", "key-manager", 9311, "/v1/", None, None),
    ("manila", "sharev2", 8786, "/v2/", "2.0", "2.82"),
    ("designate", "dns", 9001, "/v2/", None, None),
    ("magnum", "container-infra", 9511, "/v1/", None, None),
    ("zun", "container", 9517, "/v1/", None, None),
    ("trove", "database", 8779, "/v1.0/", None, None),
    ("mistral", "workflowv2", 8989, "/v2/", None, None),
    ("aodh", "alarming", 8042, "/v2/", None, None),
    ("cloudkitty", "rating", 8889, "/v1/", None, None),
    ("freezer", "backup", 9090, "/v2/", None, None),
    ("blazar", "reservation", 1234, "/v1/", None, None),
    ("vitrage", "rca", 8999, "/", None, None),
    ("masakari", "instance-ha", 15868, "/v1/", None, None),
    ("tacker", "nfv-orchestration", 9890, "/", None, None),
    ("adjutant", "admin-logic", 5050, "/", None, None),
    # Present on docs.openstack.org/2024.2/api (Dalmatian) index.
    ("watcher", "infra-optim", 9322, "/v1/", None, None),
    ("zaqar", "messaging", 8888, "/v2/", None, None),
]

SERIES: list[tuple[str, int]] = [
    ("yoga", 6),
    ("antelope", 7),
    ("caracal", 8),
    ("dalmatian", 9),
]


def _crud(
    resource: str,
    path: str,
    key: str,
    *,
    detail: bool = True,
    actions: list[str] | None = None,
    nested: list[tuple[str, str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Expand a resource into list/detail/create/show/update/delete + actions/nested."""

    from app.openstack.singular import singular as _singularize

    singular = _singularize(key)
    ops: list[dict[str, Any]] = [
        {
            "operation_id": f"{resource}_list",
            "method": "GET",
            "path": path,
            "resource_type": resource,
            "collection_key": key,
            "kind": "collection",
            "status_code": 200,
        },
        {
            "operation_id": f"{resource}_create",
            "method": "POST",
            "path": path,
            "resource_type": resource,
            "collection_key": key,
            "item_key": singular,
            "kind": "collection",
            "status_code": 201,
            "create_status": 201,
        },
        {
            "operation_id": f"{resource}_show",
            "method": "GET",
            "path": f"{path}/{{id}}",
            "resource_type": resource,
            "collection_key": key,
            "item_key": singular,
            "kind": "item",
            "status_code": 200,
        },
        {
            "operation_id": f"{resource}_update",
            "method": "PUT",
            "path": f"{path}/{{id}}",
            "resource_type": resource,
            "collection_key": key,
            "item_key": singular,
            "kind": "item",
            "status_code": 200,
        },
        {
            "operation_id": f"{resource}_patch",
            "method": "PATCH",
            "path": f"{path}/{{id}}",
            "resource_type": resource,
            "collection_key": key,
            "item_key": singular,
            "kind": "item",
            "status_code": 200,
        },
        {
            "operation_id": f"{resource}_delete",
            "method": "DELETE",
            "path": f"{path}/{{id}}",
            "resource_type": resource,
            "collection_key": key,
            "kind": "item",
            "status_code": 204,
        },
    ]
    if detail:
        ops.append(
            {
                "operation_id": f"{resource}_list_detail",
                "method": "GET",
                "path": f"{path}/detail",
                "resource_type": resource,
                "collection_key": key,
                "kind": "detail",
                "status_code": 200,
            }
        )
    for action in actions or []:
        ops.append(
            {
                "operation_id": f"{resource}_action_{action.replace('-', '_')}",
                "method": "POST",
                "path": f"{path}/{{id}}/action",
                "resource_type": resource,
                "collection_key": key,
                "item_key": singular,
                "kind": "action",
                "action_name": action,
                "status_code": 202,
            }
        )
    # Prefer a single shared action endpoint once; expand only unique action names
    # are stored as metadata — runtime uses one POST .../action route.
    for nested_type, nested_path, nested_key in nested or []:
        ops.extend(_crud(nested_type, nested_path, nested_key, detail=False, actions=None))
    return ops


def _get(
    path: str, op_id: str, resource: str, key: str | None = None, **extra: Any
) -> dict[str, Any]:
    return {
        "operation_id": op_id,
        "method": "GET",
        "path": path,
        "resource_type": resource,
        "collection_key": key,
        "kind": "custom",
        "status_code": 200,
        **extra,
    }


def _post(
    path: str, op_id: str, resource: str, key: str | None = None, status: int = 201, **extra: Any
) -> dict[str, Any]:
    return {
        "operation_id": op_id,
        "method": "POST",
        "path": path,
        "resource_type": resource,
        "collection_key": key,
        "kind": "custom",
        "status_code": status,
        **extra,
    }


def keystone_ops() -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = [
        _get("/v3", "keystone_v3_root", "version", requires_project=False),
        _post(
            "/v3/auth/tokens",
            "keystone_auth_tokens",
            "token",
            status=201,
            requires_auth=False,
            requires_project=False,
        ),
        _get("/v3/auth/tokens", "keystone_validate_token", "token", requires_project=False),
        _get("/v3/auth/catalog", "keystone_catalog", "catalog", requires_project=False),
    ]
    for res, path, key in [
        ("domain", "/v3/domains", "domains"),
        ("project", "/v3/projects", "projects"),
        ("user", "/v3/users", "users"),
        ("group", "/v3/groups", "groups"),
        ("role", "/v3/roles", "roles"),
        ("region", "/v3/regions", "regions"),
        ("service", "/v3/services", "services"),
        ("endpoint", "/v3/endpoints", "endpoints"),
        ("credential", "/v3/credentials", "credentials"),
        ("policy", "/v3/policies", "policies"),
    ]:
        ops.extend(_crud(res, path, key, detail=False))
    ops.extend(
        _crud(
            "application_credential",
            "/v3/users/{user_id}/application_credentials",
            "application_credentials",
            detail=False,
        )
    )
    ops.extend(
        [
            _get(
                "/v3/role_assignments",
                "keystone_role_assignments",
                "role_assignment",
                "role_assignments",
            ),
            _put(
                "/v3/projects/{project_id}/users/{user_id}/roles/{role_id}",
                "keystone_grant_project_role",
                "role_assignment",
            ),
            _delete_op(
                "/v3/projects/{project_id}/users/{user_id}/roles/{role_id}",
                "keystone_revoke_project_role",
                "role_assignment",
            ),
            _get(
                "/v3/projects/{project_id}/users/{user_id}/roles",
                "keystone_list_project_user_roles",
                "role",
                "roles",
            ),
            _get(
                "/v3/OS-INHERIT/domains/{domain_id}/users/{user_id}/roles",
                "keystone_inherit_roles",
                "role",
                "roles",
            ),
            _get("/v3/limits", "keystone_limits", "limit", "limits"),
            _get(
                "/v3/registered_limits",
                "keystone_registered_limits",
                "registered_limit",
                "registered_limits",
            ),
        ]
    )
    return ops


def _put(path: str, op_id: str, resource: str, key: str | None = None) -> dict[str, Any]:
    return {
        "operation_id": op_id,
        "method": "PUT",
        "path": path,
        "resource_type": resource,
        "collection_key": key,
        "kind": "custom",
        "status_code": 204,
    }


def _delete_op(path: str, op_id: str, resource: str) -> dict[str, Any]:
    return {
        "operation_id": op_id,
        "method": "DELETE",
        "path": path,
        "resource_type": resource,
        "kind": "custom",
        "status_code": 204,
    }


def nova_ops() -> list[dict[str, Any]]:
    server_actions = [
        "os-start",
        "os-stop",
        "reboot",
        "rebuild",
        "resize",
        "confirmResize",
        "revertResize",
        "pause",
        "unpause",
        "suspend",
        "resume",
        "shelve",
        "shelveOffload",
        "unshelve",
        "lock",
        "unlock",
        "rescue",
        "unrescue",
        "createImage",
        "createBackup",
        "addFloatingIp",
        "removeFloatingIp",
        "addSecurityGroup",
        "removeSecurityGroup",
        "changePassword",
        "evacuate",
        "migrate",
        "liveMigrate",
        "resetState",
        "os-getConsoleOutput",
        "os-getVNCConsole",
        "remote-consoles",
        "trigger_crash_dump",
    ]
    ops = _crud(
        "server",
        "/v2.1/servers",
        "servers",
        actions=server_actions,
        nested=[
            (
                "volume_attachment",
                "/v2.1/servers/{server_id}/os-volume_attachments",
                "volumeAttachments",
            ),
            (
                "interface_attachment",
                "/v2.1/servers/{server_id}/os-interface",
                "interfaceAttachments",
            ),
            ("instance_action", "/v2.1/servers/{server_id}/os-instance-actions", "instanceActions"),
            ("server_metadata", "/v2.1/servers/{server_id}/metadata", "metadata"),
            ("server_tag", "/v2.1/servers/{server_id}/tags", "tags"),
            (
                "server_security_group",
                "/v2.1/servers/{server_id}/os-security-groups",
                "security_groups",
            ),
        ],
    )
    # Deduplicate action endpoints to a single POST route (schema engine handles body key)
    ops = [o for o in ops if o.get("kind") != "action"]
    ops.append(
        {
            "operation_id": "server_action",
            "method": "POST",
            "path": "/v2.1/servers/{id}/action",
            "resource_type": "server",
            "collection_key": "servers",
            "kind": "action",
            "status_code": 202,
            "action_name": "*",
        }
    )
    ops.extend(_crud("flavor", "/v2.1/flavors", "flavors"))
    ops.extend(_crud("keypair", "/v2.1/os-keypairs", "keypairs", detail=False))
    # keypairs use name as id
    ops.extend(_crud("aggregate", "/v2.1/os-aggregates", "aggregates", detail=False))
    ops.extend(_crud("server_group", "/v2.1/os-server-groups", "server_groups", detail=False))
    ops.extend(
        [
            _get("/v2.1", "nova_versions", "version", requires_project=False),
            _get("/v2.1/os-hypervisors", "hypervisor_list", "hypervisor", "hypervisors"),
            _get("/v2.1/os-hypervisors/detail", "hypervisor_detail", "hypervisor", "hypervisors"),
            _get("/v2.1/os-hypervisors/{id}", "hypervisor_show", "hypervisor", "hypervisors"),
            _get(
                "/v2.1/os-availability-zone", "az_list", "availability_zone", "availabilityZoneInfo"
            ),
            _get(
                "/v2.1/os-availability-zone/detail",
                "az_detail",
                "availability_zone",
                "availabilityZoneInfo",
            ),
            _get("/v2.1/os-services", "compute_services", "service", "services"),
            _get("/v2.1/limits", "compute_limits", "limit", "limits"),
            _get("/v2.1/os-quota-sets/{id}", "quota_set_show", "quota_set", "quota_set"),
            _put("/v2.1/os-quota-sets/{id}", "quota_set_update", "quota_set", "quota_set"),
            _get("/v2.1/os-quota-sets/{id}/detail", "quota_set_detail", "quota_set", "quota_set"),
            _get("/v2.1/os-migrations", "migrations_list", "migration", "migrations"),
            _get("/v2.1/os-networks", "nova_networks", "network", "networks"),
            _get("/v2.1/os-tenant-networks", "nova_tenant_networks", "network", "networks"),
            _get(
                "/v2.1/os-security-groups",
                "nova_security_groups",
                "security_group",
                "security_groups",
            ),
            _get("/v2.1/os-floating-ips", "nova_floating_ips", "floating_ip", "floating_ips"),
            _get(
                "/v2.1/os-instance_usage_audit_log",
                "instance_usage_audit",
                "instance_usage_audit_log",
                "instance_usage_audit_logs",
            ),
            _get(
                "/v2.1/os-assisted-volume-snapshots",
                "assisted_volume_snapshots",
                "assisted_volume_snapshot",
                "snapshots",
            ),
            _post(
                "/v2.1/os-server-external-events",
                "server_external_events",
                "server_external_event",
                "events",
                status=200,
            ),
            _get("/v2.1/servers/{server_id}/diagnostics", "server_diagnostics", "server"),
            _get(
                "/v2.1/servers/{server_id}/os-instance-actions/{request_id}",
                "instance_action_show",
                "instance_action",
                "instanceAction",
            ),
            _post(
                "/v2.1/servers/{server_id}/remote-consoles",
                "remote_console_create",
                "remote_console",
                "remote_console",
                status=200,
            ),
            _get(
                "/v2.1/flavors/{id}/os-extra_specs",
                "flavor_extra_specs",
                "flavor_extra_spec",
                "extra_specs",
            ),
            _get("/v2.1/os-simple-tenant-usage", "simple_tenant_usage", "usage", "tenant_usages"),
            _get("/v2.1/os-hosts", "os_hosts", "host", "hosts"),
            # Additional Compute API-ref surface (Dalmatian).
            _get("/v2.1/extensions", "nova_extensions", "extension", "extensions"),
            _get("/v2.1/extensions/{id}", "nova_extension_show", "extension"),
            *_crud("agent", "/v2.1/os-agents", "agents", detail=False),
            *_crud(
                "flavor_extra_spec",
                "/v2.1/flavors/{flavor_id}/os-extra_specs",
                "extra_specs",
                detail=False,
            ),
            *_crud(
                "server_migration",
                "/v2.1/servers/{server_id}/migrations",
                "migrations",
                detail=False,
            ),
            *_crud("console", "/v2.1/servers/{server_id}/consoles", "consoles", detail=False),
            _get(
                "/v2.1/os-console-auth-tokens/{id}", "console_auth_token_show", "console_auth_token"
            ),
            _get("/v2.1/servers/{server_id}/topology", "server_topology", "server"),
            _get("/v2.1/servers/{server_id}/os-server-password", "server_password_show", "server"),
            _delete_op(
                "/v2.1/servers/{server_id}/os-server-password", "server_password_clear", "server"
            ),
            _get("/v2.1/os-server-groups/{id}", "server_group_show", "server_group"),
        ]
    )
    return ops


def neutron_ops() -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = [
        _get("/v2.0", "neutron_versions", "version", requires_project=False)
    ]
    for res, path, key in [
        ("network", "/v2.0/networks", "networks"),
        ("subnet", "/v2.0/subnets", "subnets"),
        ("port", "/v2.0/ports", "ports"),
        ("router", "/v2.0/routers", "routers"),
        ("floatingip", "/v2.0/floatingips", "floatingips"),
        ("security_group", "/v2.0/security-groups", "security_groups"),
        ("security_group_rule", "/v2.0/security-group-rules", "security_group_rules"),
        ("address_scope", "/v2.0/address-scopes", "address_scopes"),
        ("address_group", "/v2.0/address-groups", "address_groups"),
        ("subnetpool", "/v2.0/subnetpools", "subnetpools"),
        ("qos_policy", "/v2.0/qos/policies", "policies"),
        ("trunk", "/v2.0/trunks", "trunks"),
        ("rbac_policy", "/v2.0/rbac-policies", "rbac_policies"),
        ("metering_label", "/v2.0/metering/metering-labels", "metering_labels"),
        ("metering_label_rule", "/v2.0/metering/metering-label-rules", "metering_label_rules"),
        ("firewall_group", "/v2.0/fwaas/firewall_groups", "firewall_groups"),
        ("firewall_policy", "/v2.0/fwaas/firewall_policies", "firewall_policies"),
        ("firewall_rule", "/v2.0/fwaas/firewall_rules", "firewall_rules"),
        ("vpn_service", "/v2.0/vpn/vpnservices", "vpnservices"),
        ("ipsec_site_connection", "/v2.0/vpn/ipsec-site-connections", "ipsec_site_connections"),
        ("ike_policy", "/v2.0/vpn/ikepolicies", "ikepolicies"),
        ("ipsec_policy", "/v2.0/vpn/ipsecpolicies", "ipsecpolicies"),
        ("vpn_endpoint_group", "/v2.0/vpn/endpoint-groups", "endpoint_groups"),
        ("bgpvpn", "/v2.0/bgpvpn/bgpvpns", "bgpvpns"),
        ("bgp_speaker", "/v2.0/bgp-speakers", "bgp_speakers"),
        ("bgp_peer", "/v2.0/bgp-peers", "bgp_peers"),
        ("log", "/v2.0/log/logs", "logs"),
        ("ndp_proxy", "/v2.0/ndp_proxies", "ndp_proxies"),
        ("local_ip", "/v2.0/local_ips", "local_ips"),
        ("segment", "/v2.0/segments", "segments"),
        ("network_segment_range", "/v2.0/network_segment_ranges", "network_segment_ranges"),
        ("service_profile", "/v2.0/service_profiles", "service_profiles"),
        ("neutron_flavor", "/v2.0/flavors", "flavors"),
        (
            "default_security_group_rule",
            "/v2.0/default-security-group-rules",
            "default_security_group_rules",
        ),
        ("lbaas_loadbalancer", "/v2.0/lbaas/loadbalancers", "loadbalancers"),
        ("lbaas_listener", "/v2.0/lbaas/listeners", "listeners"),
        ("lbaas_pool", "/v2.0/lbaas/pools", "pools"),
    ]:
        ops.extend(_crud(res, path, key, detail=False))
    ops.extend(
        [
            _get("/v2.0/agents", "neutron_agents", "agent", "agents"),
            _get("/v2.0/agents/{id}", "neutron_agent_show", "agent"),
            _get("/v2.0/qos/rule-types", "qos_rule_types", "qos_rule_type", "rule_types"),
            _get(
                "/v2.0/network-ip-availabilities",
                "network_ip_availabilities",
                "network_ip_availability",
                "network_ip_availabilities",
            ),
            _get(
                "/v2.0/auto-allocated-topology",
                "auto_allocated_topology",
                "auto_allocated_topology",
                "auto_allocated_topology",
            ),
            _get("/v2.0/quotas", "neutron_quota_list", "quota", "quotas"),
            _get("/v2.0/quotas/{id}", "neutron_quota_show", "quota"),
            _put("/v2.0/quotas/{id}", "neutron_quota_update", "quota"),
            _delete_op("/v2.0/quotas/{id}", "neutron_quota_delete", "quota"),
            _put("/v2.0/routers/{id}/add_router_interface", "router_add_interface", "router"),
            _put("/v2.0/routers/{id}/remove_router_interface", "router_remove_interface", "router"),
            _put("/v2.0/routers/{id}/add_extraroutes", "router_add_extraroutes", "router"),
            _put("/v2.0/routers/{id}/remove_extraroutes", "router_remove_extraroutes", "router"),
            *_crud(
                "conntrack_helper",
                "/v2.0/routers/{router_id}/conntrack_helpers",
                "conntrack_helpers",
                detail=False,
            ),
            *_crud(
                "qos_bandwidth_limit_rule",
                "/v2.0/qos/policies/{policy_id}/bandwidth_limit_rules",
                "bandwidth_limit_rules",
                detail=False,
            ),
            *_crud(
                "qos_dscp_marking_rule",
                "/v2.0/qos/policies/{policy_id}/dscp_marking_rules",
                "dscp_marking_rules",
                detail=False,
            ),
            *_crud(
                "qos_minimum_bandwidth_rule",
                "/v2.0/qos/policies/{policy_id}/minimum_bandwidth_rules",
                "minimum_bandwidth_rules",
                detail=False,
            ),
            *_crud(
                "trunk_subport", "/v2.0/trunks/{trunk_id}/add_subports", "sub_ports", detail=False
            ),
            *_crud(
                "floatingip_port_forwarding",
                "/v2.0/floatingips/{floatingip_id}/port_forwardings",
                "port_forwardings",
                detail=False,
            ),
            *_crud(
                "local_ip_association",
                "/v2.0/local_ips/{local_ip_id}/port_associations",
                "port_associations",
                detail=False,
            ),
            *_crud(
                "bgpvpn_network_association",
                "/v2.0/bgpvpn/bgpvpns/{bgpvpn_id}/network_associations",
                "network_associations",
                detail=False,
            ),
            *_crud(
                "bgpvpn_router_association",
                "/v2.0/bgpvpn/bgpvpns/{bgpvpn_id}/router_associations",
                "router_associations",
                detail=False,
            ),
        ]
    )
    return ops


def glance_ops() -> list[dict[str, Any]]:
    ops = [_get("/v2", "glance_versions", "version", requires_project=False)]
    ops.extend(_crud("image", "/v2/images", "images", detail=False))
    ops.extend(
        [
            _put("/v2/images/{id}/file", "image_upload", "image"),
            _get("/v2/images/{id}/file", "image_download", "image"),
            *_crud("metadef_namespace", "/v2/metadefs/namespaces", "namespaces", detail=False),
            *_crud("task", "/v2/tasks", "tasks", detail=False),
            _get("/v2/info/import", "glance_import_info", "info_import", "import-methods"),
            _get("/v2/info/stores", "glance_stores", "info_store", "stores"),
            _get("/v2/schemas/image", "glance_schema_image", "schema"),
            _get("/v2/schemas/images", "glance_schema_images", "schema"),
            _post("/v2/images/{id}/actions/deactivate", "image_deactivate", "image", status=204),
            _post("/v2/images/{id}/actions/reactivate", "image_reactivate", "image", status=204),
            *_crud("image_member", "/v2/images/{image_id}/members", "members", detail=False),
            *_crud("image_tag", "/v2/images/{image_id}/tags", "tags", detail=False),
        ]
    )
    return ops


def cinder_ops() -> list[dict[str, Any]]:
    ops = [_get("/v3", "cinder_versions", "version", requires_project=False)]
    for res, path, key in [
        ("volume", "/v3/volumes", "volumes"),
        ("snapshot", "/v3/snapshots", "snapshots"),
        ("backup", "/v3/backups", "backups"),
        ("volume_type", "/v3/types", "volume_types"),
        ("qos_spec", "/v3/qos-specs", "qos_specs"),
        ("group", "/v3/groups", "groups"),
        ("group_snapshot", "/v3/group_snapshots", "group_snapshots"),
        ("consistencygroup", "/v3/consistencygroups", "consistencygroups"),
        ("attachment", "/v3/attachments", "attachments"),
        ("transfer", "/v3/volume-transfers", "transfers"),
        ("message", "/v3/messages", "messages"),
        ("cluster", "/v3/clusters", "clusters"),
    ]:
        ops.extend(_crud(res, path, key))
    # project-scoped aliases
    ops.extend(_crud("volume_tenant", "/v3/{project_id}/volumes", "volumes"))
    ops.extend(
        [
            {
                "operation_id": "volume_action",
                "method": "POST",
                "path": "/v3/volumes/{id}/action",
                "resource_type": "volume",
                "kind": "action",
                "status_code": 202,
                "action_name": "*",
            },
            _get("/v3/os-services", "cinder_services", "service", "services"),
            _get("/v3/limits", "cinder_limits", "limit", "limits"),
            _get("/v3/os-quota-sets/{id}", "cinder_quota_show", "quota_set", "quota_set"),
            _get(
                "/v3/resource_filters",
                "cinder_resource_filters",
                "resource_filter",
                "resource_filters",
            ),
            _get("/v3/scheduler-stats/get_pools", "cinder_pools", "pool", "pools"),
        ]
    )
    return ops


def placement_ops() -> list[dict[str, Any]]:
    ops = [
        _get("/", "placement_root", "version", requires_project=False),
    ]
    for res, path, key in [
        ("resource_provider", "/resource_providers", "resource_providers"),
        ("resource_class", "/resource_classes", "resource_classes"),
        ("trait", "/traits", "traits"),
    ]:
        ops.extend(_crud(res, path, key, detail=False))
    ops.extend(
        [
            _get("/allocations/{consumer_uuid}", "allocation_show", "allocation", "allocations"),
            _put("/allocations/{consumer_uuid}", "allocation_set", "allocation"),
            _delete_op("/allocations/{consumer_uuid}", "allocation_delete", "allocation"),
            _get(
                "/allocation_candidates",
                "allocation_candidates",
                "allocation_candidate",
                "allocation_requests",
            ),
            _get("/usages", "usages", "usage", "usages"),
            _get(
                "/resource_providers/{id}/inventories", "rp_inventories", "inventory", "inventories"
            ),
            _put("/resource_providers/{id}/inventories", "rp_inventories_set", "inventory"),
            _get("/resource_providers/{id}/aggregates", "rp_aggregates", "aggregate", "aggregates"),
            _get("/resource_providers/{id}/traits", "rp_traits", "trait", "traits"),
            _get("/resource_providers/{id}/usages", "rp_usages", "usage", "usages"),
            _get(
                "/resource_providers/{id}/allocations",
                "rp_allocations",
                "allocation",
                "allocations",
            ),
        ]
    )
    return ops


def heat_ops() -> list[dict[str, Any]]:
    ops = [_get("/v1", "heat_versions", "version", requires_project=False)]
    base = "/v1/{tenant_id}"
    ops.extend(_crud("stack", f"{base}/stacks", "stacks", detail=False))
    ops.extend(
        [
            _get(f"{base}/stacks/detail", "stack_list_detail", "stack", "stacks"),
            _get(
                f"{base}/stacks/{{stack_name}}/{{stack_id}}", "stack_show_by_name", "stack", "stack"
            ),
            _delete_op(
                f"{base}/stacks/{{stack_name}}/{{stack_id}}", "stack_delete_by_name", "stack"
            ),
            *_crud(
                "stack_resource",
                f"{base}/stacks/{{stack_name}}/{{stack_id}}/resources",
                "resources",
                detail=False,
            ),
            *_crud(
                "stack_event",
                f"{base}/stacks/{{stack_name}}/{{stack_id}}/events",
                "events",
                detail=False,
            ),
            *_crud("software_config", f"{base}/software_configs", "software_configs", detail=False),
            *_crud(
                "software_deployment",
                f"{base}/software_deployments",
                "software_deployments",
                detail=False,
            ),
            _get(
                f"{base}/resource_types", "heat_resource_types", "resource_type", "resource_types"
            ),
            _get(f"{base}/services", "heat_services", "service", "services"),
            _post(f"{base}/stacks/preview", "stack_preview", "stack", "stack", status=200),
            _post(f"{base}/validate", "template_validate", "template", status=200),
        ]
    )
    return ops


def heat_cfn_ops() -> list[dict[str, Any]]:
    return [
        *_crud("stack", "/stacks", "Stacks", detail=False),
        _get("/v1", "heat_cfn_versions", "version", requires_project=False),
        _post("/", "heat_cfn_query", "stack", status=200, requires_project=False),
    ]


def swift_ops() -> list[dict[str, Any]]:
    return [
        _get("/info", "swift_info", "info", requires_auth=False, requires_project=False),
        _get("/v1/{account}", "swift_account_get", "account", requires_project=False),
        _post("/v1/{account}", "swift_account_post", "account", status=204),
        _get("/v1/{account}/{container}", "swift_container_get", "container"),
        _put("/v1/{account}/{container}", "swift_container_put", "container"),
        _delete_op("/v1/{account}/{container}", "swift_container_delete", "container"),
        _get("/v1/{account}/{container}/{object}", "swift_object_get", "object"),
        _put("/v1/{account}/{container}/{object}", "swift_object_put", "object"),
        _delete_op("/v1/{account}/{container}/{object}", "swift_object_delete", "object"),
        _post("/v1/{account}/{container}/{object}", "swift_object_post", "object", status=202),
    ]


def ironic_ops() -> list[dict[str, Any]]:
    ops = [_get("/v1", "ironic_versions", "version", requires_project=False)]
    for res, path, key in [
        ("node", "/v1/nodes", "nodes"),
        ("port", "/v1/ports", "ports"),
        ("portgroup", "/v1/portgroups", "portgroups"),
        ("chassis", "/v1/chassis", "chassis"),
        ("allocation", "/v1/allocations", "allocations"),
        ("deploy_template", "/v1/deploy_templates", "deploy_templates"),
        ("volume_connector", "/v1/volume/connectors", "connectors"),
        ("volume_target", "/v1/volume/targets", "targets"),
    ]:
        ops.extend(_crud(res, path, key, detail=False))
    ops.extend(
        [
            _get("/v1/drivers", "ironic_drivers", "driver", "drivers"),
            _get("/v1/drivers/{name}", "ironic_driver_show", "driver"),
            _get("/v1/conductors", "ironic_conductors", "conductor", "conductors"),
            _put("/v1/nodes/{id}/states/provision", "node_provision_state", "node"),
            _put("/v1/nodes/{id}/states/power", "node_power_state", "node"),
            _put("/v1/nodes/{id}/states/raid", "node_raid_state", "node"),
            _get("/v1/nodes/{id}/states", "node_states", "node"),
            _get("/v1/nodes/{id}/vendor_passthru", "node_vendor_passthru", "node"),
            {
                "operation_id": "node_action",
                "method": "POST",
                "path": "/v1/nodes/{id}/vifs",
                "resource_type": "node",
                "kind": "action",
                "status_code": 204,
            },
        ]
    )
    return ops


def octavia_ops() -> list[dict[str, Any]]:
    ops = [_get("/v2", "octavia_versions", "version", requires_project=False)]
    for res, path, key in [
        ("loadbalancer", "/v2/lbaas/loadbalancers", "loadbalancers"),
        ("listener", "/v2/lbaas/listeners", "listeners"),
        ("pool", "/v2/lbaas/pools", "pools"),
        ("healthmonitor", "/v2/lbaas/healthmonitors", "healthmonitors"),
        ("l7policy", "/v2/lbaas/l7policies", "l7policies"),
        ("flavor", "/v2/lbaas/flavors", "flavors"),
        ("flavorprofile", "/v2/lbaas/flavorprofiles", "flavorprofiles"),
        ("amphora", "/v2/octavia/amphorae", "amphorae"),
        ("quota", "/v2/lbaas/quotas", "quotas"),
        ("provider", "/v2/lbaas/providers", "providers"),
    ]:
        ops.extend(_crud(res, path, key, detail=False))
    ops.extend(_crud("member", "/v2/lbaas/pools/{pool_id}/members", "members", detail=False))
    ops.extend(_crud("l7rule", "/v2/lbaas/l7policies/{l7policy_id}/rules", "rules", detail=False))
    ops.append(
        {
            "operation_id": "loadbalancer_failover",
            "method": "PUT",
            "path": "/v2/lbaas/loadbalancers/{id}/failover",
            "resource_type": "loadbalancer",
            "kind": "action",
            "status_code": 202,
        }
    )
    return ops


def _simple_service_ops(
    resources: list[tuple[str, str, str]],
    *,
    version_get: tuple[str, str] | None = None,
    extras: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    ops: list[dict[str, Any]] = []
    if version_get:
        ops.append(_get(version_get[0], version_get[1], "version", requires_project=False))
    for res, path, key in resources:
        ops.extend(_crud(res, path, key, detail=False))
    ops.extend(extras or [])
    return ops


def build_all_operations() -> dict[str, list[dict[str, Any]]]:
    return {
        "keystone": keystone_ops(),
        "nova": nova_ops(),
        "neutron": neutron_ops(),
        "glance": glance_ops(),
        "cinder": cinder_ops(),
        "placement": placement_ops(),
        "heat": heat_ops(),
        "heat-cfn": heat_cfn_ops(),
        "swift": swift_ops(),
        "ironic": ironic_ops(),
        "octavia": octavia_ops(),
        "barbican": _simple_service_ops(
            [
                ("secret", "/v1/secrets", "secrets"),
                ("container", "/v1/containers", "containers"),
                ("order", "/v1/orders", "orders"),
                ("secret_store", "/v1/secret-stores", "secret_stores"),
            ],
            version_get=("/v1", "barbican_versions"),
        ),
        "manila": _simple_service_ops(
            [
                ("share", "/v2/shares", "shares"),
                ("share_snapshot", "/v2/snapshots", "snapshots"),
                ("share_network", "/v2/share-networks", "share_networks"),
                ("share_type", "/v2/types", "share_types"),
                ("share_server", "/v2/share-servers", "share_servers"),
                ("security_service", "/v2/security-services", "security_services"),
                ("share_group", "/v2/share-groups", "share_groups"),
                ("share_replica", "/v2/share-replicas", "share_replicas"),
            ],
            version_get=("/v2", "manila_versions"),
            extras=[
                {
                    "operation_id": "share_action",
                    "method": "POST",
                    "path": "/v2/shares/{id}/action",
                    "resource_type": "share",
                    "kind": "action",
                    "status_code": 202,
                    "action_name": "*",
                }
            ],
        ),
        "designate": _simple_service_ops(
            [
                ("zone", "/v2/zones", "zones"),
                ("recordset", "/v2/zones/{zone_id}/recordsets", "recordsets"),
                ("tld", "/v2/tlds", "tlds"),
                ("blacklist", "/v2/blacklists", "blacklists"),
                ("pool", "/v2/pools", "pools"),
                ("service_status", "/v2/service_statuses", "service_statuses"),
            ],
            version_get=("/v2", "designate_versions"),
        ),
        "magnum": _simple_service_ops(
            [
                ("cluster", "/v1/clusters", "clusters"),
                ("clustertemplate", "/v1/clustertemplates", "clustertemplates"),
                ("certificate", "/v1/certificates", "certificates"),
                ("nodegroup", "/v1/clusters/{cluster_id}/nodegroups", "nodegroups"),
            ],
            version_get=("/v1", "magnum_versions"),
        ),
        "zun": _simple_service_ops(
            [
                ("container", "/v1/containers", "containers"),
                ("image", "/v1/images", "images"),
                ("capsule", "/v1/capsules", "capsules"),
                ("host", "/v1/hosts", "hosts"),
                ("service", "/v1/services", "services"),
            ],
            version_get=("/v1", "zun_versions"),
            extras=[
                {
                    "operation_id": "container_action",
                    "method": "POST",
                    "path": "/v1/containers/{id}/start",
                    "resource_type": "container",
                    "kind": "action",
                    "status_code": 202,
                },
                {
                    "operation_id": "container_stop",
                    "method": "POST",
                    "path": "/v1/containers/{id}/stop",
                    "resource_type": "container",
                    "kind": "action",
                    "status_code": 202,
                },
            ],
        ),
        "trove": _simple_service_ops(
            [
                ("instance", "/v1.0/instances", "instances"),
                ("datastore", "/v1.0/datastores", "datastores"),
                ("backup", "/v1.0/backups", "backups"),
                ("configuration", "/v1.0/configurations", "configurations"),
                ("cluster", "/v1.0/clusters", "clusters"),
            ],
            version_get=("/v1.0", "trove_versions"),
        ),
        "mistral": _simple_service_ops(
            [
                ("workflow", "/v2/workflows", "workflows"),
                ("execution", "/v2/executions", "executions"),
                ("action", "/v2/actions", "actions"),
                ("workbook", "/v2/workbooks", "workbooks"),
                ("cron_trigger", "/v2/cron_triggers", "cron_triggers"),
                ("task", "/v2/tasks", "tasks"),
            ],
            version_get=("/v2", "mistral_versions"),
        ),
        "aodh": _simple_service_ops(
            [
                ("alarm", "/v2/alarms", "alarms"),
                ("alarm_history", "/v2/alarms/{alarm_id}/history", "alarm_history"),
                ("quota", "/v2/quotas", "quotas"),
            ],
            version_get=("/v2", "aodh_versions"),
        ),
        "cloudkitty": _simple_service_ops(
            [
                ("hashmap_service", "/v1/rating/module_config/hashmap/services", "services"),
                ("hashmap_field", "/v1/rating/module_config/hashmap/fields", "fields"),
                ("report_summary", "/v1/report/summary", "summary"),
                ("dataframes", "/v1/storage/dataframes", "dataframes"),
            ],
            version_get=("/v1", "cloudkitty_versions"),
        ),
        "freezer": _simple_service_ops(
            [
                ("job", "/v2/jobs", "jobs"),
                ("client", "/v2/clients", "clients"),
                ("backup", "/v2/backups", "backups"),
                ("session", "/v2/sessions", "sessions"),
                ("action", "/v2/actions", "actions"),
            ],
            version_get=("/v2", "freezer_versions"),
        ),
        "blazar": _simple_service_ops(
            [
                ("lease", "/leases", "leases"),
                ("host", "/os-hosts", "hosts"),
                ("floatingip", "/floatingips", "floatingips"),
            ],
            version_get=("/v1", "blazar_versions"),
        ),
        "vitrage": _simple_service_ops(
            [
                ("topology", "/v1/topology", "topology"),
                ("alarm", "/v1/alarm", "alarms"),
                ("resource", "/v1/resources", "resources"),
                ("template", "/v1/template", "templates"),
                ("event", "/v1/event", "events"),
            ],
        ),
        "masakari": _simple_service_ops(
            [
                ("segment", "/v1/segments", "segments"),
                ("host", "/v1/segments/{segment_id}/hosts", "hosts"),
                ("notification", "/v1/notifications", "notifications"),
            ],
            version_get=("/v1", "masakari_versions"),
        ),
        "tacker": _simple_service_ops(
            [
                ("vnf", "/v1.0/vnfs", "vnfs"),
                ("vnfd", "/v1.0/vnfds", "vnfds"),
                ("vim", "/v1.0/vims", "vims"),
                ("vnf_package", "/vnfpkgm/v1/vnf_packages", "vnf_packages"),
                ("vnf_instance", "/vnflcm/v1/vnf_instances", "vnf_instances"),
            ],
        ),
        "adjutant": _simple_service_ops(
            [
                ("task", "/v1/tasks", "tasks"),
                ("token", "/v1/tokens", "tokens"),
                ("notification", "/v1/notifications", "notifications"),
                ("status", "/v1/status", "status"),
            ],
        ),
        # https://docs.openstack.org/2024.2/api/ — Infrastructure Optimization + Messaging
        "watcher": _simple_service_ops(
            [
                ("audit_template", "/v1/audit_templates", "audit_templates"),
                ("audit", "/v1/audits", "audits"),
                ("action_plan", "/v1/action_plans", "action_plans"),
                ("action", "/v1/actions", "actions"),
                ("goal", "/v1/goals", "goals"),
                ("strategy", "/v1/strategies", "strategies"),
                ("scoring_engine", "/v1/scoring_engines", "scoring_engines"),
                ("service", "/v1/services", "services"),
            ],
            version_get=("/v1", "watcher_versions"),
        ),
        "zaqar": _simple_service_ops(
            [
                ("queue", "/v2/queues", "queues"),
                ("subscription", "/v2/queues/{queue_name}/subscriptions", "subscriptions"),
                ("claim", "/v2/queues/{queue_name}/claims", "claims"),
                ("message", "/v2/queues/{queue_name}/messages", "messages"),
            ],
            version_get=("/v2", "zaqar_versions"),
            extras=[
                _get("/v2/health", "zaqar_health", "health", requires_project=False),
                _get("/v2/ping", "zaqar_ping", "ping", requires_auth=False, requires_project=False),
            ],
        ),
    }
