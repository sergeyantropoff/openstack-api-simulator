"""Maximize pulumi_openstack coverage against the OpenStack API simulator.

Creates / looks up resources via the official provider, then exports IDs so
the suite can assert every stack output is non-empty.

Notes vs simulator limits:
- flavor_id is seeded ``1`` (get_flavor fails on extra_specs shape)
- skip Heat/Designate/Swift/Octavia creates (status codes or catalog URL
  shapes the lab does not yet match)
"""

from __future__ import annotations

import os
import uuid

import pulumi
from pulumi_openstack import blockstorage, compute, identity, images, networking

series = os.environ.get("OPENSTACK_SERIES", "dalmatian")
tag = f"pu-{series}-{uuid.uuid4().hex[:6]}"

# --- Data sources (reads) ---
auth = identity.get_auth_scope(name="lab-token")
image = images.get_image(name="cirros", most_recent=True)
demo_net = networking.get_network(name="demo-net")
flavor_id = "1"  # seeded m1.tiny

# --- Identity (writes) ---
project = identity.Project(
    f"{tag}-project",
    name=f"{tag}-project",
    description=f"pulumi coverage {series}",
    enabled=True,
)
user = identity.User(
    f"{tag}-user",
    name=f"{tag}-user",
    password="pulumi-lab-secret",
    description=f"pulumi coverage {series}",
    enabled=True,
)

# --- Networking ---
app_net = networking.Network(f"{tag}-net", name=f"{tag}-net", admin_state_up=True)
app_subnet = networking.Subnet(
    f"{tag}-subnet",
    name=f"{tag}-subnet",
    network_id=app_net.id,
    cidr="10.88.0.0/24",
    ip_version=4,
    enable_dhcp=True,
)
router = networking.Router(f"{tag}-router", name=f"{tag}-router", admin_state_up=True)
router_iface = networking.RouterInterface(
    f"{tag}-rtr-if",
    router_id=router.id,
    subnet_id=app_subnet.id,
)
sg = networking.SecGroup(
    f"{tag}-sg",
    name=f"{tag}-sg",
    description=f"pulumi {series}",
    delete_default_rules=True,
)
sg_rule = networking.SecGroupRule(
    f"{tag}-sg-ssh",
    direction="ingress",
    ethertype="IPv4",
    protocol="tcp",
    port_range_min=22,
    port_range_max=22,
    remote_ip_prefix="0.0.0.0/0",
    security_group_id=sg.id,
)
port = networking.Port(
    f"{tag}-port",
    name=f"{tag}-port",
    network_id=app_net.id,
    admin_state_up=True,
    security_group_ids=[sg.id],
    fixed_ips=[networking.PortFixedIpArgs(subnet_id=app_subnet.id)],
)

# --- Compute ---
keypair = compute.Keypair(f"{tag}-kp", name=f"{tag}-kp")
server_group = compute.ServerGroup(
    f"{tag}-sgroup",
    name=f"{tag}-sgroup",
    policies="anti-affinity",
)
server = compute.Instance(
    f"{tag}-vm",
    name=f"{tag}-vm",
    flavor_id=flavor_id,
    image_id=image.id,
    key_pair=keypair.name,
    security_groups=[sg.name],
    networks=[compute.InstanceNetworkArgs(uuid=demo_net.id)],
    scheduler_hints=[compute.InstanceSchedulerHintArgs(group=server_group.id)],
    metadata={"managed_by": "pulumi", "series": series, "tag": tag},
)
iface = compute.InterfaceAttach(
    f"{tag}-iface",
    instance_id=server.id,
    port_id=port.id,
)

# --- Block storage ---
volume = blockstorage.Volume(
    f"{tag}-vol",
    name=f"{tag}-vol",
    size=1,
    description=f"pulumi coverage {series}",
)
vol_attach = compute.VolumeAttach(
    f"{tag}-attach",
    instance_id=server.id,
    volume_id=volume.id,
)
volume2 = blockstorage.Volume(
    f"{tag}-vol2",
    name=f"{tag}-vol2",
    size=1,
    description=f"pulumi second volume {series}",
)

# Octavia / Designate / Swift / Heat omitted: catalog paths or status codes
# in the lab gateway do not yet match what pulumi_openstack expects.

# --- Exports (all must be non-empty; suite requires >= 25) ---
pulumi.export("series", series)
pulumi.export("tag", tag)
pulumi.export("auth_user_id", auth.user_id)
pulumi.export("auth_project_id", auth.project_id)
pulumi.export("project_name", auth.project_name)
pulumi.export("flavor_id", flavor_id)
pulumi.export("image_id", image.id)
pulumi.export("image_name", image.name)
pulumi.export("demo_net_id", demo_net.id)
pulumi.export("created_project_id", project.id)
pulumi.export("created_user_id", user.id)
pulumi.export("network_id", app_net.id)
pulumi.export("subnet_id", app_subnet.id)
pulumi.export("router_id", router.id)
pulumi.export("router_iface_id", router_iface.id)
pulumi.export("secgroup_id", sg.id)
pulumi.export("secgroup_rule_id", sg_rule.id)
pulumi.export("port_id", port.id)
pulumi.export("keypair_name", keypair.name)
pulumi.export("server_group_id", server_group.id)
pulumi.export("server_id", server.id)
pulumi.export("server_name", server.name)
pulumi.export("interface_id", iface.id)
pulumi.export("volume_id", volume.id)
pulumi.export("volume2_id", volume2.id)
pulumi.export("volume_attach_id", vol_attach.id)
