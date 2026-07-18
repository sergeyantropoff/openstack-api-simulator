#!/usr/bin/env python3
"""Full-surface smoke: Keystone token → every default-port OpenStack service."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

HOST = os.environ.get("OS_HOST", "127.0.0.1")
KEYSTONE = sys.argv[1] if len(sys.argv) > 1 else f"http://{HOST}:5000"


def _u(port: int, path: str) -> str:
    return f"http://{HOST}:{port}{path}"


# (label, url, expected_json_key or None for version-only)
CHECKS: list[tuple[str, str, str | None]] = [
    ("nova.servers", _u(8774, "/v2.1/servers/detail"), "servers"),
    ("nova.flavors", _u(8774, "/v2.1/flavors"), "flavors"),
    ("nova.keypairs", _u(8774, "/v2.1/os-keypairs"), "keypairs"),
    ("nova.az", _u(8774, "/v2.1/os-availability-zone"), "availabilityZoneInfo"),
    ("nova.hypervisors", _u(8774, "/v2.1/os-hypervisors"), "hypervisors"),
    ("neutron.networks", _u(9696, "/v2.0/networks"), "networks"),
    ("neutron.routers", _u(9696, "/v2.0/routers"), "routers"),
    ("neutron.sg", _u(9696, "/v2.0/security-groups"), "security_groups"),
    ("neutron.fips", _u(9696, "/v2.0/floatingips"), "floatingips"),
    ("glance.images", _u(9292, "/v2/images"), "images"),
    ("cinder.volumes", _u(8776, "/v3/volumes/detail"), "volumes"),
    ("placement.rp", _u(8003, "/resource_providers"), "resource_providers"),
    ("heat.stacks", _u(8004, "/v1/demo/stacks"), "stacks"),
    ("swift.info", _u(8080, "/info"), None),
    ("ironic.nodes", _u(6385, "/v1/nodes"), "nodes"),
    ("octavia.lbs", _u(9876, "/v2/lbaas/loadbalancers"), "loadbalancers"),
    ("barbican.secrets", _u(9311, "/v1/secrets"), "secrets"),
    ("manila.shares", _u(8786, "/v2/shares"), "shares"),
    ("designate.zones", _u(9001, "/v2/zones"), "zones"),
    ("magnum.clusters", _u(9511, "/v1/clusters"), "clusters"),
    ("zun.containers", _u(9517, "/v1/containers"), "containers"),
    ("trove.instances", _u(8779, "/v1.0/instances"), "instances"),
    ("mistral.workflows", _u(8989, "/v2/workflows"), "workflows"),
    ("aodh.alarms", _u(8042, "/v2/alarms"), "alarms"),
    ("freezer.jobs", _u(9090, "/v2/jobs"), "jobs"),
    ("blazar.leases", _u(1234, "/leases"), "leases"),
    ("vitrage.alarms", _u(8999, "/v1/alarm"), "alarms"),
    ("masakari.segments", _u(15868, "/v1/segments"), "segments"),
    ("tacker.vnfs", _u(9890, "/v1.0/vnfs"), "vnfs"),
    ("adjutant.tasks", _u(5050, "/v1/tasks"), "tasks"),
    ("cloudkitty.services", _u(8889, "/v1/rating/module_config/hashmap/services"), "services"),
    ("heat-cfn.stacks", _u(8000, "/stacks"), "Stacks"),
]


def request(
    method: str,
    url: str,
    *,
    data: dict | None = None,
    token: str | None = None,
    extra_headers: dict[str, str] | None = None,
):
    body = None if data is None else json.dumps(data).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Auth-Token"] = token
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            raw = res.read().decode()
            return res.status, dict(res.headers), json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, dict(exc.headers), parsed
    except urllib.error.URLError as exc:
        return 0, {}, {"error": str(exc.reason)}


def main() -> int:
    auth = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": "admin",
                        "domain": {"name": "Default"},
                        "password": "secret",
                    }
                },
            },
            "scope": {"project": {"name": "demo", "domain": {"name": "Default"}}},
        }
    }
    status, headers, body = request("POST", f"{KEYSTONE}/v3/auth/tokens", data=auth)
    token = headers.get("X-Subject-Token") or headers.get("x-subject-token")
    print("auth", status, "token", bool(token))
    if status != 201 or not token:
        print(body)
        return 1
    catalog = (body or {}).get("token", {}).get("catalog", [])
    print("catalog_services", len(catalog), sorted(s.get("name") for s in catalog))

    # Microversion header round-trip on Nova
    st, hdrs, _ = request(
        "GET",
        _u(8774, "/v2.1/servers"),
        token=token,
        extra_headers={"OpenStack-API-Version": "compute 2.79"},
    )
    mv = hdrs.get("OpenStack-API-Version") or hdrs.get("openstack-api-version")
    print("nova.microversion", st, mv)
    if st >= 400:
        return 1

    failed = 0
    for label, url, key in CHECKS:
        # Heat needs project id in path — fetch from token
        if label == "heat.stacks":
            project_id = (body or {}).get("token", {}).get("project", {}).get("id")
            if project_id:
                url = _u(8004, f"/v1/{project_id}/stacks")
        st, _, payload = request("GET", url, token=token)
        if key is None:
            print(label, st)
        else:
            items = (payload or {}).get(key)
            count = (
                len(items)
                if isinstance(items, list)
                else ("ok" if items is not None else "missing")
            )
            print(label, st, "count", count)
        if st == 0 or st >= 400:
            print("  FAIL", payload)
            failed += 1

    # Root discovery per port
    for port, name in [(5000, "keystone"), (8774, "nova"), (6385, "ironic"), (8080, "swift")]:
        st, _, payload = request("GET", _u(port, "/"))
        print(f"root.{name}", st, list((payload or {}).keys())[:3])

    if failed:
        print(f"FAILED {failed}/{len(CHECKS)}")
        return 1
    print("OK", len(CHECKS), "service checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
