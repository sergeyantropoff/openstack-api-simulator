"""JSON Schema fragments for OpenStack request bodies (api-ref style).

Used by ``generate_request_bodies.py`` to emit
``contracts/openstack/request_bodies/<service>.json`` for every write op.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.openstack.singular import singular

Str = dict[str, Any]


def _s(
    description: str = "",
    *,
    enum: list[Any] | None = None,
    fmt: str | None = None,
    example: Any = None,
    default: Any = None,
) -> Str:
    out: Str = {"type": "string", "description": description}
    if enum is not None:
        out["enum"] = enum
    if fmt:
        out["format"] = fmt
    if example is not None:
        out["example"] = example
    if default is not None:
        out["default"] = default
    return out


def _i(description: str = "", *, minimum: int | None = None, example: int | None = None) -> Str:
    out: Str = {"type": "integer", "description": description}
    if minimum is not None:
        out["minimum"] = minimum
    if example is not None:
        out["example"] = example
    return out


def _b(description: str = "", *, default: bool | None = None) -> Str:
    out: Str = {"type": "boolean", "description": description}
    if default is not None:
        out["default"] = default
    return out


def _o(properties: dict[str, Str], required: list[str] | None = None, description: str = "") -> Str:
    out: Str = {"type": "object", "description": description, "properties": properties}
    if required:
        out["required"] = required
    return out


def _a(items: Str, description: str = "") -> Str:
    return {"type": "array", "description": description, "items": items}


def _envelope(key: str, inner: Str, *, required_inner: bool = True) -> Str:
    return _o({key: inner}, required=[key] if required_inner else None)


# --- Resource property libraries (api-ref style) ---

def _name_desc() -> dict[str, Str]:
    return {
        "name": _s("Human-readable name", example="example"),
        "description": _s("Optional description", example=""),
    }


def props_server() -> Str:
    return _o(
        {
            **_name_desc(),
            "flavorRef": _s("Flavor UUID or id", example="1"),
            "imageRef": _s("Image UUID", fmt="uuid"),
            "networks": _a(
                _o(
                    {
                        "uuid": _s("Network UUID", fmt="uuid"),
                        "port": _s("Port UUID", fmt="uuid"),
                        "fixed_ip": _s("Fixed IP address"),
                    }
                ),
                "NICs",
            ),
            "adminPass": _s("Admin password"),
            "key_name": _s("Keypair name"),
            "metadata": _o({}, description="Arbitrary key/value metadata"),
            "security_groups": _a(_o({"name": _s("Security group name")})),
            "availability_zone": _s("AZ name"),
            "user_data": _s("Base64 user data"),
            "config_drive": _b("Attach config drive"),
            "min_count": _i("Minimum instances", minimum=1, example=1),
            "max_count": _i("Maximum instances", minimum=1, example=1),
            "block_device_mapping_v2": _a(_o({}, description="BDM v2 entry")),
        },
        required=["name", "flavorRef", "networks"],
    )


def props_network() -> Str:
    return _o(
        {
            **_name_desc(),
            "admin_state_up": _b("Administrative state", default=True),
            "shared": _b("Shared across projects", default=False),
            "external": _b("External network", default=False),
            "provider:network_type": _s("Provider network type", enum=["local", "flat", "vlan", "vxlan", "gre"]),
            "provider:physical_network": _s("Physical network label"),
            "provider:segmentation_id": _i("Segmentation id"),
            "mtu": _i("MTU", minimum=68, example=1500),
            "port_security_enabled": _b("Port security", default=True),
            "router:external": _b("Router external alias", default=False),
        },
        required=["name"],
    )


def props_subnet() -> Str:
    return _o(
        {
            **_name_desc(),
            "network_id": _s("Parent network UUID", fmt="uuid"),
            "cidr": _s("CIDR", example="10.0.0.0/24"),
            "ip_version": _i("IP version", example=4),
            "gateway_ip": _s("Gateway IP"),
            "enable_dhcp": _b("DHCP enabled", default=True),
            "dns_nameservers": _a(_s("DNS server"), "DNS nameservers"),
            "allocation_pools": _a(
                _o({"start": _s("Start IP"), "end": _s("End IP")}),
                "Allocation pools",
            ),
            "host_routes": _a(_o({"destination": _s(), "nexthop": _s()}), "Host routes"),
            "ipv6_address_mode": _s("IPv6 address mode"),
            "ipv6_ra_mode": _s("IPv6 RA mode"),
        },
        required=["network_id", "cidr", "ip_version"],
    )


def props_port() -> Str:
    return _o(
        {
            **_name_desc(),
            "network_id": _s("Network UUID", fmt="uuid"),
            "admin_state_up": _b("Administrative state", default=True),
            "mac_address": _s("MAC address"),
            "fixed_ips": _a(
                _o({"subnet_id": _s(fmt="uuid"), "ip_address": _s()}),
                "Fixed IPs",
            ),
            "device_id": _s("Device UUID", fmt="uuid"),
            "device_owner": _s("Device owner"),
            "security_groups": _a(_s("Security group UUID", fmt="uuid")),
            "binding:vnic_type": _s("VNIC type", enum=["normal", "direct", "macvtap", "baremetal"]),
            "port_security_enabled": _b("Port security"),
            "allowed_address_pairs": _a(_o({"ip_address": _s(), "mac_address": _s()})),
        },
        required=["network_id"],
    )


def props_router() -> Str:
    return _o(
        {
            **_name_desc(),
            "admin_state_up": _b("Administrative state", default=True),
            "external_gateway_info": _o(
                {
                    "network_id": _s("External network UUID", fmt="uuid"),
                    "enable_snat": _b("SNAT", default=True),
                    "external_fixed_ips": _a(_o({"subnet_id": _s(fmt="uuid"), "ip_address": _s()})),
                }
            ),
            "distributed": _b("DVR router"),
            "ha": _b("Highly available"),
            "routes": _a(_o({"destination": _s(), "nexthop": _s()})),
        },
        required=["name"],
    )


def props_floatingip() -> Str:
    return _o(
        {
            "floating_network_id": _s("External network UUID", fmt="uuid"),
            "port_id": _s("Port UUID", fmt="uuid"),
            "fixed_ip_address": _s("Fixed IP"),
            "floating_ip_address": _s("Floating IP"),
            "description": _s(),
            "subnet_id": _s("Subnet UUID", fmt="uuid"),
            "dns_name": _s(),
            "dns_domain": _s(),
        },
        required=["floating_network_id"],
    )


def props_security_group() -> Str:
    return _o({**_name_desc()}, required=["name"])


def props_security_group_rule() -> Str:
    return _o(
        {
            "security_group_id": _s("Security group UUID", fmt="uuid"),
            "direction": _s("Direction", enum=["ingress", "egress"], example="ingress"),
            "ethertype": _s("Ethertype", enum=["IPv4", "IPv6"], example="IPv4"),
            "protocol": _s("Protocol", example="tcp"),
            "port_range_min": _i("Min port", example=22),
            "port_range_max": _i("Max port", example=22),
            "remote_ip_prefix": _s("CIDR", example="0.0.0.0/0"),
            "remote_group_id": _s("Remote SG UUID", fmt="uuid"),
            "description": _s(),
        },
        required=["security_group_id", "direction"],
    )


def props_volume() -> Str:
    return _o(
        {
            **_name_desc(),
            "size": _i("Size in GiB", minimum=1, example=1),
            "volume_type": _s("Volume type name"),
            "availability_zone": _s("AZ"),
            "snapshot_id": _s("Snapshot UUID", fmt="uuid"),
            "source_volid": _s("Source volume UUID", fmt="uuid"),
            "imageRef": _s("Image UUID", fmt="uuid"),
            "metadata": _o({}),
            "consistencygroup_id": _s(fmt="uuid"),
            "multiattach": _b("Multi-attach"),
        },
        required=["size"],
    )


def props_snapshot() -> Str:
    return _o(
        {
            **_name_desc(),
            "volume_id": _s("Volume UUID", fmt="uuid"),
            "force": _b("Force snapshot"),
            "metadata": _o({}),
        },
        required=["volume_id"],
    )


def props_image() -> Str:
    return _o(
        {
            **_name_desc(),
            "container_format": _s(
                "Container format",
                enum=["bare", "ovf", "aki", "ari", "ami", "ova", "docker"],
                example="bare",
            ),
            "disk_format": _s(
                "Disk format",
                enum=["raw", "qcow2", "vmdk", "vdi", "iso", "aki", "ari", "ami"],
                example="qcow2",
            ),
            "visibility": _s("Visibility", enum=["public", "private", "shared", "community"], example="private"),
            "protected": _b("Protected"),
            "tags": _a(_s()),
            "min_disk": _i("Min disk GiB", minimum=0, example=0),
            "min_ram": _i("Min RAM MiB", minimum=0, example=0),
            "os_type": _s("OS type"),
            "architecture": _s("CPU architecture"),
        },
        required=["name", "container_format", "disk_format"],
    )


def props_vim() -> Str:
    return _o(
        {
            "type": _s("VIM type", enum=["openstack", "kubernetes"], example="openstack"),
            "auth_url": _s("Identity endpoint", fmt="uri", example="http://127.0.0.1:5000/v3"),
            "auth_cred": _o(
                {
                    "username": _s("Username", example="admin"),
                    "password": _s("Password", example="secret"),
                    "user_domain_name": _s("User domain", example="Default"),
                    "cert_verify": _s("TLS verify", example="True"),
                },
                required=["username", "password", "user_domain_name"],
            ),
            "vim_project": _o(
                {
                    "name": _s("Project name", example="admin"),
                    "project_domain_name": _s("Project domain", example="Default"),
                },
                required=["name", "project_domain_name"],
            ),
            "name": _s("VIM name", example="example"),
            "description": _s(),
            "is_default": _b("Default VIM", default=False),
        },
        required=["type", "auth_url", "auth_cred", "vim_project", "name"],
    )


def props_stack() -> Str:
    return _o(
        {
            "stack_name": _s("Stack name", example="example"),
            "template": _o(
                {
                    "heat_template_version": _s(example="2015-04-30"),
                    "description": _s(),
                    "resources": _o({}),
                    "parameters": _o({}),
                },
                required=["heat_template_version"],
            ),
            "template_url": _s("Template URL", fmt="uri"),
            "parameters": _o({}, description="Stack parameters"),
            "timeout_mins": _i("Timeout minutes", example=60),
            "disable_rollback": _b("Disable rollback", default=True),
            "environment": _o({}),
            "files": _o({}),
            "tags": _a(_s()),
        },
        required=["stack_name", "template"],
    )


def props_secret() -> Str:
    return _o(
        {
            "name": _s("Secret name", example="example"),
            "payload": _s("Secret payload", example="c2VjcmV0"),
            "payload_content_type": _s("Content type", example="text/plain"),
            "payload_content_encoding": _s("Encoding", enum=["base64"], example="base64"),
            "algorithm": _s("Algorithm"),
            "bit_length": _i("Bit length"),
            "mode": _s("Mode"),
            "secret_type": _s(
                "Secret type",
                enum=["opaque", "symmetric", "public", "private", "certificate", "passphrase"],
                example="opaque",
            ),
            "expiration": _s("Expiration timestamp"),
        },
        required=["payload"],
    )


def props_alarm() -> Str:
    return _o(
        {
            **_name_desc(),
            "type": _s("Alarm type", enum=["threshold", "event", "gnocchi_resources_threshold"], example="threshold"),
            "enabled": _b("Enabled", default=True),
            "alarm_actions": _a(_s("Webhook URL", fmt="uri")),
            "ok_actions": _a(_s(fmt="uri")),
            "insufficient_data_actions": _a(_s(fmt="uri")),
            "repeat_actions": _b("Repeat actions", default=True),
            "threshold_rule": _o(
                {
                    "meter_name": _s(example="cpu_util"),
                    "threshold": _i(example=80),
                    "comparison_operator": _s(enum=["gt", "lt", "ge", "le", "eq", "ne"], example="gt"),
                    "evaluation_periods": _i(example=1),
                    "period": _i(example=60),
                    "statistic": _s(enum=["avg", "max", "min", "sum", "count"], example="avg"),
                    "query": _a(_o({"field": _s(), "op": _s(), "value": _s()})),
                }
            ),
        },
        required=["name", "type"],
    )


def props_zone() -> Str:
    return _o(
        {
            "name": _s("Zone name FQDN", example="example.com."),
            "email": _s("SOA email", fmt="email", example="hostmaster@example.com"),
            "ttl": _i("TTL seconds", example=3600),
            "description": _s(),
            "type": _s("Zone type", enum=["PRIMARY", "SECONDARY"], example="PRIMARY"),
            "masters": _a(_s("Master server")),
            "attributes": _o({}),
        },
        required=["name", "email"],
    )


def props_recordset() -> Str:
    return _o(
        {
            "name": _s("Recordset name", example="www.example.com."),
            "type": _s("RR type", enum=["A", "AAAA", "CNAME", "MX", "TXT", "SRV", "NS", "PTR"], example="A"),
            "records": _a(_s("Record data"), "Records"),
            "ttl": _i("TTL", example=3600),
            "description": _s(),
        },
        required=["name", "type", "records"],
    )


def props_loadbalancer() -> Str:
    return _o(
        {
            **_name_desc(),
            "vip_subnet_id": _s("VIP subnet UUID", fmt="uuid"),
            "vip_network_id": _s("VIP network UUID", fmt="uuid"),
            "vip_address": _s("VIP address"),
            "provider": _s("Provider", example="amphora"),
            "flavor_id": _s(fmt="uuid"),
            "admin_state_up": _b(default=True),
            "listeners": _a(_o({})),
            "pools": _a(_o({})),
            "project_id": _s(fmt="uuid"),
        },
        required=["vip_subnet_id"],
    )


def props_listener() -> Str:
    return _o(
        {
            **_name_desc(),
            "loadbalancer_id": _s(fmt="uuid"),
            "protocol": _s(enum=["HTTP", "HTTPS", "TCP", "UDP", "TERMINATED_HTTPS"], example="HTTP"),
            "protocol_port": _i(example=80),
            "connection_limit": _i(example=-1),
            "admin_state_up": _b(default=True),
            "default_pool_id": _s(fmt="uuid"),
            "insert_headers": _o({}),
        },
        required=["loadbalancer_id", "protocol", "protocol_port"],
    )


def props_pool() -> Str:
    return _o(
        {
            **_name_desc(),
            "lb_algorithm": _s(
                enum=["ROUND_ROBIN", "LEAST_CONNECTIONS", "SOURCE_IP"],
                example="ROUND_ROBIN",
            ),
            "protocol": _s(enum=["HTTP", "HTTPS", "TCP", "UDP", "PROXY"], example="HTTP"),
            "listener_id": _s(fmt="uuid"),
            "loadbalancer_id": _s(fmt="uuid"),
            "admin_state_up": _b(default=True),
            "session_persistence": _o({"type": _s(), "cookie_name": _s()}),
        },
        required=["lb_algorithm", "protocol"],
    )


def props_member() -> Str:
    return _o(
        {
            **_name_desc(),
            "address": _s("Member IP", example="10.0.0.10"),
            "protocol_port": _i(example=80),
            "subnet_id": _s(fmt="uuid"),
            "weight": _i(example=1),
            "admin_state_up": _b(default=True),
            "monitor_address": _s(),
            "monitor_port": _i(),
            "backup": _b(default=False),
        },
        required=["address", "protocol_port"],
    )


def props_cluster() -> Str:
    return _o(
        {
            **_name_desc(),
            "cluster_template_id": _s(fmt="uuid"),
            "node_count": _i(example=1),
            "master_count": _i(example=1),
            "keypair": _s("Keypair name"),
            "labels": _o({}),
            "flavor_id": _s(),
            "master_flavor_id": _s(),
            "docker_volume_size": _i(example=5),
        },
        required=["name", "cluster_template_id"],
    )


def props_cluster_template() -> Str:
    return _o(
        {
            **_name_desc(),
            "image_id": _s(fmt="uuid"),
            "coe": _s(enum=["kubernetes", "swarm", "mesos"], example="kubernetes"),
            "keypair_id": _s(),
            "external_network_id": _s(fmt="uuid"),
            "dns_nameserver": _s(example="8.8.8.8"),
            "flavor_id": _s(),
            "master_flavor_id": _s(),
            "docker_volume_size": _i(example=5),
            "network_driver": _s(example="flannel"),
            "volume_driver": _s(),
            "public": _b(default=False),
            "registry_enabled": _b(default=False),
            "tls_disabled": _b(default=False),
        },
        required=["name", "image_id", "coe"],
    )


def props_share() -> Str:
    return _o(
        {
            **_name_desc(),
            "size": _i("Size GiB", minimum=1, example=1),
            "share_proto": _s(enum=["NFS", "CIFS", "GlusterFS", "HDFS", "CephFS"], example="NFS"),
            "share_type": _s(),
            "share_network_id": _s(fmt="uuid"),
            "availability_zone": _s(),
            "metadata": _o({}),
            "is_public": _b(default=False),
            "snapshot_id": _s(fmt="uuid"),
        },
        required=["size", "share_proto"],
    )


def props_instance() -> Str:  # trove / zun style
    return _o(
        {
            **_name_desc(),
            "flavorRef": _s(example="1"),
            "volume_size": _i(example=1),
            "datastore": _o(
                {"type": _s(example="mysql"), "version": _s(example="8.0")},
                required=["type", "version"],
            ),
            "nics": _a(_o({"net-id": _s(fmt="uuid")})),
            "databases": _a(_o({"name": _s()})),
            "users": _a(_o({"name": _s(), "password": _s(), "databases": _a(_o({"name": _s()}))})),
            "availability_zone": _s(),
        },
        required=["name", "flavorRef"],
    )


def props_container() -> Str:
    return _o(
        {
            **_name_desc(),
            "image": _s("Container image", example="cirros"),
            "command": _s("Command"),
            "cpu": _i(example=1),
            "memory": _i("Memory MiB", example=512),
            "workdir": _s(),
            "environment": _o({}),
            "nets": _a(_o({"network": _s(fmt="uuid")})),
            "restart_policy": _o({"Name": _s(example="no"), "MaximumRetryCount": _i(example=0)}),
            "interactive": _b(default=False),
            "tty": _b(default=False),
        },
        required=["image"],
    )


def props_node() -> Str:  # ironic
    return _o(
        {
            **_name_desc(),
            "driver": _s(example="ipmi"),
            "driver_info": _o(
                {
                    "ipmi_address": _s(),
                    "ipmi_username": _s(),
                    "ipmi_password": _s(),
                }
            ),
            "properties": _o({"cpus": _i(example=4), "memory_mb": _i(example=8192), "local_gb": _i(example=100)}),
            "resource_class": _s(example="baremetal"),
            "conductor_group": _s(),
            "network_interface": _s(example="flat"),
            "storage_interface": _s(),
            "boot_interface": _s(),
            "deploy_interface": _s(),
        },
        required=["driver"],
    )


def props_workflow() -> Str:
    return _o(
        {
            **_name_desc(),
            "definition": _s("Workflow DSL", example="version: '2.0'\nexample:\n  tasks: {}"),
            "scope": _s(enum=["private", "public"], example="private"),
            "namespace": _s(),
            "input": _s(),
            "tags": _a(_s()),
        },
        required=["definition"],
    )


def props_execution() -> Str:
    return _o(
        {
            "workflow_name": _s(example="example"),
            "workflow_id": _s(fmt="uuid"),
            "input": _o({}),
            "params": _o({}),
            "description": _s(),
        },
        required=["workflow_name"],
    )


def props_host() -> Str:  # blazar
    return _o(
        {
            "name": _s(example="example"),
            "reservable": _b(default=True),
            "extra_capabilities": _o({}),
        },
        required=["name"],
    )


def props_lease() -> Str:
    return _o(
        {
            "name": _s(example="example"),
            "start_date": _s(example="2026-01-01 00:00"),
            "end_date": _s(example="2026-01-02 00:00"),
            "reservations": _a(
                _o(
                    {
                        "resource_type": _s(example="physical:host"),
                        "min": _i(example=1),
                        "max": _i(example=1),
                        "hypervisor_properties": _s(),
                        "resource_properties": _s(),
                    }
                )
            ),
            "events": _a(_o({})),
        },
        required=["name", "start_date", "end_date", "reservations"],
    )


def props_segment() -> Str:  # masakari
    return _o(
        {
            **_name_desc(),
            "recovery_method": _s(enum=["auto", "reserved_host", "auto_priority", "rh_priority"], example="auto"),
            "service_type": _s(enum=["compute"], example="compute"),
        },
        required=["name", "recovery_method", "service_type"],
    )


def props_notification() -> Str:
    return _o(
        {
            "type": _s(enum=["VM", "PROCESS", "COMPUTE_HOST"], example="VM"),
            "hostname": _s(example="compute-1"),
            "generated_time": _s(example="2026-01-01T00:00:00Z"),
            "payload": _o(
                {
                    "instance_uuid": _s(fmt="uuid"),
                    "vir_domain_event": _s(),
                    "event": _s(),
                }
            ),
            "source_host_uuid": _s(fmt="uuid"),
        },
        required=["type", "hostname", "generated_time", "payload"],
    )


def props_status() -> Str:  # adjutant
    return _o(
        {
            "service": _s(example="identity"),
            "status": _s(enum=["UP", "DOWN", "UNKNOWN"], example="UP"),
            "state": _s(example="up"),
            "description": _s(),
            "name": _s(example="example"),
        },
        required=["service", "status"],
    )


def props_auth_token() -> Str:
    return _o(
        {
            "auth": _o(
                {
                    "identity": _o(
                        {
                            "methods": _a(_s(example="password")),
                            "password": _o(
                                {
                                    "user": _o(
                                        {
                                            "name": _s(example="admin"),
                                            "domain": _o({"name": _s(example="Default")}, required=["name"]),
                                            "password": _s(example="secret"),
                                            "id": _s(fmt="uuid"),
                                        },
                                        required=["password"],
                                    )
                                }
                            ),
                            "token": _o({"id": _s()}),
                        },
                        required=["methods"],
                    ),
                    "scope": _o(
                        {
                            "project": _o(
                                {
                                    "name": _s(example="admin"),
                                    "domain": _o({"name": _s(example="Default")}),
                                    "id": _s(fmt="uuid"),
                                }
                            ),
                            "domain": _o({"name": _s(example="Default"), "id": _s(fmt="uuid")}),
                            "system": _o({"all": _b(default=True)}),
                        }
                    ),
                },
                required=["identity"],
            )
        },
        required=["auth"],
    )


def props_user() -> Str:
    return _o(
        {
            **_name_desc(),
            "domain_id": _s(fmt="uuid", example="default"),
            "enabled": _b(default=True),
            "password": _s(example="secret"),
            "email": _s(fmt="email"),
            "options": _o({}),
            "default_project_id": _s(fmt="uuid"),
        },
        required=["name"],
    )


def props_project() -> Str:
    return _o(
        {
            **_name_desc(),
            "domain_id": _s(fmt="uuid", example="default"),
            "enabled": _b(default=True),
            "is_domain": _b(default=False),
            "parent_id": _s(fmt="uuid"),
            "tags": _a(_s()),
            "options": _o({}),
        },
        required=["name"],
    )


def props_role() -> Str:
    return _o(
        {
            **_name_desc(),
            "domain_id": _s(fmt="uuid"),
            "options": _o({}),
        },
        required=["name"],
    )


def props_group() -> Str:
    return _o({**_name_desc(), "domain_id": _s(fmt="uuid", example="default")}, required=["name"])


def props_region() -> Str:
    return _o(
        {"id": _s(example="RegionOne"), "description": _s(), "parent_region_id": _s()},
        required=["id"],
    )


def props_service() -> Str:
    return _o(
        {
            **_name_desc(),
            "type": _s(example="compute"),
            "enabled": _b(default=True),
        },
        required=["name", "type"],
    )


def props_endpoint() -> Str:
    return _o(
        {
            "interface": _s(enum=["public", "internal", "admin"], example="public"),
            "region_id": _s(example="RegionOne"),
            "url": _s(fmt="uri", example="http://127.0.0.1:8774/v2.1"),
            "service_id": _s(fmt="uuid"),
            "enabled": _b(default=True),
        },
        required=["interface", "url", "service_id"],
    )


def props_flavor() -> Str:
    return _o(
        {
            "name": _s(example="example"),
            "ram": _i("RAM MiB", example=512),
            "vcpus": _i(example=1),
            "disk": _i("Root disk GiB", example=1),
            "id": _s(example="auto"),
            "OS-FLV-EXT-DATA:ephemeral": _i(example=0),
            "swap": _i(example=0),
            "rxtx_factor": {"type": "number", "example": 1.0},
            "os-flavor-access:is_public": _b(default=True),
        },
        required=["name", "ram", "vcpus", "disk"],
    )


def props_keypair() -> Str:
    return _o(
        {
            "name": _s(example="example"),
            "public_key": _s("SSH public key"),
            "type": _s(enum=["ssh", "x509"], example="ssh"),
            "user_id": _s(fmt="uuid"),
        },
        required=["name"],
    )


def props_aggregate() -> Str:
    return _o(
        {
            "name": _s(example="example"),
            "availability_zone": _s(example="nova"),
            "metadata": _o({}),
        },
        required=["name"],
    )


def props_server_group() -> Str:
    return _o(
        {
            "name": _s(example="example"),
            "policies": _a(_s(enum=["affinity", "anti-affinity", "soft-affinity", "soft-anti-affinity"])),
            "policy": _s(enum=["affinity", "anti-affinity", "soft-affinity", "soft-anti-affinity"]),
            "rules": _o({"max_server_per_host": _i(example=1)}),
        },
        required=["name"],
    )


def props_quota_set() -> Str:
    return _o(
        {
            "instances": _i(example=10),
            "cores": _i(example=20),
            "ram": _i(example=51200),
            "floating_ips": _i(example=10),
            "fixed_ips": _i(example=-1),
            "metadata_items": _i(example=128),
            "injected_files": _i(example=5),
            "injected_file_content_bytes": _i(example=10240),
            "security_groups": _i(example=10),
            "security_group_rules": _i(example=20),
            "key_pairs": _i(example=100),
            "volumes": _i(example=10),
            "snapshots": _i(example=10),
            "gigabytes": _i(example=1000),
            "networks": _i(example=100),
            "subnets": _i(example=100),
            "ports": _i(example=500),
            "routers": _i(example=10),
            "force": _b(default=False),
        }
    )


def props_allocation() -> Str:  # placement
    return _o(
        {
            "allocations": _o(
                {},
                description="Map of resource provider UUID to resources",
            ),
            "project_id": _s(fmt="uuid"),
            "user_id": _s(fmt="uuid"),
            "consumer_generation": _i("Consumer generation", example=0),
        },
        required=["allocations", "project_id", "user_id"],
    )


def props_resource_provider() -> Str:
    return _o(
        {
            "name": _s(example="example"),
            "uuid": _s(fmt="uuid"),
            "parent_provider_uuid": _s(fmt="uuid"),
        },
        required=["name"],
    )


def props_inventory() -> Str:
    return _o(
        {
            "resource_class": _s(example="VCPU"),
            "total": _i(example=8),
            "reserved": _i(example=0),
            "min_unit": _i(example=1),
            "max_unit": _i(example=8),
            "step_size": _i(example=1),
            "allocation_ratio": {"type": "number", "example": 16.0},
        },
        required=["resource_class", "total"],
    )


def props_trait() -> Str:
    return _o({"name": _s(example="CUSTOM_EXAMPLE"), "traits": _a(_s())}, required=["name"])


def props_queue() -> Str:  # zaqar
    return _o(
        {
            "queue_name": _s(example="example"),
            "_metadata": _o({}),
        },
        required=["queue_name"],
    )


def props_message() -> Str:
    return _o(
        {
            "messages": _a(
                _o(
                    {
                        "body": _o({"event": _s(example="example")}),
                        "ttl": _i(example=3600),
                    },
                    required=["body"],
                )
            )
        },
        required=["messages"],
    )


def props_subscription() -> Str:
    return _o(
        {
            "subscriber": _s(fmt="uri", example="http://example.com/hook"),
            "ttl": _i(example=3600),
            "options": _o({}),
        },
        required=["subscriber"],
    )


def props_job() -> Str:  # freezer
    return _o(
        {
            "description": _s(example="example"),
            "job_actions": _a(
                _o(
                    {
                        "freezer_action": _o(
                            {
                                "action": _s(enum=["backup", "restore"], example="backup"),
                                "mode": _s(example="fs"),
                                "storage": _s(example="swift"),
                                "container": _s(example="freezer_backup"),
                                "path_to_backup": _s(example="/home"),
                            }
                        ),
                        "max_retries": _i(example=3),
                        "max_retries_interval": _i(example=60),
                    }
                )
            ),
            "client_id": _s(example="example-client"),
            "job_schedule": _o(
                {
                    "schedule_start_date": _s(),
                    "schedule_interval": _s(example="1 day"),
                    "status": _s(example="scheduled"),
                }
            ),
        },
        required=["job_actions", "client_id"],
    )


def props_backup() -> Str:
    return _o(
        {
            **_name_desc(),
            "volume_id": _s(fmt="uuid"),
            "container": _s(),
            "force": _b(default=False),
            "incremental": _b(default=False),
            "snapshot_id": _s(fmt="uuid"),
            "metadata": _o({}),
        },
        required=["volume_id"],
    )


def props_trunk() -> Str:
    return _o(
        {
            **_name_desc(),
            "port_id": _s(fmt="uuid"),
            "admin_state_up": _b(default=True),
            "sub_ports": _a(
                _o(
                    {
                        "port_id": _s(fmt="uuid"),
                        "segmentation_type": _s(example="vlan"),
                        "segmentation_id": _i(example=100),
                    },
                    required=["port_id", "segmentation_type", "segmentation_id"],
                )
            ),
        },
        required=["port_id"],
    )


def props_qos_policy() -> Str:
    return _o({**_name_desc(), "shared": _b(default=False), "is_default": _b(default=False)}, required=["name"])


def props_rbac_policy() -> Str:
    return _o(
        {
            "object_type": _s(example="network"),
            "object_id": _s(fmt="uuid"),
            "target_tenant": _s(fmt="uuid"),
            "action": _s(enum=["access_as_shared", "access_as_external"], example="access_as_shared"),
        },
        required=["object_type", "object_id", "target_tenant", "action"],
    )


def props_metering_label() -> Str:
    return _o({**_name_desc(), "shared": _b(default=False)}, required=["name"])


def props_firewall_group() -> Str:
    return _o(
        {
            **_name_desc(),
            "ingress_firewall_policy_id": _s(fmt="uuid"),
            "egress_firewall_policy_id": _s(fmt="uuid"),
            "ports": _a(_s(fmt="uuid")),
            "admin_state_up": _b(default=True),
            "shared": _b(default=False),
        },
        required=["name"],
    )


def props_l7policy() -> Str:
    return _o(
        {
            **_name_desc(),
            "listener_id": _s(fmt="uuid"),
            "action": _s(
                enum=["REJECT", "REDIRECT_TO_URL", "REDIRECT_TO_POOL", "REDIRECT_PREFIX"],
                example="REJECT",
            ),
            "redirect_pool_id": _s(fmt="uuid"),
            "redirect_url": _s(fmt="uri"),
            "position": _i(example=1),
            "admin_state_up": _b(default=True),
        },
        required=["listener_id", "action"],
    )


def props_healthmonitor() -> Str:
    return _o(
        {
            **_name_desc(),
            "type": _s(enum=["HTTP", "HTTPS", "PING", "TCP", "TLS-HELLO", "UDP-CONNECT"], example="HTTP"),
            "delay": _i(example=5),
            "timeout": _i(example=3),
            "max_retries": _i(example=3),
            "pool_id": _s(fmt="uuid"),
            "http_method": _s(example="GET"),
            "url_path": _s(example="/"),
            "expected_codes": _s(example="200"),
            "admin_state_up": _b(default=True),
        },
        required=["type", "delay", "timeout", "max_retries", "pool_id"],
    )


def props_generic(resource_type: str) -> Str:
    """Fallback full-ish object for lesser-known resources."""

    return _o(
        {
            **_name_desc(),
            "id": _s(fmt="uuid"),
            "project_id": _s(fmt="uuid"),
            "tenant_id": _s(fmt="uuid"),
            "status": _s(example="ACTIVE"),
            "enabled": _b(default=True),
            "shared": _b(default=False),
            "admin_state_up": _b(default=True),
            "metadata": _o({}),
            "tags": _a(_s()),
            "type": _s(example=resource_type),
            "configuration": _o({}),
            "properties": _o({}),
            "spec": _o({}),
            "data": _o({}),
            "value": _s(),
            "size": _i(example=1),
            "version": _s(example="1"),
            "url": _s(fmt="uri"),
            "address": _s(),
            "protocol": _s(),
            "port": _i(example=80),
            "extra": _o({}),
        },
        required=["name"],
    )


_RESOURCE_PROPS: dict[str, Any] = {
    "server": props_server,
    "network": props_network,
    "subnet": props_subnet,
    "port": props_port,
    "router": props_router,
    "floatingip": props_floatingip,
    "security_group": props_security_group,
    "security_group_rule": props_security_group_rule,
    "volume": props_volume,
    "snapshot": props_snapshot,
    "backup": props_backup,
    "image": props_image,
    "vim": props_vim,
    "stack": props_stack,
    "secret": props_secret,
    "alarm": props_alarm,
    "zone": props_zone,
    "recordset": props_recordset,
    "loadbalancer": props_loadbalancer,
    "listener": props_listener,
    "pool": props_pool,
    "member": props_member,
    "cluster": props_cluster,
    "cluster_template": props_cluster_template,
    "share": props_share,
    "instance": props_instance,
    "container": props_container,
    "node": props_node,
    "workflow": props_workflow,
    "execution": props_execution,
    "host": props_host,
    "lease": props_lease,
    "segment": props_segment,
    "notification": props_notification,
    "status": props_status,
    "user": props_user,
    "project": props_project,
    "role": props_role,
    "group": props_group,
    "region": props_region,
    "service": props_service,
    "endpoint": props_endpoint,
    "flavor": props_flavor,
    "keypair": props_keypair,
    "aggregate": props_aggregate,
    "server_group": props_server_group,
    "quota_set": props_quota_set,
    "quota": props_quota_set,
    "allocation": props_allocation,
    "resource_provider": props_resource_provider,
    "inventory": props_inventory,
    "trait": props_trait,
    "queue": props_queue,
    "message": props_message,
    "subscription": props_subscription,
    "job": props_job,
    "trunk": props_trunk,
    "qos_policy": props_qos_policy,
    "rbac_policy": props_rbac_policy,
    "metering_label": props_metering_label,
    "firewall_group": props_firewall_group,
    "l7policy": props_l7policy,
    "healthmonitor": props_healthmonitor,
    "volume_type": lambda: _o({**_name_desc(), "extra_specs": _o({}), "os-volume-type-access:is_public": _b(default=True)}, required=["name"]),
    "consistencygroup": lambda: _o({**_name_desc(), "volume_types": _a(_s())}, required=["name", "volume_types"]),
    "attachment": lambda: _o({"instance_uuid": _s(fmt="uuid"), "volume_uuid": _s(fmt="uuid"), "mode": _s(example="rw")}, required=["instance_uuid", "volume_uuid"]),
    "share_network": lambda: _o({**_name_desc(), "neutron_net_id": _s(fmt="uuid"), "neutron_subnet_id": _s(fmt="uuid")}, required=["name"]),
    "share_type": lambda: _o({**_name_desc(), "extra_specs": _o({"driver_handles_share_servers": _b(default=False)}), "is_public": _b(default=True)}, required=["name", "extra_specs"]),
    "template": lambda: props_stack(),
    "vnf": lambda: _o({**_name_desc(), "vnfd_id": _s(fmt="uuid"), "vim_id": _s(fmt="uuid")}, required=["name", "vnfd_id"]),
    "vnfd": lambda: _o({**_name_desc(), "attributes": _o({"vnfd": _s()}), "service_types": _a(_o({"service_type": _s(example="vnfd")}))}, required=["name"]),
    "ns": lambda: _o({**_name_desc(), "nsd_id": _s(fmt="uuid"), "vim_id": _s(fmt="uuid")}, required=["name", "nsd_id"]),
    "nsd": lambda: _o({**_name_desc(), "attributes": _o({"nsd": _s()})}, required=["name"]),
    "action": lambda: _o({"action": _s(example="os-start"), "name": _s()}, required=["action"]),
    "rating_module": lambda: _o({**_name_desc(), "enabled": _b(default=True), "priority": _i(example=1)}, required=["name"]),
    "hashmap_service": lambda: _o({**_name_desc()}, required=["name"]),
    "collector": lambda: _o({**_name_desc(), "url": _s(fmt="uri")}, required=["name", "url"]),
    "template_definition": lambda: _o({**_name_desc(), "template": _s(), "type": _s()}, required=["name", "template"]),
    "webhook": lambda: _o({**_name_desc(), "url": _s(fmt="uri"), "headers": _o({})}, required=["name", "url"]),
    "topology": lambda: _o({**_name_desc(), "graph": _o({})}, required=["name"]),
    "template_version": lambda: _o({"id": _s(example="2021-04-16"), "type": _s(example="heat")}, required=["id"]),
}


def inner_for_resource(resource_type: str) -> Str:
    factory = _RESOURCE_PROPS.get(resource_type)
    if factory is None:
        # Try singular of resource_type
        factory = _RESOURCE_PROPS.get(singular(resource_type))
    if factory is None:
        return props_generic(resource_type)
    return deepcopy(factory() if callable(factory) else factory)


def action_schema(action_name: str | None) -> Str:
    action = action_name if action_name and action_name != "*" else "os-start"
    bodies: dict[str, Str] = {
        "os-getConsoleOutput": _o({action: _o({"length": _i(example=20)})}, required=[action]),
        "reboot": _o({action: _o({"type": _s(enum=["SOFT", "HARD"], example="SOFT")}, required=["type"])}, required=[action]),
        "resize": _o({action: _o({"flavorRef": _s(example="2")}, required=["flavorRef"])}, required=[action]),
        "rebuild": _o(
            {action: _o({"imageRef": _s(fmt="uuid"), "name": _s(), "adminPass": _s()}, required=["imageRef"])},
            required=[action],
        ),
        "createImage": _o({action: _o({"name": _s(example="example"), "metadata": _o({})}, required=["name"])}, required=[action]),
    }
    if action in bodies:
        return bodies[action]
    return _o({action: {"type": "null", "description": f"Action {action} body (null object)"}}, required=[action])


def schema_for_operation(op: dict[str, Any]) -> Str:
    """Build a full request JSON Schema for one pack operation dict."""

    method = op["method"]
    kind = op.get("kind") or "collection"
    path = op.get("path") or ""
    resource_type = op.get("resource_type") or "object"
    item_key = op.get("item_key") or (
        singular(op["collection_key"]) if op.get("collection_key") else singular(resource_type)
    )

    if path == "/v3/auth/tokens" and method == "POST":
        return props_auth_token()

    if kind == "action":
        return action_schema(op.get("action_name"))

    if "add_router_interface" in path or "remove_router_interface" in path:
        return _o(
            {
                "subnet_id": _s(fmt="uuid"),
                "port_id": _s(fmt="uuid"),
            }
        )

    if path.rstrip("/").endswith("/os-interface") and method == "POST":
        return _envelope(
            "interfaceAttachment",
            _o(
                {
                    "port_id": _s(fmt="uuid"),
                    "net_id": _s(fmt="uuid"),
                    "fixed_ips": _a(_o({"ip_address": _s()})),
                }
            ),
        )

    if resource_type == "server_tag" and path.rstrip("/").endswith("/tags"):
        return _o({"tags": _a(_s(example="demo"))}, required=["tags"])

    if op.get("collection_key") == "Stacks":
        return _o(
            {
                "StackName": _s(example="example"),
                "TemplateBody": _s(example='{"AWSTemplateFormatVersion":"2010-09-09"}'),
                "Parameters": _s(),
                "TimeoutInMinutes": _i(example=60),
            },
            required=["StackName", "TemplateBody"],
        )

    # Heat stack create uses top-level keys sometimes without envelope in CFN;
    # OpenStack native uses stack envelope.
    if resource_type == "stack" and method == "POST" and "/stacks" in path:
        return _envelope("stack", inner_for_resource("stack"))

    # Queue create in Zaqar often uses path name; still document metadata body.
    if resource_type in {"queue"} and method == "PUT":
        return _o({"_metadata": _o({})})

    # Empty body endpoints (some PUT enable/disable) — still expose optional object.
    if kind == "custom" and method in {"POST", "PUT", "PATCH"}:
        inner = inner_for_resource(resource_type)
        if item_key:
            return _envelope(item_key, inner, required_inner=False)
        return inner

    inner = inner_for_resource(resource_type)
    # PATCH/PUT item updates: same fields but nothing strictly required except identity in path.
    if kind == "item" and method in {"PUT", "PATCH"}:
        relaxed = deepcopy(inner)
        relaxed.pop("required", None)
        return _envelope(item_key, relaxed)

    return _envelope(item_key, inner)
