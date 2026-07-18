#!/usr/bin/env python3
"""OpenStack SDK cookbook against openstack-api-simulator.

Creates network + server + volume, updates metadata, cleans up.
"""

from __future__ import annotations

import sys

import openstack


def main() -> int:
    conn = openstack.connect(
        auth_url="http://127.0.0.1:5000/v3",
        project_name="demo",
        username="admin",
        password="secret",
        user_domain_name="Default",
        project_domain_name="Default",
        region_name="RegionOne",
    )

    print("identity ok:", conn.identity.get_project(conn.current_project_id).name)

    image = conn.image.find_image("cirros", ignore_missing=False)
    network = conn.network.find_network("demo-net", ignore_missing=False)
    print("boot image:", image.id, image.name)
    print("network:", network.id, network.name)

    app_net = conn.network.create_network(name="sdk-app-net", admin_state_up=True)
    app_subnet = conn.network.create_subnet(
        name="sdk-app-subnet",
        network_id=app_net.id,
        ip_version=4,
        cidr="10.88.0.0/24",
    )
    print("created net/subnet:", app_net.id, app_subnet.id)

    server = conn.compute.create_server(
        name="sdk-cookbook-vm",
        flavor_id="1",
        image_id=image.id,
        networks=[{"uuid": network.id}],
        metadata={"managed_by": "openstacksdk"},
    )
    server = conn.compute.wait_for_server(server, status="ACTIVE", failures=["ERROR"], wait=60)
    print("server ACTIVE:", server.id, server.name, server.status)

    conn.compute.set_server_metadata(server, playbook="sdk", env="lab")
    server = conn.compute.get_server(server.id)
    print("metadata:", dict(server.metadata or {}))

    volume = conn.block_storage.create_volume(name="sdk-cookbook-vol", size=5)
    volume = conn.block_storage.wait_for_status(volume, status="available", wait=60)
    print("volume:", volume.id, volume.status)

    conn.compute.delete_server(server, ignore_missing=True)
    print("server deleted")

    conn.block_storage.delete_volume(volume, ignore_missing=True)
    print("volume deleted")

    conn.network.delete_subnet(app_subnet, ignore_missing=True)
    conn.network.delete_network(app_net, ignore_missing=True)
    print("network cleaned")
    print("OPENSTACKSDK_COOKBOOK_OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print("OPENSTACKSDK_COOKBOOK_FAIL:", exc, file=sys.stderr)
        raise
