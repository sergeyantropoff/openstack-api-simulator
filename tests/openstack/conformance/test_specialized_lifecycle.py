"""Specialized IaaS handlers: auth, CRUD read-after-write, Nova actions.

Runs against a live api-gateway after minimal/demo seed. Prefers real service
ports when reachable; falls back to Keystone gateway + X-OpenStack-Route-Service.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            return res.status == 200
    except Exception:
        return False


def _pick_keystone() -> str:
    candidates = [
        os.environ.get("OS_PROBE_HOST"),
        os.environ.get("OS_HOST"),
        "http://127.0.0.1:15000",
        "http://127.0.0.1:5000",
        "http://api-gateway:5000",
        "http://localhost:5000",
    ]
    for host in candidates:
        if not host:
            continue
        base = host.rstrip("/")
        if _probe(f"{base}/health/live") or _probe(f"{base}/v3"):
            return base
    return ""


KEYSTONE = _pick_keystone()

# Real OpenStack default ports (compose publishes 1:1; local override keeps them).
_PORTS = {
    "keystone": 5000,
    "nova": 8774,
    "neutron": 9696,
    "glance": 9292,
    "cinder": 8776,
    "placement": 8003,
    "heat": 8004,
    "swift": 8080,
    "ironic": 6385,
    "octavia": 9876,
}


def _service_base(service: str) -> tuple[str, str | None]:
    """Return (base_url, route_service_header_or_None)."""

    if service == "keystone":
        return KEYSTONE, None
    port = _PORTS[service]
    candidates = [port]
    if service == "swift":
        # Local override often maps Swift to host 18080.
        candidates = [18080, 8080]
    for p in candidates:
        base = f"http://127.0.0.1:{p}"
        # Any HTTP response (incl. 401/404) means the port is published.
        try:
            urllib.request.urlopen(base + "/", timeout=1)
            return base, None
        except urllib.error.HTTPError:
            return base, None
        except Exception:
            continue
    return KEYSTONE, service


@pytest.fixture(scope="module", autouse=True)
def _require_gateway():
    if not KEYSTONE:
        pytest.skip("OpenStack gateway unreachable")


def _request(
    method: str,
    service: str,
    path: str,
    *,
    token: str | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    raw_body: bytes | None = None,
) -> tuple[int, dict[str, str], Any]:
    base, route_svc = _service_base(service)
    body = raw_body
    hdrs = {"Accept": "application/json"}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    if token:
        hdrs["X-Auth-Token"] = token
    if route_svc:
        hdrs["X-OpenStack-Route-Service"] = route_svc
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(f"{base}{path}", data=body, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode()
            try:
                parsed: Any = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            return res.status, {k: v for k, v in res.headers.items()}, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, {k: v for k, v in exc.headers.items()}, parsed


def _auth(
    *,
    user: str = "demo",
    project: str = "demo",
    password: str = "secret",
) -> tuple[str, str, dict[str, Any]]:
    status, headers, body = _request(
        "POST",
        "keystone",
        "/v3/auth/tokens",
        data={
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": user,
                            "domain": {"name": "Default"},
                            "password": password,
                        }
                    },
                },
                "scope": {"project": {"name": project, "domain": {"name": "Default"}}},
            }
        },
    )
    token = headers.get("X-Subject-Token") or headers.get("x-subject-token")
    assert status == 201, (status, body)
    assert token
    project = ((body or {}).get("token") or {}).get("project") or {}
    project_id = str(project.get("id") or "")
    assert project_id
    return token, project_id, body or {}


@pytest.fixture(scope="module")
def auth_ctx() -> tuple[str, str, dict[str, Any]]:
    return _auth()


def test_keystone_token_catalog_ports(auth_ctx: tuple[str, str, dict[str, Any]]) -> None:
    _token, _pid, body = auth_ctx
    catalog = (body.get("token") or {}).get("catalog") or []
    by_type = {e.get("type"): e for e in catalog if isinstance(e, dict)}
    expected = {
        "identity": ":5000",
        "compute": ":8774",
        "network": ":9696",
        "image": ":9292",
        "volumev3": ":8776",
        "placement": ":8003",
        "orchestration": ":8004",
        "object-store": ":8080",
        "baremetal": ":6385",
        "load-balancer": ":9876",
    }
    for typ, port_frag in expected.items():
        entry = by_type.get(typ)
        assert entry, f"missing catalog type {typ}"
        urls = [
            ep.get("url") or ""
            for ep in entry.get("endpoints") or []
            if ep.get("interface") == "public"
        ]
        assert any(port_frag in u for u in urls), (typ, urls)


def test_specialized_lists_nonempty_after_seed(auth_ctx: tuple[str, str, dict[str, Any]]) -> None:
    token, pid, _ = auth_ctx
    checks = [
        ("nova", "/v2.1/servers/detail", "servers", {"OpenStack-API-Version": "compute 2.79"}),
        ("nova", "/v2.1/flavors", "flavors", None),
        ("neutron", "/v2.0/networks", "networks", None),
        ("neutron", "/v2.0/subnets", "subnets", None),
        ("neutron", "/v2.0/floatingips", "floatingips", None),
        ("glance", "/v2/images", "images", None),
        ("cinder", "/v3/volumes/detail", "volumes", None),
        (
            "placement",
            "/resource_providers",
            "resource_providers",
            {"OpenStack-API-Version": "placement 1.39"},
        ),
        ("heat", f"/v1/{pid}/stacks", "stacks", None),
        ("octavia", "/v2/lbaas/loadbalancers", "loadbalancers", None),
        ("ironic", "/v1/nodes", "nodes", {"OpenStack-API-Version": "baremetal 1.90"}),
    ]
    for service, path, key, hdrs in checks:
        status, _, body = _request("GET", service, path, token=token, headers=hdrs)
        assert status == 200, (service, path, status, body)
        items = (body or {}).get(key)
        assert isinstance(items, list) and len(items) >= 1, (service, path, key, body)

    status, _, body = _request("GET", "swift", f"/v1/AUTH_{pid}", token=token)
    assert status == 200
    assert isinstance(body, list) and len(body) >= 1


def test_nova_server_crud_and_actions(auth_ctx: tuple[str, str, dict[str, Any]]) -> None:
    token, _pid, _ = auth_ctx
    mv = {"OpenStack-API-Version": "compute 2.79"}
    st, _, flavors = _request("GET", "nova", "/v2.1/flavors", token=token)
    st, _, images = _request("GET", "glance", "/v2/images", token=token)
    st, _, nets = _request("GET", "neutron", "/v2.0/networks", token=token)
    flavor = (flavors or {}).get("flavors") or [{}]
    image = (images or {}).get("images") or [{}]
    networks = (nets or {}).get("networks") or [{}]
    # Prefer tenant demo-net over shared public for boot.
    net = next((n for n in networks if n.get("name") == "demo-net"), networks[0])
    name = f"lc-{uuid.uuid4().hex[:8]}"
    st, _, created = _request(
        "POST",
        "nova",
        "/v2.1/servers",
        token=token,
        headers=mv,
        data={
            "server": {
                "name": name,
                "flavorRef": flavor[0]["id"],
                "imageRef": image[0]["id"],
                "networks": [{"uuid": net["id"]}],
            }
        },
    )
    assert st == 202, created
    sid = (created or {}).get("server", {}).get("id")
    assert sid
    st, _, shown = _request("GET", "nova", f"/v2.1/servers/{sid}", token=token, headers=mv)
    assert st == 200
    assert shown["server"]["name"] == name

    st, _, _ = _request(
        "PUT",
        "nova",
        f"/v2.1/servers/{sid}",
        token=token,
        headers=mv,
        data={"server": {"name": f"{name}-ren"}},
    )
    assert st == 200

    for action, expect in (
        ({"os-stop": None}, "SHUTOFF"),
        ({"os-start": None}, "ACTIVE"),
        ({"reboot": {"type": "SOFT"}}, "ACTIVE"),
        ({"suspend": None}, "SUSPENDED"),
        ({"resume": None}, "ACTIVE"),
        ({"pause": None}, "PAUSED"),
        ({"unpause": None}, "ACTIVE"),
        ({"shelve": None}, "SHELVED"),
        ({"shelveOffload": None}, "SHELVED_OFFLOADED"),
        ({"unshelve": None}, "ACTIVE"),
    ):
        st, _, _ = _request(
            "POST",
            "nova",
            f"/v2.1/servers/{sid}/action",
            token=token,
            headers=mv,
            data=action,
        )
        assert st == 202, action
        st, _, shown = _request("GET", "nova", f"/v2.1/servers/{sid}", token=token, headers=mv)
        assert shown["server"]["status"] == expect, (action, shown["server"]["status"])

    st, _, _ = _request("DELETE", "nova", f"/v2.1/servers/{sid}", token=token, headers=mv)
    assert st == 204
    st, _, _ = _request("GET", "nova", f"/v2.1/servers/{sid}", token=token, headers=mv)
    assert st == 404


def test_neutron_network_subnet_port_fip_crud(
    auth_ctx: tuple[str, str, dict[str, Any]],
) -> None:
    token, _pid, _ = auth_ctx
    tag = uuid.uuid4().hex[:8]
    st, _, created = _request(
        "POST",
        "neutron",
        "/v2.0/networks",
        token=token,
        data={"network": {"name": f"n-{tag}", "admin_state_up": True}},
    )
    assert st == 201
    nid = created["network"]["id"]
    st, _, sub = _request(
        "POST",
        "neutron",
        "/v2.0/subnets",
        token=token,
        data={
            "subnet": {
                "name": f"s-{tag}",
                "network_id": nid,
                "cidr": "10.210.0.0/24",
                "ip_version": 4,
            }
        },
    )
    assert st == 201
    sid = sub["subnet"]["id"]
    st, _, port = _request(
        "POST",
        "neutron",
        "/v2.0/ports",
        token=token,
        data={"port": {"name": f"p-{tag}", "network_id": nid}},
    )
    assert st == 201
    pid = port["port"]["id"]

    st, _, nets = _request("GET", "neutron", "/v2.0/networks", token=token)
    assert any(n.get("id") == nid for n in nets.get("networks") or [])
    public = next(n for n in nets["networks"] if n.get("name") == "public")
    assert public.get("router:external") is True

    st, _, fip = _request(
        "POST",
        "neutron",
        "/v2.0/floatingips",
        token=token,
        data={"floatingip": {"floating_network_id": public["id"]}},
    )
    assert st == 201
    fid = fip["floatingip"]["id"]
    st, _, shown = _request("GET", "neutron", f"/v2.0/floatingips/{fid}", token=token)
    assert st == 200
    assert shown["floatingip"]["id"] == fid

    st, _, _ = _request("DELETE", "neutron", f"/v2.0/floatingips/{fid}", token=token)
    assert st == 204
    st, _, _ = _request("DELETE", "neutron", f"/v2.0/ports/{pid}", token=token)
    assert st == 204
    st, _, _ = _request("DELETE", "neutron", f"/v2.0/subnets/{sid}", token=token)
    assert st == 204
    st, _, _ = _request("DELETE", "neutron", f"/v2.0/networks/{nid}", token=token)
    assert st == 204
    st, _, _ = _request("GET", "neutron", f"/v2.0/networks/{nid}", token=token)
    assert st == 404


def test_glance_cinder_heat_octavia_ironic_swift_crud(
    auth_ctx: tuple[str, str, dict[str, Any]],
) -> None:
    token, project_id, _ = auth_ctx
    tag = uuid.uuid4().hex[:8]

    st, _, img = _request(
        "POST",
        "glance",
        "/v2/images",
        token=token,
        data={"name": f"img-{tag}", "container_format": "bare", "disk_format": "qcow2"},
    )
    assert st == 201
    iid = img["id"]
    st, _, shown = _request("GET", "glance", f"/v2/images/{iid}", token=token)
    assert st == 200 and shown["id"] == iid
    st, _, _ = _request("DELETE", "glance", f"/v2/images/{iid}", token=token)
    assert st == 204

    st, _, vol = _request(
        "POST",
        "cinder",
        "/v3/volumes",
        token=token,
        data={"volume": {"size": 1, "name": f"vol-{tag}"}},
    )
    assert st == 202
    vid = vol["volume"]["id"]
    st, _, shown = _request("GET", "cinder", f"/v3/volumes/{vid}", token=token)
    assert st == 200 and shown["volume"]["id"] == vid
    st, _, _ = _request(
        "PUT",
        "cinder",
        f"/v3/volumes/{vid}",
        token=token,
        data={"volume": {"name": f"vol-{tag}-ren", "description": "lc"}},
    )
    assert st == 200
    st, _, _ = _request("DELETE", "cinder", f"/v3/volumes/{vid}", token=token)
    assert st == 202
    st, _, _ = _request("GET", "cinder", f"/v3/volumes/{vid}", token=token)
    assert st == 404

    st, _, stack = _request(
        "POST",
        "heat",
        f"/v1/{project_id}/stacks",
        token=token,
        data={
            "stack_name": f"stk-{tag}",
            "template": {"heat_template_version": "2015-04-30", "resources": {}},
        },
    )
    assert st == 201
    sid = stack["stack"]["id"]
    sname = stack["stack"]["stack_name"]
    st, _, _ = _request(
        "PUT",
        "heat",
        f"/v1/{project_id}/stacks/{sname}/{sid}",
        token=token,
        data={
            "template": {
                "heat_template_version": "2015-04-30",
                "description": "upd",
                "resources": {},
            },
            "description": "updated",
        },
    )
    assert st == 200
    st, _, shown = _request("GET", "heat", f"/v1/{project_id}/stacks/{sname}/{sid}", token=token)
    assert st == 200
    assert shown["stack"]["stack_status"] == "UPDATE_COMPLETE"
    st, _, _ = _request("DELETE", "heat", f"/v1/{project_id}/stacks/{sname}/{sid}", token=token)
    assert st == 204

    st, _, subs = _request("GET", "neutron", "/v2.0/subnets", token=token)
    sub_id = (subs.get("subnets") or [{}])[0].get("id")
    assert sub_id
    st, _, lb = _request(
        "POST",
        "octavia",
        "/v2/lbaas/loadbalancers",
        token=token,
        data={"loadbalancer": {"name": f"lb-{tag}", "vip_subnet_id": sub_id}},
    )
    assert st == 201
    lbid = lb["loadbalancer"]["id"]
    st, _, _ = _request(
        "PUT",
        "octavia",
        f"/v2/lbaas/loadbalancers/{lbid}",
        token=token,
        data={"loadbalancer": {"name": f"lb-{tag}-ren"}},
    )
    assert st == 200
    st, _, _ = _request("DELETE", "octavia", f"/v2/lbaas/loadbalancers/{lbid}", token=token)
    assert st == 204
    st, _, _ = _request("GET", "octavia", f"/v2/lbaas/loadbalancers/{lbid}", token=token)
    assert st == 404

    st, _, node = _request(
        "POST",
        "ironic",
        "/v1/nodes",
        token=token,
        headers={"OpenStack-API-Version": "baremetal 1.90"},
        data={"name": f"node-{tag}", "driver": "ipmi"},
    )
    assert st == 201
    nuid = node["uuid"]
    st, _, _ = _request(
        "PUT",
        "ironic",
        f"/v1/nodes/{nuid}/states/power",
        token=token,
        headers={"OpenStack-API-Version": "baremetal 1.90"},
        data={"target": "power on"},
    )
    assert st == 202
    st, _, shown = _request(
        "GET",
        "ironic",
        f"/v1/nodes/{nuid}",
        token=token,
        headers={"OpenStack-API-Version": "baremetal 1.90"},
    )
    assert shown.get("power_state") == "power on"
    st, _, _ = _request(
        "DELETE",
        "ironic",
        f"/v1/nodes/{nuid}",
        token=token,
        headers={"OpenStack-API-Version": "baremetal 1.90"},
    )
    assert st == 204

    acct = f"AUTH_{project_id}"
    cname = f"c-{tag}"
    st, _, _ = _request("PUT", "swift", f"/v1/{acct}/{cname}", token=token)
    assert st == 201
    st, _, _ = _request(
        "PUT",
        "swift",
        f"/v1/{acct}/{cname}/hello.txt",
        token=token,
        headers={"Content-Type": "text/plain"},
        raw_body=b"hello",
    )
    assert st == 201
    st, _, obj = _request("GET", "swift", f"/v1/{acct}/{cname}/hello.txt", token=token)
    assert st == 200
    st, _, _ = _request("DELETE", "swift", f"/v1/{acct}/{cname}/hello.txt", token=token)
    assert st == 204
    st, _, _ = _request("DELETE", "swift", f"/v1/{acct}/{cname}", token=token)
    assert st == 204
    st, _, containers = _request("GET", "swift", f"/v1/{acct}", token=token)
    assert st == 200
    assert not any(c.get("name") == cname for c in containers or [])


def test_project_scoped_token_required_for_nova() -> None:
    status, headers, body = _request(
        "POST",
        "keystone",
        "/v3/auth/tokens",
        data={
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": "demo",
                            "domain": {"name": "Default"},
                            "password": "secret",
                        }
                    },
                }
            }
        },
    )
    token = headers.get("X-Subject-Token") or headers.get("x-subject-token")
    assert status == 201 and token
    st, _, err = _request("GET", "nova", "/v2.1/servers", token=token)
    assert st in {401, 403}
    assert isinstance(err, dict)
