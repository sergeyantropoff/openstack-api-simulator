"""Pulumi cookbook: OpenStack network + compute instance on the simulator.

Uses pulumi_openstack (not vsphere). Defaults target local Compose gateway.
"""

from __future__ import annotations

import pulumi
from pulumi_openstack import compute, images, networking

config = pulumi.Config()
# Provider picks up OS_* env vars; also set via Pulumi.yaml / pulumi config.

image = images.get_image(name="cirros", most_recent=True)
demo_net = networking.get_network(name="demo-net")

app_net = networking.Network("pulumi-app-net", name="pulumi-app-net", admin_state_up=True)
app_subnet = networking.Subnet(
    "pulumi-app-subnet",
    name="pulumi-app-subnet",
    network_id=app_net.id,
    cidr="10.77.0.0/24",
    ip_version=4,
)

instance = compute.Instance(
    "pulumi-cookbook-vm",
    name="pulumi-cookbook-vm",
    flavor_id="1",
    image_id=image.id,
    networks=[compute.InstanceNetworkArgs(uuid=demo_net.id)],
    metadata={
        "managed_by": "pulumi",
        "stack": "openstack-api-simulator",
    },
)

pulumi.export("image_id", image.id)
pulumi.export("server_id", instance.id)
pulumi.export("server_name", instance.name)
pulumi.export("app_network_id", app_net.id)
pulumi.export("app_subnet_id", app_subnet.id)
