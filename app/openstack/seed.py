"""Seed OpenStack identity and sample cloud resources."""

from __future__ import annotations

import json

from asyncpg import Connection

from app.openstack.ids import oid
from app.security.auth import hash_secret


async def seed_openstack(conn: Connection, *, password: str = "secret") -> dict[str, object]:
    """Idempotent OpenStack lab seed (admin + demo project/user + sample resources)."""

    domain_id = oid("domain:Default")
    admin_project = oid("project:admin")
    demo_project = oid("project:demo")
    admin_user = oid("user:admin")
    demo_user = oid("user:demo")
    role_admin = oid("role:admin")
    role_member = oid("role:member")
    pw = hash_secret(password, salt=b"openstack-sim-v1")

    await conn.execute(
        """INSERT INTO os_domains(id, name, description, enabled)
           VALUES($1, 'Default', 'Default domain', true)
           ON CONFLICT (id) DO NOTHING""",
        domain_id,
    )
    await conn.execute(
        """INSERT INTO os_projects(id, domain_id, name, description, enabled) VALUES
           ($1, $3, 'admin', 'Admin project', true),
           ($2, $3, 'demo', 'Demo project', true)
           ON CONFLICT (id) DO NOTHING""",
        admin_project,
        demo_project,
        domain_id,
    )
    await conn.execute(
        """INSERT INTO os_users(id, domain_id, name, password_hash, enabled) VALUES
           ($1, $3, 'admin', $4, true),
           ($2, $3, 'demo', $4, true)
           ON CONFLICT (id) DO NOTHING""",
        admin_user,
        demo_user,
        domain_id,
        pw,
    )
    await conn.execute(
        """INSERT INTO os_roles(id, name) VALUES
           ($1, 'admin'), ($2, 'member')
           ON CONFLICT (id) DO NOTHING""",
        role_admin,
        role_member,
    )
    await conn.execute(
        """INSERT INTO os_role_assignments(id, role_id, user_id, project_id) VALUES
           ($1, $3, $5, $7),
           ($2, $4, $6, $8)
           ON CONFLICT (role_id, user_id, project_id) DO NOTHING""",
        oid("assign:admin-admin"),
        oid("assign:demo-member"),
        role_admin,
        role_member,
        admin_user,
        demo_user,
        admin_project,
        demo_project,
    )
    # admin also admin on demo for convenience
    await conn.execute(
        """INSERT INTO os_role_assignments(id, role_id, user_id, project_id)
           VALUES($1, $2, $3, $4)
           ON CONFLICT (role_id, user_id, project_id) DO NOTHING""",
        oid("assign:admin-demo-admin"),
        role_admin,
        admin_user,
        demo_project,
    )

    flavors = [
        ("1", "m1.tiny", 1, 512, 1),
        ("2", "m1.small", 1, 2048, 20),
        ("3", "m1.medium", 2, 4096, 40),
        ("4", "m1.large", 4, 8192, 80),
    ]
    for fid, name, vcpus, ram, disk in flavors:
        await conn.execute(
            """INSERT INTO os_flavors(id, name, vcpus, ram, disk, is_public)
               VALUES($1, $2, $3, $4, $5, true)
               ON CONFLICT (id) DO NOTHING""",
            fid,
            name,
            vcpus,
            ram,
            disk,
        )

    cirros = oid("image:cirros")
    ubuntu = oid("image:ubuntu")
    await conn.execute(
        """INSERT INTO os_images(id, name, status, visibility, size, disk_format,
               container_format, owner_project_id)
           VALUES
           ($1, 'cirros', 'active', 'public', 13287936, 'qcow2', 'bare', $3),
           ($2, 'ubuntu-22.04', 'active', 'public', 400000000, 'qcow2', 'bare', $3)
           ON CONFLICT (id) DO NOTHING""",
        cirros,
        ubuntu,
        admin_project,
    )

    demo_net = oid("net:demo-net")
    await conn.execute(
        """INSERT INTO os_networks(id, project_id, name, status, shared, admin_state_up)
           VALUES($1, $2, 'demo-net', 'ACTIVE', false, true)
           ON CONFLICT (id) DO NOTHING""",
        demo_net,
        demo_project,
    )
    demo_subnet = oid("subnet:demo-subnet")
    await conn.execute(
        """INSERT INTO os_subnets(id, network_id, project_id, name, cidr, ip_version, gateway_ip)
           VALUES($1, $2, $3, 'demo-subnet', '10.0.0.0/24', 4, '10.0.0.1')
           ON CONFLICT (id) DO NOTHING""",
        demo_subnet,
        demo_net,
        demo_project,
    )

    vol = oid("volume:demo-vol")
    await conn.execute(
        """INSERT INTO os_volumes(id, project_id, name, status, size, volume_type, bootable)
           VALUES($1, $2, 'demo-volume', 'available', 10, 'lvmdriver-1', false)
           ON CONFLICT (id) DO NOTHING""",
        vol,
        demo_project,
    )

    server = oid("server:demo-1")
    await conn.execute(
        """INSERT INTO os_servers(id, project_id, user_id, name, status, flavor_id, image_id, addresses, metadata)
           VALUES($1, $2, $3, 'demo-instance', 'ACTIVE', '2', $4,
                  $5::jsonb, $6::jsonb)
           ON CONFLICT (id) DO NOTHING""",
        server,
        demo_project,
        demo_user,
        cirros,
        '{"demo-net":[{"OS-EXT-IPS-MAC:mac_addr":"fa:16:3e:00:00:01","version":4,"addr":"10.0.0.12","OS-EXT-IPS:type":"fixed"}]}',
        '{"env":"lab","_tags":["lab","env","demo"]}',
    )
    await conn.execute(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,'nova','instance_action',$2,'create','DONE',$3::jsonb)
           ON CONFLICT (id) DO NOTHING""",
        oid("nova:instance_action:demo-1"),
        demo_project,
        json.dumps(
            {
                "action": "create",
                "instance_uuid": str(server),
                "server_id": str(server),
                "request_id": f"req-seed-{str(server)[:8]}",
                "message": None,
            }
        ),
    )

    await seed_openstack_extras(conn)

    from app.openstack.pack_seed import seed_pack_surface_samples
    from app.openstack.seed_discovery import seed_discovery_documents

    await seed_discovery_documents(conn)
    await seed_pack_surface_samples(conn, per_type=3)

    # Minimal topology tables (011+) — ignore if migration not applied yet.
    try:
        await conn.execute(
            """INSERT INTO os_availability_zones(name, zone_state)
               VALUES('nova', '{"available": true}'::jsonb)
               ON CONFLICT (name) DO NOTHING"""
        )
        await conn.execute(
            """INSERT INTO os_hypervisors(
                   id, hypervisor_hostname, state, status, host_ip, vcpus, vcpus_used,
                   memory_mb, memory_mb_used, local_gb, local_gb_used, running_vms,
                   service_host, availability_zone)
               VALUES(1,'compute-1','up','enabled','10.20.0.10',64,1,262144,2048,2000,20,1,'compute-1','nova')
               ON CONFLICT (id) DO NOTHING"""
        )
        await conn.execute(
            """INSERT INTO os_demo_meta(key, value) VALUES('profile','minimal')
               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=now()"""
        )
    except Exception:
        pass

    return {
        "domain": "Default",
        "users": ["admin", "demo"],
        "password": password,
        "projects": ["admin", "demo"],
        "sample_server": "demo-instance",
        "profile": "minimal",
    }


async def seed_openstack_extras(conn: Connection) -> None:
    """Seed routers, SG, ironic nodes, LB, heat stack, swift objects, generic services."""

    import json
    from uuid import uuid4

    demo_project = oid("project:demo")
    admin_project = oid("project:admin")
    demo_user = oid("user:demo")

    # default security group
    sg = oid("sg:demo-default")
    await conn.execute(
        """INSERT INTO os_security_groups(id, project_id, name, description)
           VALUES($1,$2,'default','Default security group') ON CONFLICT (id) DO NOTHING""",
        sg,
        demo_project,
    )
    for direction, proto, pmin, pmax, prefix in (
        ("egress", None, None, None, None),
        ("ingress", "tcp", 22, 22, "0.0.0.0/0"),
        ("ingress", "icmp", None, None, "0.0.0.0/0"),
    ):
        await conn.execute(
            """INSERT INTO os_security_group_rules(id, security_group_id, project_id, direction, ethertype, protocol, port_range_min, port_range_max, remote_ip_prefix)
               VALUES($1,$2,$3,$4,'IPv4',$5,$6,$7,$8) ON CONFLICT (id) DO NOTHING""",
            oid(f"sgrule:{direction}:{proto}:{pmin}"),
            sg,
            demo_project,
            direction,
            proto,
            pmin,
            pmax,
            prefix,
        )

    # Shared external provider network for floating IPs / router gateways.
    public_net = oid("net:public")
    await conn.execute(
        """INSERT INTO os_networks(id, project_id, name, status, shared, admin_state_up)
           VALUES($1,$2,'public','ACTIVE',true,true) ON CONFLICT (id) DO NOTHING""",
        public_net,
        admin_project,
    )
    public_subnet = oid("subnet:public")
    await conn.execute(
        """INSERT INTO os_subnets(id, network_id, project_id, name, cidr, ip_version, gateway_ip)
           VALUES($1,$2,$3,'public-subnet','203.0.113.0/24',4,'203.0.113.1')
           ON CONFLICT (id) DO NOTHING""",
        public_subnet,
        public_net,
        admin_project,
    )
    await conn.execute(
        """INSERT INTO os_routers(id, project_id, name, status, admin_state_up, external_gateway_info)
           VALUES($1,$2,'demo-router','ACTIVE',true,$3::jsonb) ON CONFLICT (id) DO NOTHING""",
        oid("router:demo"),
        demo_project,
        json.dumps(
            {
                "network_id": str(public_net),
                "enable_snat": True,
                "external_fixed_ips": [
                    {"ip_address": "203.0.113.2", "subnet_id": str(public_subnet)}
                ],
            }
        ),
    )
    await conn.execute(
        """INSERT INTO os_floating_ips(
               id, project_id, floating_ip_address, floating_network_id, port_id, status)
           VALUES($1,$2,'203.0.113.50',$3,NULL,'DOWN') ON CONFLICT (id) DO NOTHING""",
        oid("fip:demo"),
        demo_project,
        public_net,
    )

    demo_net = oid("net:demo-net")
    demo_subnet = oid("subnet:demo-subnet")
    demo_server = oid("server:demo-1")
    await conn.execute(
        """INSERT INTO os_ports(
               id, network_id, project_id, name, status, mac_address,
               device_id, device_owner, fixed_ips)
           VALUES(
               $1,$2,$3,'demo-port','ACTIVE','fa:16:3e:00:00:aa',
               $4,'compute:nova',
               $5::jsonb
           ) ON CONFLICT (id) DO NOTHING""",
        oid("port:demo"),
        demo_net,
        demo_project,
        str(demo_server),
        json.dumps([{"subnet_id": str(demo_subnet), "ip_address": "10.0.0.12"}]),
    )
    await conn.execute(
        """INSERT INTO os_server_groups(id, project_id, name, policies, members)
           VALUES($1,$2,'demo-sg',$3::jsonb,'[]'::jsonb) ON CONFLICT (id) DO NOTHING""",
        oid("sgroup:demo"),
        demo_project,
        json.dumps(["soft-anti-affinity"]),
    )
    try:
        await conn.execute(
            """INSERT INTO os_aggregates(id, name, availability_zone, hosts, metadata)
               VALUES(1,'agg-nova','nova','["compute-1"]'::jsonb,'{}'::jsonb)
               ON CONFLICT (id) DO NOTHING"""
        )
        await conn.execute(
            """INSERT INTO os_compute_services("binary", host, zone, status, state)
               VALUES('nova-compute','compute-1','nova','enabled','up')"""
        )
    except Exception:
        # Topology tables from migration 011 may be absent in partial installs.
        pass

    await conn.execute(
        """INSERT INTO os_nodes(id, name, driver, provision_state, power_state, resource_class, properties, driver_info, ports)
           VALUES($1,'baremetal-1','ipmi','available','power off','baremetal',
                  '{"cpus":64,"memory_mb":262144,"local_gb":2000}'::jsonb,'{}'::jsonb,'[]'::jsonb)
           ON CONFLICT (id) DO NOTHING""",
        oid("node:baremetal-1"),
    )

    await conn.execute(
        """INSERT INTO os_loadbalancers(id, project_id, name, description, vip_address, provisioning_status, operating_status)
           VALUES($1,$2,'demo-lb','Seed LB','10.0.0.50','ACTIVE','ONLINE')
           ON CONFLICT (id) DO NOTHING""",
        oid("lb:demo"),
        demo_project,
    )

    await conn.execute(
        """INSERT INTO os_stacks(id, project_id, stack_name, stack_status, description, template, parameters, outputs)
           VALUES($1,$2,'demo-stack','CREATE_COMPLETE','Seed stack','{"heat_template_version":"2015-04-30"}'::jsonb,'{}'::jsonb,'[]'::jsonb)
           ON CONFLICT (id) DO NOTHING""",
        oid("stack:demo"),
        demo_project,
    )

    for project in (demo_project, admin_project):
        account = f"AUTH_{project}"
        await conn.execute(
            """INSERT INTO os_swift_containers(account, name, meta)
               VALUES($1,'images','{}'::jsonb) ON CONFLICT DO NOTHING""",
            account,
        )
        await conn.execute(
            """INSERT INTO os_swift_objects(id, account, container, name, content_type, bytes, body, meta)
               VALUES($1,$2,'images','readme.txt','text/plain',12,$3,'{}'::jsonb)
               ON CONFLICT (account, container, name) DO NOTHING""",
            oid(f"swift:readme:{account}"),
            account,
            b"hello swift\n",
        )

    for user_id, key_name in ((demo_user, "demo-key"), (oid("user:admin"), "admin-key")):
        await conn.execute(
            """INSERT INTO os_keypairs(name, user_id, fingerprint, public_key, type)
               VALUES($1,$2,$3,$4,'ssh')
               ON CONFLICT DO NOTHING""",
            key_name,
            user_id,
            f"https://example.invalid/{key_name}",
            f"ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC {key_name}@lab",
        )

    # Sample objects for every remaining service collection
    samples = [
        (
            "barbican",
            "secret",
            "demo-secret",
            {"payload_content_type": "text/plain", "secret_type": "passphrase"},
        ),
        (
            "manila",
            "share",
            "demo-share",
            {"size": 10, "share_proto": "NFS", "status": "available"},
        ),
        (
            "designate",
            "zone",
            "example.lab.",
            {"email": "hostmaster@example.lab", "ttl": 3600, "type": "PRIMARY"},
        ),
        (
            "magnum",
            "cluster",
            "demo-k8s",
            {"coe": "kubernetes", "status": "CREATE_COMPLETE", "node_count": 2},
        ),
        ("zun", "container", "demo-ctr", {"image": "cirros", "status": "Running"}),
        (
            "trove",
            "instance",
            "demo-db",
            {"datastore": {"type": "mysql", "version": "8.0"}, "status": "ACTIVE"},
        ),
        (
            "mistral",
            "workflow",
            "demo-wf",
            {"input": {}, "definition": "version: '2.0'\ndemo_wf:\n  tasks: {}"},
        ),
        (
            "aodh",
            "alarm",
            "cpu-high",
            {"type": "threshold", "state": "ok", "severity": "avg(cpu)>80"},
        ),
        (
            "freezer",
            "job",
            "daily-backup",
            {"description": "lab backup job", "status": "scheduled"},
        ),
        (
            "blazar",
            "lease",
            "demo-lease",
            {"start_date": "2026-01-01T00:00:00", "end_date": "2026-12-31T00:00:00"},
        ),
        ("vitrage", "alarm", "host-down", {"type": "host", "state": "critical"}),
        (
            "masakari",
            "segment",
            "az-segment",
            {"recovery_method": "auto", "service_type": "compute"},
        ),
        ("tacker", "vnf", "demo-vnf", {"status": "ACTIVE", "vnfd_id": "vnfd-1"}),
        ("adjutant", "task", "invite-user", {"task_type": "create_user", "status": "open"}),
        ("adjutant", "token", "adj-token-demo", {"status": "active"}),
        ("adjutant", "notification", "adj-notif-demo", {"status": "sent"}),
        (
            "adjutant",
            "status",
            "adj-status-demo",
            {"status": "UP", "service": "adjutant", "state": "up"},
        ),
        ("cloudkitty", "hashmap_service", "compute", {"name": "compute"}),
        (
            "heat-cfn",
            "stack",
            "demo-cfn",
            {"StackName": "demo-cfn", "StackStatus": "CREATE_COMPLETE"},
        ),
        ("watcher", "audit", "demo-audit", {"state": "SUCCEEDED"}),
        ("zaqar", "queue", "demo-queue", {"_default_message_ttl": 3600}),
        (
            "masakari",
            "host",
            "compute-1",
            {"name": "compute-1", "type": "compute", "reserved": False},
        ),
        ("designate", "recordset", "www", {"type": "A", "records": ["203.0.113.10"], "ttl": 3600}),
        # Extra types that pack lists expose and previously relied on lazy fixtures.
        ("barbican", "container", "demo-container", {"type": "generic", "status": "ACTIVE"}),
        ("barbican", "order", "demo-order", {"type": "key", "status": "ACTIVE"}),
        ("barbican", "secret_store", "demo-store", {"status": "ACTIVE"}),
        ("manila", "share_type", "default", {"is_public": True}),
        ("manila", "share_network", "demo-share-net", {"status": "active"}),
        ("manila", "share_snapshot", "demo-share-snap", {"status": "available", "size": 10}),
        ("manila", "share_server", "demo-share-srv", {"status": "active"}),
        ("manila", "security_service", "demo-sec-svc", {"type": "ldap", "status": "new"}),
        ("manila", "share_group", "demo-share-grp", {"status": "available"}),
        ("manila", "share_replica", "demo-share-rep", {"status": "available"}),
        ("designate", "tld", "lab", {"name": "lab"}),
        ("designate", "blacklist", "bad-pattern", {"pattern": "^bad\\..*"}),
        ("designate", "pool", "default", {"name": "default"}),
        ("designate", "service_status", "dns-central", {"status": "UP"}),
        ("magnum", "clustertemplate", "k8s-default", {"coe": "kubernetes", "image_id": "cirros"}),
        ("magnum", "certificate", "demo-cert", {"cluster_uuid": "demo-k8s"}),
        ("zun", "capsule", "demo-capsule", {"status": "Running", "cpu": 1, "memory": 512}),
        ("zun", "host", "zun-compute-1", {"hostname": "zun-compute-1", "state": "up"}),
        ("zun", "image", "nginx", {"image": "nginx", "status": "ACTIVE"}),
        (
            "zun",
            "service",
            "zun-compute",
            {"host": "zun-1", "binary": "zun-compute", "state": "up"},
        ),
        ("trove", "backup", "demo-db-bak", {"status": "COMPLETED", "size": 1.5}),
        ("trove", "cluster", "demo-db-cl", {"instance_count": 3}),
        ("trove", "configuration", "demo-db-cfg", {"datastore_name": "mysql"}),
        ("trove", "datastore", "mysql", {"name": "mysql", "version": "8.0"}),
        ("mistral", "action", "demo-action", {"is_system": False}),
        ("mistral", "cron_trigger", "hourly", {"pattern": "0 * * * *"}),
        ("mistral", "execution", "demo-exec", {"state": "SUCCESS"}),
        ("mistral", "task", "demo-task", {"state": "SUCCESS"}),
        ("mistral", "workbook", "demo-wb", {"definition": "version: '2.0'"}),
        ("aodh", "quota", "aodh-default", {"alarm": 100}),
        ("freezer", "action", "demo-freezer-action", {"status": "available"}),
        ("freezer", "backup", "demo-freezer-bak", {"status": "available"}),
        ("freezer", "client", "demo-freezer-client", {"status": "available"}),
        ("freezer", "session", "demo-freezer-session", {"status": "scheduled"}),
        ("blazar", "floatingip", "blazar-fip", {"floating_ip_address": "198.51.100.10"}),
        ("blazar", "host", "blazar-host-1", {"status": "available"}),
        ("vitrage", "event", "host-down-evt", {"type": "compute.host.down"}),
        ("vitrage", "resource", "vit-server", {"type": "nova.instance", "state": "ACTIVE"}),
        ("vitrage", "template", "vit-tmpl", {"type": "standard", "status": "active"}),
        ("vitrage", "topology", "vit-topo", {"nodes": [], "links": []}),
        ("masakari", "notification", "demo-notif", {"status": "finished"}),
        ("tacker", "vim", "demo-vim", {"type": "openstack", "status": "REACHABLE"}),
        ("tacker", "vnf_instance", "demo-vnf-inst", {"instantiationState": "INSTANTIATED"}),
        ("tacker", "vnf_package", "demo-vnf-pkg", {"onboardingState": "ONBOARDED"}),
        ("tacker", "vnfd", "demo-vnfd", {"name": "demo-vnfd"}),
        ("cloudkitty", "dataframes", "df-0", {"period": "3600"}),
        ("cloudkitty", "hashmap_field", "field-0", {"name": "field-0"}),
        ("cloudkitty", "report_summary", "summary-0", {"tenant_id": "demo"}),
        ("watcher", "action", "w-action-0", {"state": "SUCCEEDED"}),
        ("watcher", "action_plan", "ap-0", {"state": "SUCCEEDED"}),
        ("watcher", "audit_template", "at-0", {"goal": "server_consolidation"}),
        ("watcher", "goal", "goal-0", {"display_name": "Goal 0"}),
        ("watcher", "scoring_engine", "se-0", {"description": "engine 0"}),
        ("watcher", "service", "wsvc-0", {"host": "watcher-0", "status": "ACTIVE"}),
        ("watcher", "strategy", "strategy-0", {"goal_uuid": "goal-0"}),
        ("ironic", "driver", "ipmi", {"name": "ipmi", "hosts": ["simulator"], "type": "classic"}),
        (
            "ironic",
            "driver",
            "redfish",
            {"name": "redfish", "hosts": ["simulator"], "type": "classic"},
        ),
        (
            "neutron",
            "agent",
            "l3-agent",
            {"agent_type": "L3 agent", "host": "network-1", "alive": True, "admin_state_up": True},
        ),
        (
            "neutron",
            "agent",
            "ovs-agent",
            {
                "agent_type": "Open vSwitch agent",
                "host": "compute-1",
                "alive": True,
                "admin_state_up": True,
            },
        ),
        (
            "nova",
            "console_output",
            "default-console",
            {"output": "Booting...\nSimulator console\n"},
        ),
        (
            "nova",
            "console",
            "default-vnc",
            {"type": "novnc", "url": "https://127.0.0.1:6080/vnc_auto.html?token=simulator"},
        ),
        (
            "nova",
            "migration",
            "demo-mig",
            {
                "status": "completed",
                "migration_type": "migration",
                "source_compute": "compute-1",
                "dest_compute": "compute-2",
                "instance_uuid": str(oid("server:demo-1")),
            },
        ),
        (
            "nova",
            "server_topology",
            "demo-topo",
            {
                "server_id": str(oid("server:demo-1")),
                "nodes": [
                    {
                        "vcpu_set": [0],
                        "siblings": [[0]],
                        "host_node": 0,
                        "memory_mb": 2048,
                        "cpu_pinning": {},
                    }
                ],
                "pagesize_kb": 4,
                "host": "compute-1",
            },
        ),
        (
            "nova",
            "server_password",
            "demo-password",
            {"server_id": str(oid("server:demo-1")), "password": ""},
        ),
        (
            "placement",
            "resource_provider",
            "rp-0",
            {"name": "compute-1", "generation": 1},
        ),
        (
            "placement",
            "allocation",
            "alloc-demo",
            {
                "consumer_uuid": str(oid("server:demo-1")),
                "resource_provider": str(oid("placement:resource_provider:rp-0")),
                "resource_provider_id": str(oid("placement:resource_provider:rp-0")),
                "resources": {"VCPU": 1, "MEMORY_MB": 2048, "DISK_GB": 20},
                "consumer_generation": 1,
            },
        ),
        (
            "placement",
            "inventory",
            "inv-demo",
            {
                "resource_provider": str(oid("placement:resource_provider:rp-0")),
                "resource_provider_id": str(oid("placement:resource_provider:rp-0")),
                "resource_class": "VCPU",
                "total": 64,
                "reserved": 0,
            },
        ),
        (
            "placement",
            "aggregate",
            "agg-demo",
            {
                "name": "agg-demo",
                "resource_provider": str(oid("placement:resource_provider:rp-0")),
                "resource_provider_id": str(oid("placement:resource_provider:rp-0")),
            },
        ),
        (
            "nova",
            "console_auth_token",
            "demo-cat",
            {
                "token": "demo-console-token",
                "console_type": "novnc",
                "host": "127.0.0.1",
                "port": 6080,
                "internal_access_path": None,
            },
        ),
    ]
    for service, rtype, name, data in samples:
        item_id = oid(f"{service}:{rtype}:{name}")
        payload = {"id": str(item_id), "name": name, "status": data.get("status", "ACTIVE"), **data}
        await conn.execute(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)
               ON CONFLICT (id) DO NOTHING""",
            item_id,
            service,
            rtype,
            None,  # visible to any project-scoped token
            name,
            payload["status"],
            json.dumps(payload),
        )
