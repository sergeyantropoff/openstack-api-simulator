"""Declarative OpenStack API surface — all lab services and resource collections.

Collection GETs/POSTs and item GET/PATCH/PUT/DELETE are served from os_api_objects
unless a service mounts a specialized router that shadows the path.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ServiceSpec:
    name: str
    typ: str
    port: int
    version_path: str
    resources: tuple[tuple[str, str, str], ...]
    # resources: (resource_type, collection_path, item_key)
    # collection_path is absolute under the service (e.g. /v2.0/networks)


# Full OpenStack default ports (install-guide firewalls-default-ports).
SERVICES: tuple[ServiceSpec, ...] = (
    ServiceSpec(
        "keystone",
        "identity",
        5000,
        "/v3/",
        (
            ("domain", "/v3/domains", "domains"),
            ("project", "/v3/projects", "projects"),
            ("user", "/v3/users", "users"),
            ("group", "/v3/groups", "groups"),
            ("role", "/v3/roles", "roles"),
            ("region", "/v3/regions", "regions"),
            ("service", "/v3/services", "services"),
            ("endpoint", "/v3/endpoints", "endpoints"),
            (
                "application_credential",
                "/v3/users/{user_id}/application_credentials",
                "application_credentials",
            ),
            ("credential", "/v3/credentials", "credentials"),
            ("policy", "/v3/policies", "policies"),
        ),
    ),
    ServiceSpec(
        "nova",
        "compute",
        8774,
        "/v2.1/",
        (
            ("server", "/v2.1/servers", "servers"),
            ("flavor", "/v2.1/flavors", "flavors"),
            ("keypair", "/v2.1/os-keypairs", "keypairs"),
            ("aggregate", "/v2.1/os-aggregates", "aggregates"),
            ("hypervisor", "/v2.1/os-hypervisors", "hypervisors"),
            ("availability_zone", "/v2.1/os-availability-zone", "availabilityZoneInfo"),
            ("server_group", "/v2.1/os-server-groups", "server_groups"),
            ("service", "/v2.1/os-services", "services"),
            ("limit", "/v2.1/limits", "limits"),
            ("quota_set", "/v2.1/os-quota-sets", "quota_set"),
            (
                "instance_usage_audit_log",
                "/v2.1/os-instance_usage_audit_log",
                "instance_usage_audit_logs",
            ),
            ("migration", "/v2.1/os-migrations", "migrations"),
            ("assisted_volume_snapshot", "/v2.1/os-assisted-volume-snapshots", "snapshot"),
            ("console_auth_token", "/v2.1/os-console-auth-tokens", "console"),
            ("server_external_event", "/v2.1/os-server-external-events", "events"),
            ("instance_action", "/v2.1/servers/{server_id}/os-instance-actions", "instanceActions"),
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
            ("security_group", "/v2.1/os-security-groups", "security_groups"),
            ("floating_ip", "/v2.1/os-floating-ips", "floating_ips"),
            ("network", "/v2.1/os-networks", "networks"),
            ("tenant_network", "/v2.1/os-tenant-networks", "networks"),
        ),
    ),
    ServiceSpec(
        "neutron",
        "network",
        9696,
        "/v2.0/",
        (
            ("network", "/v2.0/networks", "networks"),
            ("subnet", "/v2.0/subnets", "subnets"),
            ("port", "/v2.0/ports", "ports"),
            ("router", "/v2.0/routers", "routers"),
            ("floatingip", "/v2.0/floatingips", "floatingips"),
            ("security_group", "/v2.0/security-groups", "security_groups"),
            ("security_group_rule", "/v2.0/security-group-rules", "security_group_rules"),
            ("address_scope", "/v2.0/address-scopes", "address_scopes"),
            ("subnetpool", "/v2.0/subnetpools", "subnetpools"),
            ("qos_policy", "/v2.0/qos/policies", "policies"),
            ("qos_rule_type", "/v2.0/qos/rule-types", "rule_types"),
            ("trunk", "/v2.0/trunks", "trunks"),
            ("rbac_policy", "/v2.0/rbac-policies", "rbac_policies"),
            ("agent", "/v2.0/agents", "agents"),
            (
                "network_ip_availability",
                "/v2.0/network-ip-availabilities",
                "network_ip_availabilities",
            ),
            ("auto_allocated_topology", "/v2.0/auto-allocated-topology", "auto_allocated_topology"),
            ("lbaas_loadbalancer", "/v2.0/lbaas/loadbalancers", "loadbalancers"),
            ("lbaas_listener", "/v2.0/lbaas/listeners", "listeners"),
            ("lbaas_pool", "/v2.0/lbaas/pools", "pools"),
            ("metering_label", "/v2.0/metering/metering-labels", "metering_labels"),
            ("firewall_group", "/v2.0/fwaas/firewall_groups", "firewall_groups"),
            ("vpn_service", "/v2.0/vpn/vpnservices", "vpnservices"),
            ("bgpvpn", "/v2.0/bgpvpn/bgpvpns", "bgpvpns"),
            ("log", "/v2.0/log/logs", "logs"),
            ("ndp_proxy", "/v2.0/ndp_proxies", "ndp_proxies"),
            ("local_ip", "/v2.0/local_ips", "local_ips"),
            (
                "conntrack_helper",
                "/v2.0/routers/{router_id}/conntrack_helpers",
                "conntrack_helpers",
            ),
            ("quota", "/v2.0/quotas", "quotas"),
            (
                "floatingip_port_forwarding",
                "/v2.0/floatingips/{floatingip_id}/port_forwardings",
                "port_forwardings",
            ),
        ),
    ),
    ServiceSpec(
        "glance",
        "image",
        9292,
        "/v2/",
        (
            ("image", "/v2/images", "images"),
            ("metadef_namespace", "/v2/metadefs/namespaces", "namespaces"),
            ("task", "/v2/tasks", "tasks"),
            ("info_import", "/v2/info/import", "import-methods"),
            ("info_store", "/v2/info/stores", "stores"),
        ),
    ),
    ServiceSpec(
        "cinder",
        "volumev3",
        8776,
        "/v3/",
        (
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
            ("service", "/v3/os-services", "services"),
            ("quota_set", "/v3/os-quota-sets", "quota_set"),
            ("limit", "/v3/limits", "limits"),
            ("cluster", "/v3/clusters", "clusters"),
            ("message", "/v3/messages", "messages"),
            ("resource_filter", "/v3/resource_filters", "resource_filters"),
        ),
    ),
    ServiceSpec(
        "placement",
        "placement",
        8003,
        "/",
        (
            ("resource_provider", "/resource_providers", "resource_providers"),
            ("resource_class", "/resource_classes", "resource_classes"),
            ("trait", "/traits", "traits"),
            ("allocation", "/allocations", "allocations"),
            ("usage", "/usages", "usages"),
            ("allocation_candidate", "/allocation_candidates", "allocation_candidates"),
        ),
    ),
    ServiceSpec(
        "heat",
        "orchestration",
        8004,
        "/v1/",
        (
            ("stack", "/v1/{tenant_id}/stacks", "stacks"),
            ("resource", "/v1/{tenant_id}/stacks/{stack_name}/{stack_id}/resources", "resources"),
            ("event", "/v1/{tenant_id}/stacks/{stack_name}/{stack_id}/events", "events"),
            ("software_config", "/v1/{tenant_id}/software_configs", "software_configs"),
            ("software_deployment", "/v1/{tenant_id}/software_deployments", "software_deployments"),
            ("resource_type", "/v1/{tenant_id}/resource_types", "resource_types"),
            ("service", "/v1/{tenant_id}/services", "services"),
        ),
    ),
    ServiceSpec(
        "heat-cfn",
        "cloudformation",
        8000,
        "/v1/",
        (("stack", "/stacks", "Stacks"),),
    ),
    ServiceSpec(
        "swift",
        "object-store",
        8080,
        "/v1/",
        (
            ("account", "/v1/{account}", "account"),
            ("container", "/v1/{account}/{container}", "container"),
            ("object", "/v1/{account}/{container}/{object}", "object"),
        ),
    ),
    ServiceSpec(
        "ironic",
        "baremetal",
        6385,
        "/",
        (
            ("node", "/v1/nodes", "nodes"),
            ("port", "/v1/ports", "ports"),
            ("portgroup", "/v1/portgroups", "portgroups"),
            ("chassis", "/v1/chassis", "chassis"),
            ("driver", "/v1/drivers", "drivers"),
            ("volume_connector", "/v1/volume/connectors", "connectors"),
            ("volume_target", "/v1/volume/targets", "targets"),
            ("allocation", "/v1/allocations", "allocations"),
            ("deploy_template", "/v1/deploy_templates", "deploy_templates"),
            ("conductor", "/v1/conductors", "conductors"),
        ),
    ),
    ServiceSpec(
        "octavia",
        "load-balancer",
        9876,
        "/v2/",
        (
            ("loadbalancer", "/v2/lbaas/loadbalancers", "loadbalancers"),
            ("listener", "/v2/lbaas/listeners", "listeners"),
            ("pool", "/v2/lbaas/pools", "pools"),
            ("member", "/v2/lbaas/pools/{pool_id}/members", "members"),
            ("healthmonitor", "/v2/lbaas/healthmonitors", "healthmonitors"),
            ("l7policy", "/v2/lbaas/l7policies", "l7policies"),
            ("l7rule", "/v2/lbaas/l7policies/{l7policy_id}/rules", "rules"),
            ("amphora", "/v2/octavia/amphorae", "amphorae"),
            ("quota", "/v2/lbaas/quotas", "quotas"),
            ("provider", "/v2/lbaas/providers", "providers"),
            ("flavor", "/v2/lbaas/flavors", "flavors"),
            ("flavorprofile", "/v2/lbaas/flavorprofiles", "flavorprofiles"),
        ),
    ),
    ServiceSpec(
        "barbican",
        "key-manager",
        9311,
        "/v1/",
        (
            ("secret", "/v1/secrets", "secrets"),
            ("container", "/v1/containers", "containers"),
            ("order", "/v1/orders", "orders"),
            ("secret_store", "/v1/secret-stores", "secret_stores"),
        ),
    ),
    ServiceSpec(
        "manila",
        "sharev2",
        8786,
        "/v2/",
        (
            ("share", "/v2/shares", "shares"),
            ("share_snapshot", "/v2/snapshots", "snapshots"),
            ("share_network", "/v2/share-networks", "share_networks"),
            ("share_type", "/v2/types", "share_types"),
            ("share_server", "/v2/share-servers", "share_servers"),
            ("security_service", "/v2/security-services", "security_services"),
            ("share_group", "/v2/share-groups", "share_groups"),
        ),
    ),
    ServiceSpec(
        "designate",
        "dns",
        9001,
        "/v2/",
        (
            ("zone", "/v2/zones", "zones"),
            ("recordset", "/v2/zones/{zone_id}/recordsets", "recordsets"),
            ("tld", "/v2/tlds", "tlds"),
            ("blacklist", "/v2/blacklists", "blacklists"),
            ("pool", "/v2/pools", "pools"),
            ("service_status", "/v2/service_statuses", "service_statuses"),
        ),
    ),
    ServiceSpec(
        "magnum",
        "container-infra",
        9511,
        "/v1/",
        (
            ("cluster", "/v1/clusters", "clusters"),
            ("clustertemplate", "/v1/clustertemplates", "clustertemplates"),
            ("certificate", "/v1/certificates", "certificates"),
            ("nodegroup", "/v1/clusters/{cluster_id}/nodegroups", "nodegroups"),
        ),
    ),
    ServiceSpec(
        "zun",
        "container",
        9517,
        "/v1/",
        (
            ("container", "/v1/containers", "containers"),
            ("image", "/v1/images", "images"),
            ("capsule", "/v1/capsules", "capsules"),
            ("host", "/v1/hosts", "hosts"),
            ("service", "/v1/services", "services"),
        ),
    ),
    ServiceSpec(
        "trove",
        "database",
        8779,
        "/v1.0/",
        (
            ("instance", "/v1.0/instances", "instances"),
            ("datastore", "/v1.0/datastores", "datastores"),
            ("backup", "/v1.0/backups", "backups"),
            ("configuration", "/v1.0/configurations", "configurations"),
            ("cluster", "/v1.0/clusters", "clusters"),
        ),
    ),
    ServiceSpec(
        "mistral",
        "workflowv2",
        8989,
        "/v2/",
        (
            ("workflow", "/v2/workflows", "workflows"),
            ("execution", "/v2/executions", "executions"),
            ("action", "/v2/actions", "actions"),
            ("workbook", "/v2/workbooks", "workbooks"),
            ("cron_trigger", "/v2/cron_triggers", "cron_triggers"),
            ("task", "/v2/tasks", "tasks"),
        ),
    ),
    ServiceSpec(
        "aodh",
        "alarming",
        8042,
        "/v2/",
        (
            ("alarm", "/v2/alarms", "alarms"),
            ("alarm_history", "/v2/alarms/{alarm_id}/history", "alarm_history"),
            ("quota", "/v2/quotas", "quotas"),
        ),
    ),
    ServiceSpec(
        "cloudkitty",
        "rating",
        8889,
        "/v1/",
        (
            ("hashmap_service", "/v1/rating/module_config/hashmap/services", "services"),
            ("hashmap_field", "/v1/rating/module_config/hashmap/fields", "fields"),
            ("report_summary", "/v1/report/summary", "summary"),
            ("dataframes", "/v1/storage/dataframes", "dataframes"),
        ),
    ),
    ServiceSpec(
        "freezer",
        "backup",
        9090,
        "/v2/",
        (
            ("job", "/v2/jobs", "jobs"),
            ("client", "/v2/clients", "clients"),
            ("backup", "/v2/backups", "backups"),
            ("session", "/v2/sessions", "sessions"),
            ("action", "/v2/actions", "actions"),
        ),
    ),
    ServiceSpec(
        "blazar",
        "reservation",
        1234,
        "/v1/",
        (
            ("lease", "/leases", "leases"),
            ("host", "/os-hosts", "hosts"),
            ("floatingip", "/floatingips", "floatingips"),
        ),
    ),
    ServiceSpec(
        "vitrage",
        "rca",
        8999,
        "/",
        (
            ("topology", "/v1/topology", "topology"),
            ("alarm", "/v1/alarm", "alarms"),
            ("resource", "/v1/resources", "resources"),
            ("template", "/v1/template", "templates"),
            ("event", "/v1/event", "events"),
        ),
    ),
    ServiceSpec(
        "masakari",
        "instance-ha",
        15868,
        "/v1/",
        (
            ("segment", "/v1/segments", "segments"),
            ("host", "/v1/segments/{segment_id}/hosts", "hosts"),
            ("notification", "/v1/notifications", "notifications"),
        ),
    ),
    ServiceSpec(
        "tacker",
        "nfv-orchestration",
        9890,
        "/",
        (
            ("vnf", "/v1.0/vnfs", "vnfs"),
            ("vnfd", "/v1.0/vnfds", "vnfds"),
            ("vim", "/v1.0/vims", "vims"),
            ("vnf_package", "/vnfpkgm/v1/vnf_packages", "vnf_packages"),
            ("vnf_instance", "/vnflcm/v1/vnf_instances", "vnf_instances"),
        ),
    ),
    ServiceSpec(
        "adjutant",
        "admin-logic",
        5050,
        "/",
        (
            ("task", "/v1/tasks", "tasks"),
            ("token", "/v1/tokens", "tokens"),
            ("notification", "/v1/notifications", "notifications"),
            ("status", "/v1/status", "status"),
        ),
    ),
    ServiceSpec(
        "watcher",
        "infra-optim",
        9322,
        "/v1/",
        (
            ("audit_template", "/v1/audit_templates", "audit_templates"),
            ("audit", "/v1/audits", "audits"),
            ("action_plan", "/v1/action_plans", "action_plans"),
            ("action", "/v1/actions", "actions"),
            ("goal", "/v1/goals", "goals"),
            ("strategy", "/v1/strategies", "strategies"),
            ("scoring_engine", "/v1/scoring_engines", "scoring_engines"),
            ("service", "/v1/services", "services"),
        ),
    ),
    ServiceSpec(
        "zaqar",
        "messaging",
        8888,
        "/v2/",
        (
            ("queue", "/v2/queues", "queues"),
            ("subscription", "/v2/queues/{queue_name}/subscriptions", "subscriptions"),
            ("claim", "/v2/queues/{queue_name}/claims", "claims"),
            ("message", "/v2/queues/{queue_name}/messages", "messages"),
        ),
    ),
)


def all_service_ports() -> dict[str, int]:
    return {spec.name: spec.port for spec in SERVICES}


def catalog_entries(host: str, *, scheme: str = "http") -> list[dict[str, object]]:
    catalog: list[dict[str, object]] = []
    for spec in SERVICES:
        if spec.name == "heat-cfn":
            url = f"{scheme}://{host}:{spec.port}"
        elif spec.name == "swift":
            url = f"{scheme}://{host}:{spec.port}/v1"
        elif spec.name == "placement":
            url = f"{scheme}://{host}:{spec.port}"
        elif spec.name == "ironic":
            url = f"{scheme}://{host}:{spec.port}"
        elif spec.name == "nova":
            url = f"{scheme}://{host}:{spec.port}/v2.1"
        elif spec.name == "cinder":
            url = f"{scheme}://{host}:{spec.port}/v3"
        elif spec.name == "glance":
            # Unversioned: terraform-provider-openstack appends /v2 itself.
            # Clients must reach this port without an HTTP proxy (see run_iac_stack.sh).
            url = f"{scheme}://{host}:{spec.port}"
        elif spec.name == "neutron":
            url = f"{scheme}://{host}:{spec.port}"
        elif spec.name == "keystone":
            url = f"{scheme}://{host}:{spec.port}/v3"
        elif spec.name == "octavia":
            # Specialized routes live under /v2/lbaas/… (not /v2.0).
            url = f"{scheme}://{host}:{spec.port}/v2"
        elif spec.name == "blazar":
            # Contract paths are /leases, /os-hosts (no /v1 prefix).
            url = f"{scheme}://{host}:{spec.port}"
        elif spec.name == "heat":
            url = f"{scheme}://{host}:{spec.port}/v1"
        else:
            url = f"{scheme}://{host}:{spec.port}{spec.version_path.rstrip('/')}"
        catalog.append(
            {
                "id": spec.name,
                "type": spec.typ,
                "name": spec.name,
                "endpoints": [
                    {
                        "id": f"{spec.name}-public",
                        "interface": "public",
                        "region": "RegionOne",
                        "region_id": "RegionOne",
                        "url": url,
                    },
                    {
                        "id": f"{spec.name}-internal",
                        "interface": "internal",
                        "region": "RegionOne",
                        "region_id": "RegionOne",
                        "url": url,
                    },
                    {
                        "id": f"{spec.name}-admin",
                        "interface": "admin",
                        "region": "RegionOne",
                        "region_id": "RegionOne",
                        "url": url,
                    },
                ],
            }
        )
    return catalog
