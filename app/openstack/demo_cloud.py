"""Sized OpenStack demo cloud seed (small / large / big synthetic clusters)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any
from uuid import UUID

from asyncpg import Connection

from app.openstack.ids import oid
from app.security.auth import hash_secret

DEMO_PROFILE = "openstack-demo-cloud"
DEMO_SIZE_DEFAULT = "large"


@dataclass(frozen=True, slots=True)
class DemoClusterSize:
    """Proportional inventory for a demo cluster size button."""

    name: str
    hypervisors: int
    servers: int
    volumes: int
    ironic_nodes: int
    loadbalancers: int
    stacks: int
    floating_ips: int
    surface_samples: int
    server_groups: int
    nested_samples: int
    pack_per_type: int
    extra_networks: int
    extra_security_groups: int
    keypairs_per_user: int
    edge_routers: int


def _scale(base: int, factor: float, minimum: int) -> int:
    return max(minimum, int(round(base * factor)))


def _cluster(name: str, *, hypervisors: int, servers: int) -> DemoClusterSize:
    """Derive secondary counts from the large (1000 VM) reference ratios."""

    factor = servers / 1000
    return DemoClusterSize(
        name=name,
        hypervisors=hypervisors,
        servers=servers,
        volumes=_scale(600, factor, 20),
        ironic_nodes=_scale(24, factor, 2),
        loadbalancers=_scale(12, factor, 2),
        stacks=_scale(30, factor, 3),
        floating_ips=_scale(120, factor, 6),
        surface_samples=_scale(8, factor, 3),
        server_groups=_scale(16, factor, 3),
        nested_samples=_scale(24, factor, 8),
        pack_per_type=_scale(3, factor, 2),
        # Topology density (large reference: 3 extra nets, 3 SG tiers, 4 keys, 1 edge router).
        extra_networks=_scale(3, factor, 1),
        extra_security_groups=_scale(3, factor, 1),
        keypairs_per_user=_scale(4, factor, 2),
        edge_routers=_scale(1, factor, 0),
    )


DEMO_CLUSTER_SIZES: dict[str, DemoClusterSize] = {
    "small": _cluster("small", hypervisors=3, servers=50),
    "large": _cluster("large", hypervisors=10, servers=1000),
    "big": _cluster("big", hypervisors=20, servers=2000),
}


def resolve_demo_size(size: str | None) -> DemoClusterSize:
    key = (size or DEMO_SIZE_DEFAULT).strip().lower()
    aliases = {
        "demo": "large",
        "demo-cloud": "large",
        "openstack-demo-cloud": "large",
        "demo-small": "small",
        "demo-large": "large",
        "demo-big": "big",
        "medium": "large",
    }
    key = aliases.get(key, key)
    if key not in DEMO_CLUSTER_SIZES:
        known = ", ".join(sorted(DEMO_CLUSTER_SIZES))
        raise ValueError(f"unknown demo size {size!r} (use {known})")
    return DEMO_CLUSTER_SIZES[key]


def demo_profile_name(size: str | DemoClusterSize) -> str:
    name = size.name if isinstance(size, DemoClusterSize) else resolve_demo_size(size).name
    return f"{DEMO_PROFILE}:{name}"


def is_demo_profile(profile: str | None) -> bool:
    if not profile:
        return False
    return profile == DEMO_PROFILE or profile.startswith(f"{DEMO_PROFILE}:")


def list_demo_sizes() -> list[dict[str, Any]]:
    return [asdict(cfg) for cfg in DEMO_CLUSTER_SIZES.values()]


# Backward-compatible aliases → large cluster (default demo).
DEMO_SERVER_COUNT = DEMO_CLUSTER_SIZES["large"].servers
DEMO_VOLUME_COUNT = DEMO_CLUSTER_SIZES["large"].volumes
DEMO_HYPERVISOR_COUNT = DEMO_CLUSTER_SIZES["large"].hypervisors
DEMO_IRONIC_COUNT = DEMO_CLUSTER_SIZES["large"].ironic_nodes
DEMO_LB_COUNT = DEMO_CLUSTER_SIZES["large"].loadbalancers
DEMO_STACK_COUNT = DEMO_CLUSTER_SIZES["large"].stacks
DEMO_FIP_COUNT = DEMO_CLUSTER_SIZES["large"].floating_ips

AZS = ("az-1", "az-2", "az-3")

PROJECTS = (
    ("admin", "Admin project"),
    ("demo", "Demo project"),
    ("production", "Production workloads"),
    ("staging", "Staging workloads"),
    ("development", "Development workloads"),
)

USERS = (
    ("admin", "admin"),
    ("demo", "member"),
    ("ops", "admin"),
    ("developer", "member"),
    ("auditor", "member"),
)

PREFIXES = (
    "web",
    "api",
    "db",
    "cache",
    "worker",
    "batch",
    "gpu",
    "ml",
    "ci",
    "jump",
)


def _server_name(index: int) -> str:
    return f"{PREFIXES[index % len(PREFIXES)]}-{index:04d}"


def _status(index: int) -> str:
    # Mostly ACTIVE for realistic inventory.
    cycle = ("ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "ACTIVE", "SHUTOFF", "ACTIVE", "ERROR")
    return cycle[index % len(cycle)]


async def clear_openstack_state(conn: Connection) -> None:
    """Wipe all OpenStack lab tables (FK-safe truncate)."""

    await conn.execute(
        """
        TRUNCATE TABLE
            os_tokens,
            os_role_assignments,
            os_security_group_rules,
            os_security_groups,
            os_floating_ips,
            os_ports,
            os_subnets,
            os_networks,
            os_routers,
            os_server_groups,
            os_servers,
            os_volumes,
            os_images,
            os_flavors,
            os_keypairs,
            os_stacks,
            os_swift_objects,
            os_swift_containers,
            os_nodes,
            os_loadbalancers,
            os_api_objects,
            os_compute_services,
            os_aggregates,
            os_hypervisors,
            os_availability_zones,
            os_demo_meta,
            os_users,
            os_roles,
            os_projects,
            os_domains
        RESTART IDENTITY CASCADE
        """
    )


async def seed_openstack_demo(
    conn: Connection,
    *,
    size: str = DEMO_SIZE_DEFAULT,
    password: str = "secret",
) -> dict[str, Any]:
    """Load a full synthetic OpenStack cloud. Replaces prior OpenStack state."""

    cfg = resolve_demo_size(size)
    server_count = cfg.servers
    volume_count = cfg.volumes
    hypervisor_count = cfg.hypervisors
    ironic_count = cfg.ironic_nodes
    lb_count = cfg.loadbalancers
    stack_count = cfg.stacks
    fip_count = cfg.floating_ips
    surface_sample_count = cfg.surface_samples
    server_group_count = cfg.server_groups
    nested_sample_count = cfg.nested_samples
    pack_per_type = cfg.pack_per_type
    extra_networks = cfg.extra_networks
    extra_security_groups = cfg.extra_security_groups
    keypairs_per_user = cfg.keypairs_per_user
    edge_routers = cfg.edge_routers
    profile = demo_profile_name(cfg)

    await clear_openstack_state(conn)
    pw = hash_secret(password, salt=b"openstack-sim-v1")

    domain_id = oid("domain:Default")
    await conn.execute(
        """INSERT INTO os_domains(id, name, description, enabled)
           VALUES($1, 'Default', 'Default domain', true)""",
        domain_id,
    )

    role_admin = oid("role:admin")
    role_member = oid("role:member")
    await conn.execute(
        """INSERT INTO os_roles(id, name) VALUES ($1, 'admin'), ($2, 'member')""",
        role_admin,
        role_member,
    )

    project_ids: dict[str, UUID] = {}
    for name, desc in PROJECTS:
        pid = oid(f"project:{name}")
        project_ids[name] = pid
        await conn.execute(
            """INSERT INTO os_projects(id, domain_id, name, description, enabled)
               VALUES($1,$2,$3,$4,true)""",
            pid,
            domain_id,
            name,
            desc,
        )

    user_ids: dict[str, UUID] = {}
    for uname, _role in USERS:
        uid = oid(f"user:{uname}")
        user_ids[uname] = uid
        await conn.execute(
            """INSERT INTO os_users(id, domain_id, name, password_hash, enabled)
               VALUES($1,$2,$3,$4,true)""",
            uid,
            domain_id,
            uname,
            pw,
        )

    # Role assignments
    assignments = [
        ("admin", "admin", role_admin),
        ("admin", "demo", role_admin),
        ("admin", "production", role_admin),
        ("admin", "staging", role_admin),
        ("admin", "development", role_admin),
        ("demo", "demo", role_member),
        ("ops", "production", role_admin),
        ("ops", "staging", role_admin),
        ("developer", "development", role_member),
        ("developer", "staging", role_member),
        ("auditor", "production", role_member),
        ("auditor", "demo", role_member),
    ]
    for i, (uname, pname, rid) in enumerate(assignments):
        await conn.execute(
            """INSERT INTO os_role_assignments(id, role_id, user_id, project_id)
               VALUES($1,$2,$3,$4)
               ON CONFLICT (role_id, user_id, project_id) DO NOTHING""",
            oid(f"assign:{uname}:{pname}:{i}"),
            rid,
            user_ids[uname],
            project_ids[pname],
        )

    # AZs + hypervisors + services + aggregates
    for az in AZS:
        await conn.execute(
            "INSERT INTO os_availability_zones(name, zone_state) VALUES($1, $2::jsonb)",
            az,
            '{"available": true}',
        )

    for i in range(hypervisor_count):
        host = f"compute-{(i // len(AZS)) + 1:02d}.{AZS[i % len(AZS)]}"
        az = AZS[i % len(AZS)]
        vms_share = max(1, server_count // hypervisor_count)
        await conn.execute(
            """INSERT INTO os_hypervisors(
                   id, hypervisor_hostname, state, status, host_ip, vcpus, vcpus_used,
                   memory_mb, memory_mb_used, local_gb, local_gb_used, running_vms,
                   service_host, availability_zone)
               VALUES($1,$2,'up','enabled',$3,96,$4,524288,$5,4000,$6,$7,$2,$8)""",
            i + 1,
            host,
            f"10.20.{i // 16}.{(i % 16) + 10}",
            min(96, vms_share * 2),
            min(400_000, vms_share * 4096),
            min(3000, vms_share * 40),
            vms_share,
            az,
        )
        await conn.execute(
            """INSERT INTO os_compute_services("binary", host, zone, status, state)
               VALUES('nova-compute',$1,$2,'enabled','up')""",
            host,
            az,
        )

    for az in AZS:
        await conn.execute(
            """INSERT INTO os_compute_services("binary", host, zone, status, state)
               VALUES('nova-scheduler',$1,$2,'enabled','up'),
                      ('nova-conductor',$1,$2,'enabled','up')""",
            f"controller-{az}",
            az,
        )

    for i, az in enumerate(AZS):
        hosts = [
            f"compute-{(j // len(AZS)) + 1:02d}.{az}"
            for j in range(i, hypervisor_count, len(AZS))
        ]
        await conn.execute(
            """INSERT INTO os_aggregates(id, name, availability_zone, hosts, metadata)
               VALUES($1,$2,$3,$4::jsonb,'{"pinned":"false"}'::jsonb)""",
            i + 1,
            f"agg-{az}",
            az,
            json.dumps(hosts),
        )

    # Flavors + images
    flavors = [
        ("1", "m1.tiny", 1, 512, 1),
        ("2", "m1.small", 1, 2048, 20),
        ("3", "m1.medium", 2, 4096, 40),
        ("4", "m1.large", 4, 8192, 80),
        ("5", "m1.xlarge", 8, 16384, 160),
        ("6", "g1.gpu", 8, 32768, 200),
        ("7", "c1.highcpu", 16, 8192, 40),
        ("8", "r1.highmem", 4, 65536, 80),
    ]
    for fid, name, vcpus, ram, disk in flavors:
        await conn.execute(
            """INSERT INTO os_flavors(id, name, vcpus, ram, disk, is_public)
               VALUES($1,$2,$3,$4,$5,true)""",
            fid,
            name,
            vcpus,
            ram,
            disk,
        )

    images = [
        ("image:cirros", "cirros", 13_287_936),
        ("image:cirros-full", "cirros-0.6.2-x86_64", 13_287_936),
        ("image:ubuntu2204", "ubuntu-22.04", 400_000_000),
        ("image:ubuntu2404", "ubuntu-24.04", 420_000_000),
        ("image:centos9", "centos-stream-9", 380_000_000),
        ("image:debian12", "debian-12", 350_000_000),
        ("image:rocky9", "rocky-9", 390_000_000),
    ]
    image_ids: list[UUID] = []
    for key, name, size in images:
        iid = oid(key)
        image_ids.append(iid)
        await conn.execute(
            """INSERT INTO os_images(id, name, status, visibility, size, disk_format,
                   container_format, owner_project_id)
               VALUES($1,$2,'active','public',$3,'qcow2','bare',$4)""",
            iid,
            name,
            size,
            project_ids["admin"],
        )

    # Networks per project + shared public
    public_net = oid("net:public")
    await conn.execute(
        """INSERT INTO os_networks(id, project_id, name, status, shared, admin_state_up)
           VALUES($1,$2,'public','ACTIVE',true,true)""",
        public_net,
        project_ids["admin"],
    )
    public_subnet = oid("subnet:public")
    await conn.execute(
        """INSERT INTO os_subnets(id, network_id, project_id, name, cidr, ip_version, gateway_ip)
           VALUES($1,$2,$3,'public-subnet','203.0.113.0/24',4,'203.0.113.1')""",
        public_subnet,
        public_net,
        project_ids["admin"],
    )

    project_nets: dict[str, tuple[UUID, UUID]] = {}
    cidr_base = {
        "demo": 10,
        "production": 20,
        "staging": 30,
        "development": 40,
        "admin": 50,
    }
    for pname, pid in project_ids.items():
        base = cidr_base[pname]
        net_id = oid(f"net:{pname}-private")
        subnet_id = oid(f"subnet:{pname}-private")
        project_nets[pname] = (net_id, subnet_id)
        await conn.execute(
            """INSERT INTO os_networks(id, project_id, name, status, shared, admin_state_up)
               VALUES($1,$2,$3,'ACTIVE',false,true)""",
            net_id,
            pid,
            f"{pname}-net",
        )
        await conn.execute(
            """INSERT INTO os_subnets(id, network_id, project_id, name, cidr, ip_version, gateway_ip)
               VALUES($1,$2,$3,$4,$5,4,$6)""",
            subnet_id,
            net_id,
            pid,
            f"{pname}-subnet",
            f"10.{base}.0.0/16",
            f"10.{base}.0.1",
        )
        # Router + external gateway
        router_id = oid(f"router:{pname}")
        await conn.execute(
            """INSERT INTO os_routers(id, project_id, name, status, admin_state_up, external_gateway_info)
               VALUES($1,$2,$3,'ACTIVE',true,$4::jsonb)""",
            router_id,
            pid,
            f"{pname}-router",
            json.dumps(
                {
                    "network_id": str(public_net),
                    "enable_snat": True,
                    "external_fixed_ips": [
                        {"ip_address": f"203.0.113.{base}", "subnet_id": str(public_subnet)}
                    ],
                }
            ),
        )
        # Default SG
        sg_id = oid(f"sg:{pname}-default")
        await conn.execute(
            """INSERT INTO os_security_groups(id, project_id, name, description)
               VALUES($1,$2,'default',$3)""",
            sg_id,
            pid,
            f"Default security group for {pname}",
        )
        for j, (direction, proto, pmin, pmax, prefix) in enumerate(
            (
                ("egress", None, None, None, None),
                ("ingress", "tcp", 22, 22, "0.0.0.0/0"),
                ("ingress", "tcp", 80, 80, "0.0.0.0/0"),
                ("ingress", "tcp", 443, 443, "0.0.0.0/0"),
                ("ingress", "icmp", None, None, "0.0.0.0/0"),
            )
        ):
            await conn.execute(
                """INSERT INTO os_security_group_rules(
                       id, security_group_id, project_id, direction, ethertype, protocol,
                       port_range_min, port_range_max, remote_ip_prefix)
                   VALUES($1,$2,$3,$4,'IPv4',$5,$6,$7,$8)""",
                oid(f"sgrule:{pname}:{j}"),
                sg_id,
                pid,
                direction,
                proto,
                pmin,
                pmax,
                prefix,
            )

    # Extra project topology — density scales with cluster size.
    extra_net_suffixes = ("mgmt", "storage", "dmz", "backup", "ci", "gpu")
    sg_tiers = (
        ("web", "HTTP/S", 443),
        ("db", "Database tier", 5432),
        ("cache", "Cache tier", 6379),
        ("mq", "Message bus", 5672),
        ("internal", "Internal RPC", 9696),
        ("monitoring", "Metrics / scrape", 9100),
    )
    for pname, pid in project_ids.items():
        base = cidr_base[pname]
        for extra_i, suffix in enumerate(extra_net_suffixes[:extra_networks], start=1):
            net_id = oid(f"net:{pname}-{suffix}")
            subnet_id = oid(f"subnet:{pname}-{suffix}")
            await conn.execute(
                """INSERT INTO os_networks(id, project_id, name, status, shared, admin_state_up)
                   VALUES($1,$2,$3,'ACTIVE',false,true)""",
                net_id,
                pid,
                f"{pname}-{suffix}",
            )
            await conn.execute(
                """INSERT INTO os_subnets(id, network_id, project_id, name, cidr, ip_version, gateway_ip)
                   VALUES($1,$2,$3,$4,$5,4,$6)""",
                subnet_id,
                net_id,
                pid,
                f"{pname}-{suffix}-subnet",
                f"10.{base}.{extra_i * 10}.0/24",
                f"10.{base}.{extra_i * 10}.1",
            )
        for sg_name, desc_prefix, port in sg_tiers[:extra_security_groups]:
            sg_id = oid(f"sg:{pname}-{sg_name}")
            await conn.execute(
                """INSERT INTO os_security_groups(id, project_id, name, description)
                   VALUES($1,$2,$3,$4)""",
                sg_id,
                pid,
                sg_name,
                f"{desc_prefix} for {pname}",
            )
            await conn.execute(
                """INSERT INTO os_security_group_rules(
                       id, security_group_id, project_id, direction, ethertype, protocol,
                       port_range_min, port_range_max, remote_ip_prefix)
                   VALUES($1,$2,$3,'ingress','IPv4','tcp',$4,$5,'0.0.0.0/0')""",
                oid(f"sgrule:{pname}:{sg_name}"),
                sg_id,
                pid,
                port,
                port,
            )
        # Secondary edge routers (0 on tiny clusters, more on big).
        for edge_i in range(edge_routers):
            await conn.execute(
                """INSERT INTO os_routers(id, project_id, name, status, admin_state_up, external_gateway_info)
                   VALUES($1,$2,$3,'ACTIVE',true,$4::jsonb)""",
                oid(f"router:{pname}-edge-{edge_i}"),
                pid,
                f"{pname}-edge-router-{edge_i}" if edge_routers > 1 else f"{pname}-edge-router",
                json.dumps(
                    {
                        "network_id": str(public_net),
                        "enable_snat": True,
                        "external_fixed_ips": [
                            {
                                "ip_address": f"203.0.113.{base + 1 + edge_i}",
                                "subnet_id": str(public_subnet),
                            }
                        ],
                    }
                ),
            )

    # Keypairs (several per user — list is user-scoped; count scales with size)
    keypair_suffixes = ("key", "deploy", "ci", "bastion", "ops", "batch", "gpu", "lab")
    for uname, uid in user_ids.items():
        for suffix in keypair_suffixes[:keypairs_per_user]:
            await conn.execute(
                """INSERT INTO os_keypairs(name, user_id, fingerprint, public_key, type)
                   VALUES($1,$2,$3,$4,'ssh')""",
                f"{uname}-{suffix}",
                uid,
                f"https://example.invalid/{uname}-{suffix}",
                f"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC {uname}@{suffix}",
            )

    # Distribute servers across all lab projects (incl. admin — tokens often use admin)
    tenant_cycle = ("admin", "demo", "production", "staging", "development", "demo")
    hypervisor_names = [
        f"compute-{(i // len(AZS)) + 1:02d}.{AZS[i % len(AZS)]}"
        for i in range(hypervisor_count)
    ]

    server_rows = []
    port_rows = []
    for i in range(server_count):
        pname = tenant_cycle[i % len(tenant_cycle)]
        pid = project_ids[pname]
        net_id, _subnet = project_nets[pname]
        az = AZS[i % len(AZS)]
        host = hypervisor_names[i % len(hypervisor_names)]
        flavor = str((i % 8) + 1)
        image = image_ids[i % len(image_ids)]
        sid = oid(f"server:demo:{i}")
        status = _status(i)
        base = cidr_base[pname]
        ip = f"10.{base}.{(i // 254) + 1}.{(i % 254) + 2}"
        mac = f"fa:16:3e:{(i >> 16) & 0xFF:02x}:{(i >> 8) & 0xFF:02x}:{i & 0xFF:02x}"
        addresses = {
            f"{pname}-net": [
                {
                    "OS-EXT-IPS-MAC:mac_addr": mac,
                    "version": 4,
                    "addr": ip,
                    "OS-EXT-IPS:type": "fixed",
                }
            ]
        }
        owner = (
            user_ids["ops"]
            if pname in {"production", "staging"}
            else user_ids.get("developer") or user_ids["demo"]
        )
        if pname == "demo":
            owner = user_ids["demo"]
        if pname == "admin":
            owner = user_ids["admin"]
        server_rows.append(
            (
                sid,
                pid,
                owner,
                _server_name(i),
                status,
                flavor,
                image,
                json.dumps(addresses),
                json.dumps(
                    {
                        "env": pname,
                        "index": i,
                        "_tags": [pname, az, PREFIXES[i % len(PREFIXES)], f"idx-{i}"],
                    }
                ),
                az,
                host,
            )
        )
        port_id = oid(f"port:demo:{i}")
        port_rows.append(
            (
                port_id,
                net_id,
                pid,
                f"port-{_server_name(i)}",
                "ACTIVE",
                mac,
                str(sid),
                "compute:nova",
                json.dumps([{"ip_address": ip, "subnet_id": str(project_nets[pname][1])}]),
            )
        )

    await conn.executemany(
        """INSERT INTO os_servers(
               id, project_id, user_id, name, status, flavor_id, image_id,
               addresses, metadata, availability_zone, host)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10,$11)""",
        server_rows,
    )
    await conn.executemany(
        """INSERT INTO os_ports(
               id, network_id, project_id, name, status, mac_address,
               device_id, device_owner, fixed_ips)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb)""",
        port_rows,
    )
    # One create action per server so GET …/os-instance-actions is never empty.
    action_rows = [
        (
            oid(f"nova:instance_action:create:{i}"),
            row[1],  # project_id
            f"create-{i}",
            json.dumps(
                {
                    "action": "create",
                    "instance_uuid": str(row[0]),
                    "server_id": str(row[0]),
                    "request_id": f"req-seed-{str(row[0])[:8]}",
                    "message": None,
                }
            ),
        )
        for i, row in enumerate(server_rows)
    ]
    await conn.executemany(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'nova','instance_action',$2,$3,'DONE',$4::jsonb)""",
        action_rows,
    )

    # Volumes
    volume_rows = []
    for i in range(volume_count):
        pname = tenant_cycle[i % len(tenant_cycle)]
        volume_rows.append(
            (
                oid(f"volume:demo:{i}"),
                project_ids[pname],
                f"vol-{pname}-{i:04d}",
                "in-use" if i < server_count // 2 else "available",
                (i % 5 + 1) * 10,
                "lvmdriver-1" if i % 3 else "ceph",
                i % 11 == 0,
                f"Synthetic volume for {pname}",
            )
        )
    await conn.executemany(
        """INSERT INTO os_volumes(id, project_id, name, status, size, volume_type, bootable, description)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8)""",
        volume_rows,
    )

    # Per-server nested rows so any listed server has DB-backed attachments/allocations.
    attachment_rows = []
    for i in range(server_count):
        pname = tenant_cycle[i % len(tenant_cycle)]
        sid = str(oid(f"server:demo:{i}"))
        vid = str(oid(f"volume:demo:{i % volume_count}"))
        port_id = str(oid(f"port:demo:{i}"))
        pid = project_ids[pname]
        attachment_rows.append(
            (
                oid(f"nova:volume_attachment:all-{i}"),
                "nova",
                "volume_attachment",
                pid,
                f"vattach-all-{i}",
                "ACTIVE",
                json.dumps(
                    {
                        "server_id": sid,
                        "serverId": sid,
                        "volume_id": vid,
                        "volumeId": vid,
                        "device": "/dev/vdb",
                    }
                ),
            )
        )
        attachment_rows.append(
            (
                oid(f"nova:interface_attachment:all-{i}"),
                "nova",
                "interface_attachment",
                pid,
                f"iattach-all-{i}",
                "ACTIVE",
                json.dumps(
                    {"server_id": sid, "port_id": port_id, "net_id": str(project_nets[pname][0])}
                ),
            )
        )
        attachment_rows.append(
            (
                oid(f"placement:allocation:all-{i}"),
                "placement",
                "allocation",
                None,
                f"palloc-all-{i}",
                "ACTIVE",
                json.dumps(
                    {
                        "consumer_uuid": sid,
                        "resource_provider": str(oid(f"placement:resource_provider:rp-{i % 8}")),
                        "resource_provider_id": str(oid(f"placement:resource_provider:rp-{i % 8}")),
                        "resources": {"VCPU": 1, "MEMORY_MB": 1024, "DISK_GB": 10},
                        "consumer_generation": 1,
                    }
                ),
            )
        )
    await conn.executemany(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)""",
        attachment_rows,
    )

    # Floating IPs
    for i in range(fip_count):
        pname = tenant_cycle[i % len(tenant_cycle)]
        await conn.execute(
            """INSERT INTO os_floating_ips(
                   id, project_id, floating_ip_address, floating_network_id, port_id, status)
               VALUES($1,$2,$3,$4,$5,$6)""",
            oid(f"fip:demo:{i}"),
            project_ids[pname],
            f"203.0.113.{(i % 200) + 20}",
            public_net,
            port_rows[i][0] if i < len(port_rows) else None,
            "ACTIVE" if i % 4 else "DOWN",
        )

    # Ironic nodes
    for i in range(ironic_count):
        await conn.execute(
            """INSERT INTO os_nodes(
                   id, name, driver, provision_state, power_state, resource_class,
                   properties, driver_info, ports)
               VALUES($1,$2,'ipmi',$3,$4,'baremetal',$5::jsonb,'{}'::jsonb,'[]'::jsonb)""",
            oid(f"node:demo:{i}"),
            f"baremetal-{i:02d}",
            "active" if i % 5 == 0 else "available",
            "power on" if i % 5 == 0 else "power off",
            json.dumps({"cpus": 64, "memory_mb": 262144, "local_gb": 2000, "az": AZS[i % 3]}),
        )

    # Octavia LBs
    for i in range(lb_count):
        pname = tenant_cycle[i % len(tenant_cycle)]
        await conn.execute(
            """INSERT INTO os_loadbalancers(
                   id, project_id, name, description, vip_address, vip_subnet_id,
                   provisioning_status, operating_status, listeners, pools)
               VALUES($1,$2,$3,$4,$5,$6,'ACTIVE','ONLINE',$7::jsonb,$8::jsonb)""",
            oid(f"lb:demo:{i}"),
            project_ids[pname],
            f"lb-{pname}-{i:02d}",
            f"Synthetic LB for {pname}",
            f"10.{cidr_base[pname]}.200.{i + 1}",
            project_nets[pname][1],
            json.dumps(
                [{"id": str(oid(f"listener:{i}")), "protocol": "HTTP", "protocol_port": 80}]
            ),
            json.dumps(
                [{"id": str(oid(f"pool:{i}")), "lb_algorithm": "ROUND_ROBIN", "protocol": "HTTP"}]
            ),
        )

    # Heat stacks
    for i in range(stack_count):
        pname = tenant_cycle[i % len(tenant_cycle)]
        await conn.execute(
            """INSERT INTO os_stacks(
                   id, project_id, stack_name, stack_status, description, template, parameters, outputs)
               VALUES($1,$2,$3,'CREATE_COMPLETE',$4,$5::jsonb,'{}'::jsonb,'[]'::jsonb)""",
            oid(f"stack:demo:{i}"),
            project_ids[pname],
            f"stack-{pname}-{i:02d}",
            f"Synthetic Heat stack {i}",
            json.dumps({"heat_template_version": "2015-04-30", "resources": {}}),
        )

    # Swift
    for pname, pid in project_ids.items():
        account = f"AUTH_{pid}"
        for cname in ("images", "backups", "artifacts"):
            await conn.execute(
                """INSERT INTO os_swift_containers(account, name, meta)
                   VALUES($1,$2,'{}'::jsonb) ON CONFLICT DO NOTHING""",
                account,
                cname,
            )
            await conn.execute(
                """INSERT INTO os_swift_objects(id, account, container, name, content_type, bytes, body, meta)
                   VALUES($1,$2,$3,$4,'text/plain',$5,$6,'{}'::jsonb)
                   ON CONFLICT DO NOTHING""",
                oid(f"swift:{pname}:{cname}:readme"),
                account,
                cname,
                "readme.txt",
                16,
                f"hello {pname}\n".encode(),
            )

    # Generic service samples (multiple per service) — keep resource_type aligned
    # with pack operation resource_type so schema list endpoints return rows.
    samples = []
    for i in range(surface_sample_count):
        samples.extend(
            [
                ("barbican", "secret", f"secret-{i}", {"secret_type": "passphrase"}),
                (
                    "barbican",
                    "container",
                    f"container-{i}",
                    {"type": "generic", "status": "ACTIVE"},
                ),
                ("barbican", "order", f"order-{i}", {"type": "key", "status": "ACTIVE"}),
                ("barbican", "secret_store", f"store-{i}", {"status": "ACTIVE"}),
                (
                    "manila",
                    "share",
                    f"share-{i}",
                    {"size": 50, "share_proto": "NFS", "status": "available"},
                ),
                (
                    "manila",
                    "share_snapshot",
                    f"share-snap-{i}",
                    {"status": "available", "size": 50},
                ),
                ("manila", "share_network", f"share-net-{i}", {"status": "active"}),
                ("manila", "share_type", f"share-type-{i}", {"is_public": True}),
                ("manila", "share_server", f"share-srv-{i}", {"status": "active"}),
                ("manila", "security_service", f"sec-svc-{i}", {"type": "ldap", "status": "new"}),
                ("manila", "share_group", f"share-grp-{i}", {"status": "available"}),
                ("manila", "share_replica", f"share-rep-{i}", {"status": "available"}),
                ("designate", "zone", f"zone{i}.lab.", {"email": "hostmaster@lab", "ttl": 3600}),
                ("designate", "tld", f"tld-{i}", {"name": f"lab{i}"}),
                ("designate", "blacklist", f"bl-{i}", {"pattern": f"^bad{i}\\..*"}),
                ("designate", "pool", f"pool-{i}", {"name": f"pool-{i}"}),
                ("designate", "service_status", f"dns-svc-{i}", {"status": "UP"}),
                (
                    "magnum",
                    "cluster",
                    f"k8s-{i}",
                    {"coe": "kubernetes", "status": "CREATE_COMPLETE", "node_count": 3},
                ),
                (
                    "magnum",
                    "clustertemplate",
                    f"k8s-tmpl-{i}",
                    {"coe": "kubernetes", "image_id": "cirros"},
                ),
                ("magnum", "certificate", f"cert-{i}", {"cluster_uuid": f"cluster-{i}"}),
                ("zun", "container", f"ctr-{i}", {"image": "nginx", "status": "Running"}),
                (
                    "trove",
                    "instance",
                    f"db-{i}",
                    {"datastore": {"type": "mysql"}, "status": "ACTIVE"},
                ),
                ("mistral", "workflow", f"wf-{i}", {"definition": "version: '2.0'"}),
                ("mistral", "execution", f"exec-{i}", {"state": "SUCCESS"}),
                ("mistral", "action", f"action-{i}", {"is_system": False}),
                ("mistral", "workbook", f"wb-{i}", {"definition": "version: '2.0'"}),
                ("mistral", "cron_trigger", f"cron-{i}", {"pattern": "0 * * * *"}),
                ("mistral", "task", f"task-{i}", {"state": "SUCCESS"}),
                ("aodh", "alarm", f"alarm-{i}", {"type": "threshold", "state": "ok"}),
                ("aodh", "quota", f"aodh-quota-{i}", {"alarm": 100}),
                ("freezer", "job", f"job-{i}", {"status": "scheduled"}),
                ("freezer", "client", f"client-{i}", {"status": "available"}),
                ("freezer", "backup", f"backup-{i}", {"status": "available"}),
                ("freezer", "session", f"session-{i}", {"status": "scheduled"}),
                ("freezer", "action", f"freezer-action-{i}", {"status": "available"}),
                ("blazar", "lease", f"lease-{i}", {"status": "ACTIVE"}),
                ("blazar", "host", f"blazar-host-{i}", {"status": "available"}),
                (
                    "blazar",
                    "floatingip",
                    f"blazar-fip-{i}",
                    {"floating_ip_address": f"198.51.100.{i + 10}"},
                ),
                ("masakari", "segment", f"segment-{i}", {"recovery_method": "auto"}),
                ("masakari", "notification", f"notif-{i}", {"status": "finished"}),
                (
                    "masakari",
                    "host",
                    f"masakari-host-{i}",
                    {
                        "name": f"compute-{(i % 3) + 1}",
                        "type": "compute",
                        "reserved": False,
                        "on_maintenance": False,
                        "segment_id": f"segment-{i % 8}",
                    },
                ),
                ("tacker", "vnf", f"vnf-{i}", {"status": "ACTIVE"}),
                ("adjutant", "task", f"task-{i}", {"status": "open"}),
                ("adjutant", "token", f"token-{i}", {"status": "active"}),
                ("adjutant", "notification", f"adj-notif-{i}", {"status": "sent"}),
                (
                    "adjutant",
                    "status",
                    f"adj-status-{i}",
                    {"status": "UP", "service": "adjutant", "state": "up"},
                ),
                (
                    "designate",
                    "recordset",
                    f"rs-{i}",
                    {
                        "zone_id": f"zone{i % 8}.lab.",
                        "type": "A",
                        "records": [f"203.0.113.{i + 10}"],
                        "ttl": 3600,
                    },
                ),
                (
                    "zaqar",
                    "message",
                    f"zmsg-{i}",
                    {"queue_name": f"queue-{i % 8}", "body": {"event": f"demo-{i}"}, "ttl": 3600},
                ),
                (
                    "zaqar",
                    "claim",
                    f"zclaim-{i}",
                    {"queue_name": f"queue-{i % 8}", "ttl": 300, "grace": 60},
                ),
                (
                    "zaqar",
                    "subscription",
                    f"zsub-{i}",
                    {
                        "queue_name": f"queue-{i % 8}",
                        "subscriber": f"http://hook.lab/{i}",
                        "ttl": 3600,
                    },
                ),
                ("cloudkitty", "hashmap_service", f"svc-{i}", {"name": f"svc-{i}"}),
                ("cloudkitty", "hashmap_field", f"field-{i}", {"name": f"field-{i}"}),
                ("cloudkitty", "report_summary", f"summary-{i}", {"tenant_id": "demo"}),
                ("cloudkitty", "dataframes", f"df-{i}", {"period": "3600"}),
                (
                    "vitrage",
                    "alarm",
                    f"vit-alarm-{i}",
                    {"state": "critical" if i % 3 == 0 else "ok"},
                ),
                ("heat-cfn", "stack", f"cfn-{i}", {"StackStatus": "CREATE_COMPLETE"}),
                ("cinder", "snapshot", f"snap-{i}", {"status": "available", "size": 10}),
                ("cinder", "backup", f"vol-backup-{i}", {"status": "available", "size": 10}),
                ("cinder", "volume_type", f"type-{i}", {"is_public": True}),
                ("cinder", "qos_spec", f"qos-{i}", {"consumer": "front-end"}),
                ("cinder", "group", f"cg-{i}", {"status": "available"}),
                ("cinder", "group_snapshot", f"cgsnap-{i}", {"status": "available"}),
                ("cinder", "consistencygroup", f"consis-{i}", {"status": "available"}),
                ("cinder", "attachment", f"attach-{i}", {"status": "attached"}),
                ("cinder", "transfer", f"xfer-{i}", {"status": "awaiting-transfer"}),
                ("cinder", "message", f"msg-{i}", {"message_level": "ERROR"}),
                ("cinder", "cluster", f"cinder-cl-{i}", {"state": "up", "status": "enabled"}),
                (
                    "cinder",
                    "service",
                    f"cinder-svc-{i}",
                    {"binary": "cinder-volume", "state": "up"},
                ),
                ("glance", "metadef_namespace", f"ns-{i}", {"visibility": "public"}),
                ("glance", "task", f"task-{i}", {"type": "import", "status": "success"}),
                (
                    "ironic",
                    "driver",
                    "ipmi" if i == 0 else f"redfish-{i}",
                    {
                        "name": "ipmi" if i == 0 else "redfish",
                        "hosts": ["simulator"],
                        "type": "classic",
                    },
                ),
                (
                    "ironic",
                    "port",
                    f"iport-{i}",
                    {"address": f"52:54:00:00:00:{i:02x}", "pxe_enabled": True},
                ),
                ("ironic", "portgroup", f"pg-{i}", {"mode": "active-backup"}),
                ("ironic", "chassis", f"chassis-{i}", {"description": f"rack-{i}"}),
                (
                    "ironic",
                    "allocation",
                    f"alloc-{i}",
                    {"state": "active", "resource_class": "baremetal"},
                ),
                ("ironic", "deploy_template", f"dt-{i}", {"steps": []}),
                (
                    "ironic",
                    "volume_connector",
                    f"vc-{i}",
                    {"type": "iqn", "connector_id": f"iqn.lab:{i}"},
                ),
                ("ironic", "volume_target", f"vt-{i}", {"volume_type": "iscsi", "boot_index": 0}),
                ("keystone", "domain", f"dom-{i}", {"enabled": True}),
                ("keystone", "group", f"group-{i}", {"description": f"group {i}"}),
                ("keystone", "region", f"Region{i}", {"description": f"region {i}"}),
                ("keystone", "service", f"svc-cat-{i}", {"type": "compute", "enabled": True}),
                (
                    "keystone",
                    "endpoint",
                    f"ep-{i}",
                    {"interface": "public", "url": f"http://svc{i}.lab:8774"},
                ),
                ("keystone", "credential", f"cred-{i}", {"type": "ec2"}),
                ("keystone", "policy", f"policy-{i}", {"type": "application/json"}),
                ("neutron", "address_group", f"ag-{i}", {"addresses": [f"10.10.{i}.0/24"]}),
                ("neutron", "segment", f"seg-{i}", {"network_type": "vxlan"}),
                ("neutron", "bgp_speaker", f"bgp-sp-{i}", {"local_as": 65000 + i}),
                (
                    "neutron",
                    "bgp_peer",
                    f"bgp-peer-{i}",
                    {"peer_ip": f"192.0.2.{i + 1}", "remote_as": 65010},
                ),
                ("watcher", "audit_template", f"at-{i}", {"goal": "server_consolidation"}),
                ("watcher", "audit", f"audit-{i}", {"state": "SUCCEEDED"}),
                ("watcher", "action_plan", f"ap-{i}", {"state": "SUCCEEDED"}),
                ("watcher", "action", f"w-action-{i}", {"state": "SUCCEEDED"}),
                ("watcher", "goal", f"goal-{i}", {"display_name": f"Goal {i}"}),
                ("watcher", "strategy", f"strategy-{i}", {"goal_uuid": f"goal-{i}"}),
                ("watcher", "scoring_engine", f"se-{i}", {"description": f"engine {i}"}),
                ("zaqar", "queue", f"queue-{i}", {"_default_message_ttl": 3600}),
                # Remaining surface collections previously empty in lab GET probes
                ("neutron", "address_scope", f"ascope-{i}", {"ip_version": 4, "shared": True}),
                (
                    "neutron",
                    "subnetpool",
                    f"spool-{i}",
                    {"default_prefixlen": 24, "prefixes": [f"10.2{i}.0.0/16"]},
                ),
                ("neutron", "qos_policy", f"qospol-{i}", {"shared": False, "is_default": i == 0}),
                ("neutron", "trunk", f"trunk-{i}", {"status": "ACTIVE", "admin_state_up": True}),
                (
                    "neutron",
                    "rbac_policy",
                    f"rbac-{i}",
                    {"action": "access_as_shared", "object_type": "network"},
                ),
                ("neutron", "metering_label", f"mlabel-{i}", {"description": f"label {i}"}),
                (
                    "neutron",
                    "metering_label_rule",
                    f"mlrule-{i}",
                    {"direction": "ingress", "remote_ip_prefix": "0.0.0.0/0"},
                ),
                (
                    "neutron",
                    "firewall_group",
                    f"fwg-{i}",
                    {"status": "ACTIVE", "admin_state_up": True},
                ),
                ("neutron", "firewall_policy", f"fwp-{i}", {"shared": False, "audited": True}),
                (
                    "neutron",
                    "firewall_rule",
                    f"fwr-{i}",
                    {"protocol": "tcp", "action": "allow", "enabled": True},
                ),
                (
                    "neutron",
                    "vpn_service",
                    f"vpns-{i}",
                    {"status": "ACTIVE", "admin_state_up": True},
                ),
                (
                    "neutron",
                    "ipsec_site_connection",
                    f"ipsec-{i}",
                    {"status": "ACTIVE", "psk": "secret"},
                ),
                (
                    "neutron",
                    "ike_policy",
                    f"ike-{i}",
                    {"auth_algorithm": "sha256", "encryption_algorithm": "aes-256"},
                ),
                ("neutron", "ipsec_policy", f"ipsecpol-{i}", {"transform_protocol": "esp"}),
                (
                    "neutron",
                    "vpn_endpoint_group",
                    f"vepg-{i}",
                    {"type": "cidr", "endpoints": [f"10.3{i}.0.0/24"]},
                ),
                (
                    "neutron",
                    "bgpvpn",
                    f"bgpvpn-{i}",
                    {"type": "l3", "route_targets": [f"64512:{i}"]},
                ),
                (
                    "neutron",
                    "log",
                    f"nlog-{i}",
                    {"enabled": True, "resource_type": "security_group"},
                ),
                ("neutron", "ndp_proxy", f"ndp-{i}", {"ip_address": f"2001:db8::{i}"}),
                (
                    "neutron",
                    "local_ip",
                    f"lip-{i}",
                    {"local_ip_address": f"10.0.0.{i + 20}", "ip_mode": "translate"},
                ),
                (
                    "neutron",
                    "network_segment_range",
                    f"nsr-{i}",
                    {"network_type": "vxlan", "minimum": 100 + i, "maximum": 200 + i},
                ),
                ("neutron", "service_profile", f"sprof-{i}", {"driver": "dummy", "enabled": True}),
                (
                    "neutron",
                    "neutron_flavor",
                    f"nflav-{i}",
                    {"service_type": "LOADBALANCERV2", "enabled": True},
                ),
                (
                    "neutron",
                    "default_security_group_rule",
                    f"dsgr-{i}",
                    {"direction": "ingress", "ethertype": "IPv4", "protocol": "tcp"},
                ),
                (
                    "neutron",
                    "lbaas_loadbalancer",
                    f"n-lb-{i}",
                    {"provisioning_status": "ACTIVE", "operating_status": "ONLINE"},
                ),
                (
                    "neutron",
                    "lbaas_listener",
                    f"n-li-{i}",
                    {"protocol": "HTTP", "protocol_port": 80},
                ),
                (
                    "neutron",
                    "lbaas_pool",
                    f"n-pool-{i}",
                    {"lb_algorithm": "ROUND_ROBIN", "protocol": "HTTP"},
                ),
                (
                    "neutron",
                    "qos_rule_type",
                    f"qrt-{i}",
                    {"type": "bandwidth_limit", "drivers": ["openvswitch"]},
                ),
                (
                    "neutron",
                    "network_ip_availability",
                    f"nipa-{i}",
                    {"network_name": f"net-{i}", "total_ips": 254, "used_ips": i},
                ),
                ("neutron", "auto_allocated_topology", f"aat-{i}", {"tenant_id": "demo"}),
                (
                    "neutron",
                    "agent",
                    f"agent-{i}",
                    {"agent_type": "L3 agent", "alive": True, "host": f"net-{i}"},
                ),
                (
                    "nova",
                    "extension",
                    f"ext-{i}",
                    {
                        "alias": f"ext-{i}",
                        "name": f"Extension {i}",
                        "namespace": "http://docs.openstack.org",
                    },
                ),
                (
                    "nova",
                    "migration",
                    f"mig-{i}",
                    {
                        "status": "completed",
                        "migration_type": "migration",
                        "source_compute": f"compute-{(i % 3) + 1}",
                        "dest_compute": f"compute-{((i + 1) % 3) + 1}",
                        "instance_uuid": str(oid(f"server:demo:{i}")),
                    },
                ),
                (
                    "nova",
                    "network",
                    f"nova-net-{i}",
                    {"label": f"nova-net-{i}", "cidr": f"10.9{i}.0.0/24"},
                ),
                ("nova", "security_group", f"nsg-{i}", {"description": f"nova sg {i}"}),
                (
                    "nova",
                    "floating_ip",
                    f"nfip-{i}",
                    {"ip": f"203.0.113.{i + 50}", "pool": "public"},
                ),
                ("nova", "instance_usage_audit_log", f"iual-{i}", {"hosts_not_run": [], "log": {}}),
                (
                    "nova",
                    "assisted_volume_snapshot",
                    f"avs-{i}",
                    {"id": f"avs-{i}", "volume_id": f"vol-{i}"},
                ),
                (
                    "nova",
                    "usage",
                    f"usage-{i}",
                    {"tenant_id": "demo", "total_hours": 10.0 * (i + 1)},
                ),
                (
                    "nova",
                    "host",
                    f"host-{i}",
                    {"host_name": f"compute-{(i % 3) + 1}", "service": "compute", "zone": "nova"},
                ),
                (
                    "nova",
                    "agent",
                    f"nagent-{i}",
                    {
                        "hypervisor": "qemu",
                        "os": "linux",
                        "architecture": "x86_64",
                        "version": "1.0",
                    },
                ),
                (
                    "octavia",
                    "listener",
                    f"ol-{i}",
                    {"protocol": "HTTP", "protocol_port": 80, "provisioning_status": "ACTIVE"},
                ),
                (
                    "octavia",
                    "pool",
                    f"op-{i}",
                    {
                        "lb_algorithm": "ROUND_ROBIN",
                        "protocol": "HTTP",
                        "provisioning_status": "ACTIVE",
                    },
                ),
                (
                    "octavia",
                    "healthmonitor",
                    f"ohm-{i}",
                    {"type": "HTTP", "delay": 5, "timeout": 3, "max_retries": 3},
                ),
                (
                    "octavia",
                    "l7policy",
                    f"ol7-{i}",
                    {"action": "REJECT", "provisioning_status": "ACTIVE"},
                ),
                (
                    "octavia",
                    "flavor",
                    f"oflav-{i}",
                    {"enabled": True, "description": f"octavia flavor {i}"},
                ),
                (
                    "octavia",
                    "flavorprofile",
                    f"ofp-{i}",
                    {"provider_name": "amphora", "flavor_data": "{}"},
                ),
                (
                    "octavia",
                    "amphora",
                    f"amph-{i}",
                    {"status": "ALLOCATED", "role": "MASTER", "cached_zone": "nova"},
                ),
                ("octavia", "quota", f"oquota-{i}", {"load_balancer": 10, "listener": 50}),
                (
                    "octavia",
                    "provider",
                    f"provider-{i}",
                    {
                        "name": f"{('amphora', 'ovn', 'octavia', 'noop')[i % 4]}-{i}",
                        "description": f"Load balancer provider {i}",
                    },
                ),
                ("placement", "resource_class", f"rc-{i}", {"name": f"CUSTOM_CLASS_{i}"}),
                ("placement", "trait", f"trait-{i}", {"name": f"CUSTOM_TRAIT_{i}"}),
                ("placement", "allocation_candidate", f"ac-{i}", {"allocations": {}}),
                ("placement", "usage", f"pusage-{i}", {"resource_class": "VCPU", "usage": i}),
                (
                    "placement",
                    "resource_provider",
                    f"rp-{i}",
                    {
                        "name": f"resource_provider-{i}",
                        "generation": 1,
                        "parent_provider_uuid": None,
                    },
                ),
                (
                    "placement",
                    "inventory",
                    f"inv-{i}",
                    {
                        "resource_provider": str(oid(f"placement:resource_provider:rp-{i}")),
                        "resource_provider_id": str(oid(f"placement:resource_provider:rp-{i}")),
                        "resource_class": "VCPU",
                        "total": 64,
                        "reserved": 0,
                    },
                ),
                (
                    "placement",
                    "aggregate",
                    f"pagg-{i}",
                    {
                        "name": f"agg-{i}",
                        "resource_provider": str(oid(f"placement:resource_provider:rp-{i}")),
                        "resource_provider_id": str(oid(f"placement:resource_provider:rp-{i}")),
                    },
                ),
                ("tacker", "vnfd", f"vnfd-{i}", {"name": f"vnfd-{i}", "description": "demo"}),
                ("tacker", "vim", f"vim-{i}", {"type": "openstack", "status": "REACHABLE"}),
                (
                    "tacker",
                    "vnf_package",
                    f"vnfpkg-{i}",
                    {"onboardingState": "ONBOARDED", "operationalState": "ENABLED"},
                ),
                ("tacker", "vnf_instance", f"vnfinst-{i}", {"instantiationState": "INSTANTIATED"}),
                ("trove", "datastore", f"ds-{i}", {"name": "mysql", "version": f"8.0.{i}"}),
                ("trove", "backup", f"tbak-{i}", {"status": "COMPLETED", "size": 1.5}),
                ("trove", "configuration", f"tcfg-{i}", {"datastore_name": "mysql"}),
                ("trove", "cluster", f"tcl-{i}", {"task": {"name": "NONE"}, "instance_count": 3}),
                ("vitrage", "topology", f"topo-{i}", {"nodes": [], "links": []}),
                ("vitrage", "resource", f"vres-{i}", {"type": "nova.instance", "state": "ACTIVE"}),
                ("vitrage", "template", f"vtmpl-{i}", {"type": "standard", "status": "active"}),
                ("vitrage", "event", f"vevt-{i}", {"type": "compute.host.down"}),
                ("watcher", "service", f"wsvc-{i}", {"host": f"watcher-{i}", "status": "ACTIVE"}),
                ("zun", "image", f"zimg-{i}", {"image": "nginx", "status": "ACTIVE"}),
                ("zun", "capsule", f"cap-{i}", {"status": "Running", "cpu": 1, "memory": 512}),
                ("zun", "host", f"zhost-{i}", {"hostname": f"zun-compute-{i}", "state": "up"}),
                (
                    "zun",
                    "service",
                    f"zsvc-{i}",
                    {"host": f"zun-{i}", "binary": "zun-compute", "state": "up"},
                ),
                ("cinder", "limit", f"clim-{i}", {"name": f"limit-{i}", "value": 1000 + i}),
                (
                    "cinder",
                    "resource_filter",
                    f"rf-{i}",
                    {"resource": "volume", "filters": ["name", "status"]},
                ),
                (
                    "cinder",
                    "pool",
                    f"cpool-{i}",
                    {"name": f"pool@backend#{i}", "capabilities": {"free_capacity_gb": 1000}},
                ),
                (
                    "ironic",
                    "conductor",
                    f"cond-{i}",
                    {"hostname": f"ironic-{i}", "conductor_group": "", "alive": True},
                ),
                (
                    "keystone",
                    "role_assignment",
                    f"ra-{i}",
                    {
                        "role": {"id": f"role-{i}"},
                        "user": {"id": f"user-{i}"},
                        "scope": {"project": {"id": "demo"}},
                    },
                ),
                (
                    "keystone",
                    "limit",
                    f"klim-{i}",
                    {"resource_name": "servers", "resource_limit": 100 + i},
                ),
                (
                    "keystone",
                    "registered_limit",
                    f"krlim-{i}",
                    {"resource_name": "servers", "default_limit": 50 + i},
                ),
                ("glance", "info_import", f"gimport-{i}", {"type": "glance-direct"}),
                (
                    "glance",
                    "info_store",
                    f"gstore-{i}",
                    {"id": f"store-{i}", "type": "file", "description": f"store {i}"},
                ),
                (
                    "glance",
                    "schema",
                    f"gschema-{i}",
                    {"name": "image", "properties": {"name": {"type": "string"}}},
                ),
                ("zaqar", "health", f"zhealth-{i}", {"catalog": True, "storage": True}),
                ("zaqar", "ping", f"zping-{i}", {"ok": True}),
            ]
        )
    for service, rtype, name, data in samples:
        item_id = oid(f"{service}:{rtype}:{name}")
        payload = {"id": str(item_id), "name": name, "status": data.get("status", "ACTIVE"), **data}
        await conn.execute(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)""",
            item_id,
            service,
            rtype,
            None,  # shared across projects so admin/demo/… tokens all see density
            name,
            payload["status"],
            json.dumps(payload),
        )

    # Nova server groups (specialized table) — denser in demo project
    for i in range(server_group_count):
        pname = "demo" if i < max(1, server_group_count // 2) else tenant_cycle[i % len(tenant_cycle)]
        span = max(1, min(8, max(1, server_count // 4)))
        members = [
            str(oid(f"server:demo:{(3 + (i % span) * 6) % server_count}")),
            str(oid(f"server:demo:{(3 + ((i + 1) % span) * 6) % server_count}")),
        ]
        await conn.execute(
            """INSERT INTO os_server_groups(id, project_id, name, policies, members)
               VALUES($1,$2,$3,$4::jsonb,$5::jsonb)""",
            oid(f"sgroup:demo:{i}"),
            project_ids[pname],
            f"sg-{pname}-{i}",
            json.dumps(["soft-anti-affinity"] if i % 2 == 0 else ["anti-affinity"]),
            json.dumps(members),
        )

    # Nested / parent-scoped collections used by pack GET probes.
    # tenant_cycle index 3,9,15… maps to the demo project for servers/volumes/ports.
    demo_pid = project_ids["demo"]
    demo_router = str(oid("router:demo"))
    demo_fip = str(oid("fip:demo:3"))
    demo_image = str(image_ids[0])
    demo_qos = str(oid("neutron:qos_policy:qospol-0"))
    demo_trunk = str(oid("neutron:trunk:trunk-0"))
    demo_local_ip = str(oid("neutron:local_ip:lip-0"))
    demo_bgpvpn = str(oid("neutron:bgpvpn:bgpvpn-0"))
    demo_stack_idx = min(3, max(0, stack_count - 1))
    demo_stack_id = str(oid(f"stack:demo:{demo_stack_idx}"))
    demo_stack_name = f"stack-demo-{demo_stack_idx:02d}"
    nested_samples: list[tuple[str, str, str, dict[str, Any]]] = []
    # Cover the first listed servers (and a wider spread) so nested GETs hit DB rows.
    for i in range(nested_sample_count):
        sidx = i % server_count
        sid = str(oid(f"server:demo:{sidx}"))
        vid = str(oid(f"volume:demo:{sidx % volume_count}"))
        port_id = str(oid(f"port:demo:{sidx}"))
        nested_samples.extend(
            [
                (
                    "nova",
                    "volume_attachment",
                    f"vattach-{i}",
                    {
                        "server_id": sid,
                        "serverId": sid,
                        "volume_id": vid,
                        "volumeId": vid,
                        "device": f"/dev/vd{chr(98 + (i % 4))}",
                    },
                ),
                (
                    "nova",
                    "interface_attachment",
                    f"iattach-{i}",
                    {"server_id": sid, "port_id": port_id, "net_id": str(project_nets["demo"][0])},
                ),
                (
                    "nova",
                    "server_metadata",
                    f"smeta-{i}",
                    {
                        "server_id": sid,
                        "key": "env",
                        "value": "demo",
                        "metadata": {"env": "demo", "index": str(sidx)},
                    },
                ),
                (
                    "nova",
                    "server_tag",
                    f"stag-{i}",
                    {"server_id": sid, "tags": [f"az-{AZS[i % 3]}", "demo", f"idx-{sidx}"]},
                ),
                (
                    "nova",
                    "server_security_group",
                    f"ssg-{i}",
                    {"server_id": sid, "name": "default", "id": str(oid("sg:demo-default"))},
                ),
                (
                    "nova",
                    "server_migration",
                    f"smig-{i}",
                    {
                        "server_id": sid,
                        "status": "completed",
                        "migration_type": "migration",
                        "source_compute": f"compute-{(i % 3) + 1}",
                    },
                ),
                (
                    "nova",
                    "console",
                    f"console-{i}",
                    {
                        "server_id": sid,
                        "protocol": "vnc",
                        "type": "novnc",
                        "url": f"http://console.lab:6080/vnc_auto.html?token=demo-{i}",
                    },
                ),
                (
                    "nova",
                    "instance_action",
                    f"iaction-{i}",
                    {
                        "server_id": sid,
                        "action": "create",
                        "instance_uuid": sid,
                        "request_id": f"req-demo-{i}",
                        "message": None,
                    },
                ),
                (
                    "nova",
                    "flavor_extra_spec",
                    f"fes-{i}",
                    {
                        "flavor_id": str((i % 8) + 1),
                        "extra_specs": {
                            "hw:cpu_policy": "shared",
                            "aggregate_instance_extra_specs:demo": "true",
                        },
                    },
                ),
                (
                    "neutron",
                    "conntrack_helper",
                    f"cth-{i}",
                    {"router_id": demo_router, "protocol": "tcp", "port": 22 + i, "helper": "ftp"},
                ),
                (
                    "neutron",
                    "floatingip_port_forwarding",
                    f"fpf-{i}",
                    {
                        "floatingip_id": demo_fip,
                        "internal_port_id": port_id,
                        "internal_ip_address": f"10.10.0.{i + 10}",
                        "internal_port": 8080 + i,
                        "external_port": 9000 + i,
                        "protocol": "tcp",
                    },
                ),
                (
                    "neutron",
                    "qos_bandwidth_limit_rule",
                    f"qbl-{i}",
                    {
                        "policy_id": demo_qos,
                        "max_kbps": 10000 * (i + 1),
                        "max_burst_kbps": 1000,
                        "direction": "egress",
                    },
                ),
                (
                    "neutron",
                    "qos_dscp_marking_rule",
                    f"qdscp-{i}",
                    {"policy_id": demo_qos, "dscp_mark": i % 64},
                ),
                (
                    "neutron",
                    "qos_minimum_bandwidth_rule",
                    f"qmb-{i}",
                    {"policy_id": demo_qos, "min_kbps": 1000 * (i + 1), "direction": "egress"},
                ),
                (
                    "neutron",
                    "trunk_subport",
                    f"tsp-{i}",
                    {
                        "trunk_id": demo_trunk,
                        "port_id": port_id,
                        "segmentation_type": "vlan",
                        "segmentation_id": 100 + i,
                    },
                ),
                (
                    "neutron",
                    "local_ip_association",
                    f"lia-{i}",
                    {
                        "local_ip_id": demo_local_ip,
                        "fixed_port_id": port_id,
                        "fixed_ip": f"10.10.0.{i + 20}",
                    },
                ),
                (
                    "neutron",
                    "bgpvpn_network_association",
                    f"bna-{i}",
                    {"bgpvpn_id": demo_bgpvpn, "network_id": str(project_nets["demo"][0])},
                ),
                (
                    "neutron",
                    "bgpvpn_router_association",
                    f"bra-{i}",
                    {"bgpvpn_id": demo_bgpvpn, "router_id": demo_router},
                ),
                (
                    "glance",
                    "image_member",
                    f"imem-{i}",
                    {
                        "image_id": demo_image,
                        "member_id": str(list(project_ids.values())[i % len(project_ids)]),
                        "status": "accepted",
                    },
                ),
                (
                    "glance",
                    "image_tag",
                    f"itag-{i}",
                    {"image_id": demo_image, "tags": [f"tag-{i}", "demo", "lab"]},
                ),
                (
                    "heat",
                    "stack_resource",
                    f"sres-{i}",
                    {
                        "tenant_id": str(demo_pid),
                        # Soft parent filter: omit stack_* so any stack list is populated.
                        "resource_name": f"resource_{i}",
                        "resource_type": "OS::Nova::Server",
                        "resource_status": "CREATE_COMPLETE",
                        "physical_resource_id": sid,
                    },
                ),
                (
                    "heat",
                    "stack_event",
                    f"sevt-{i}",
                    {
                        "tenant_id": str(demo_pid),
                        "resource_name": f"resource_{i}",
                        "resource_status": "CREATE_COMPLETE",
                        "event_time": "2026-01-01T00:00:00Z",
                    },
                ),
                (
                    "heat",
                    "software_config",
                    f"swcfg-{i}",
                    {
                        "tenant_id": str(demo_pid),
                        "group": "script",
                        "config": f"#!/bin/bash\necho demo-{i}\n",
                    },
                ),
                (
                    "heat",
                    "software_deployment",
                    f"swdep-{i}",
                    {
                        "tenant_id": str(demo_pid),
                        "status": "COMPLETE",
                        "server_id": sid,
                        "config_id": f"swcfg-{i}",
                    },
                ),
                (
                    "heat",
                    "resource_type",
                    f"rtype-{i}",
                    {
                        "tenant_id": str(demo_pid),
                        "resource_type": f"OS::Demo::Type{i}",
                        "attributes": {},
                    },
                ),
                (
                    "heat",
                    "service",
                    f"hsvc-{i}",
                    {
                        "tenant_id": str(demo_pid),
                        "host": f"heat-{i}",
                        "binary": "heat-engine",
                        "status": "up",
                    },
                ),
                (
                    "placement",
                    "allocation",
                    f"palloc-{i}",
                    {
                        "consumer_uuid": sid,
                        "resource_provider": str(oid(f"placement:resource_provider:rp-{i % 8}")),
                        "resources": {"VCPU": 1, "MEMORY_MB": 1024, "DISK_GB": 10},
                    },
                ),
            ]
        )
    for service, rtype, name, data in nested_samples:
        item_id = oid(f"{service}:{rtype}:{name}")
        payload = {"id": str(item_id), "name": name, "status": data.get("status", "ACTIVE"), **data}
        # Scope nested rows to the parent server's project (tenant_cycle index).
        owner_pid = demo_pid
        server_ref = str(data.get("server_id") or data.get("instance_uuid") or "")
        for idx in range(min(server_count, 64)):
            if server_ref == str(oid(f"server:demo:{idx}")):
                owner_pid = project_ids[tenant_cycle[idx % len(tenant_cycle)]]
                break
        await conn.execute(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)""",
            item_id,
            service,
            rtype,
            owner_pid,
            name,
            str(payload.get("status") or "ACTIVE"),
            json.dumps(payload),
        )

    # Quotas as api objects (name=project id so Neutron-style /quotas/{project_id} resolves)
    quota_factor = max(1.0, server_count / 1000)
    for pname, pid in project_ids.items():
        for svc, rtype, data in (
            (
                "nova",
                "quota_set",
                {
                    "instances": _scale(200, quota_factor, 40),
                    "cores": _scale(800, quota_factor, 80),
                    "ram": _scale(1_024_000, quota_factor, 64_000),
                },
            ),
            (
                "cinder",
                "quota_set",
                {
                    "volumes": _scale(200, quota_factor, 40),
                    "gigabytes": _scale(50_000, quota_factor, 5_000),
                },
            ),
            (
                "neutron",
                "quota",
                {
                    "network": _scale(50, quota_factor, 10),
                    "subnet": _scale(100, quota_factor, 20),
                    "port": _scale(500, quota_factor, 80),
                    "floatingip": _scale(50, quota_factor, 10),
                },
            ),
        ):
            await conn.execute(
                """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                   VALUES($1,$2,$3,$4,$5,'ACTIVE',$6::jsonb)
                   ON CONFLICT (id) DO UPDATE SET
                     name=EXCLUDED.name, status=EXCLUDED.status, data=EXCLUDED.data,
                     project_id=EXCLUDED.project_id, updated_at=now()""",
                oid(f"quota:{svc}:{pname}"),
                svc,
                rtype,
                pid,
                str(pid),
                json.dumps({"id": str(pid), "project_id": str(pid), "tenant_id": str(pid), **data}),
            )

    from app.openstack.pack_seed import seed_pack_surface_samples
    from app.openstack.seed_discovery import seed_discovery_documents

    discovery = await seed_discovery_documents(conn)
    pack_seed = await seed_pack_surface_samples(conn, per_type=pack_per_type)
    pack_seed = {**pack_seed, **discovery}

    await conn.execute(
        """INSERT INTO os_demo_meta(key, value)
           VALUES('profile', $1), ('size', $2), ('servers', $3), ('password', $4)""",
        profile,
        cfg.name,
        str(server_count),
        password,
    )

    return {
        "profile": profile,
        "size": cfg.name,
        "servers": server_count,
        "pack_seed": pack_seed,
        "volumes": volume_count,
        "hypervisors": hypervisor_count,
        "ironic_nodes": ironic_count,
        "loadbalancers": lb_count,
        "stacks": stack_count,
        "floating_ips": fip_count,
        "extra_networks": extra_networks,
        "extra_security_groups": extra_security_groups,
        "keypairs_per_user": keypairs_per_user,
        "edge_routers": edge_routers,
        "projects": list(project_ids.keys()),
        "users": list(user_ids.keys()),
        "password": password,
        "availability_zones": list(AZS),
        "cluster": asdict(cfg),
    }


async def openstack_demo_summary(conn: Connection) -> dict[str, Any]:
    profile = await conn.fetchval("SELECT value FROM os_demo_meta WHERE key='profile'")
    size = await conn.fetchval("SELECT value FROM os_demo_meta WHERE key='size'")
    servers = await conn.fetchval("SELECT count(*) FROM os_servers")
    volumes = await conn.fetchval("SELECT count(*) FROM os_volumes")
    networks = await conn.fetchval("SELECT count(*) FROM os_networks")
    ports = await conn.fetchval("SELECT count(*) FROM os_ports")
    images = await conn.fetchval("SELECT count(*) FROM os_images")
    hypervisors = await conn.fetchval("SELECT count(*) FROM os_hypervisors")
    projects = await conn.fetchval("SELECT count(*) FROM os_projects")
    users = await conn.fetchval("SELECT count(*) FROM os_users")
    lbs = await conn.fetchval("SELECT count(*) FROM os_loadbalancers")
    stacks = await conn.fetchval("SELECT count(*) FROM os_stacks")
    nodes = await conn.fetchval("SELECT count(*) FROM os_nodes")
    fips = await conn.fetchval("SELECT count(*) FROM os_floating_ips")
    loaded = is_demo_profile(profile)
    cfg = DEMO_CLUSTER_SIZES.get(str(size or ""), None)
    if cfg is None and loaded and isinstance(profile, str) and ":" in profile:
        cfg = DEMO_CLUSTER_SIZES.get(profile.rsplit(":", 1)[-1])
    return {
        "loaded": loaded,
        "profile": profile or "minimal",
        "size": (cfg.name if cfg else size) or None,
        "servers": int(servers or 0),
        "volumes": int(volumes or 0),
        "networks": int(networks or 0),
        "ports": int(ports or 0),
        "images": int(images or 0),
        "hypervisors": int(hypervisors or 0),
        "projects": int(projects or 0),
        "users": int(users or 0),
        "loadbalancers": int(lbs or 0),
        "stacks": int(stacks or 0),
        "ironic_nodes": int(nodes or 0),
        "floating_ips": int(fips or 0),
        "target_servers": cfg.servers if cfg else int(servers or 0),
        "sizes": list_demo_sizes(),
    }
