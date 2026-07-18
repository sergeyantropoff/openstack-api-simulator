"""Live gateway tests: real DB-backed GET/PUT/POST/DELETE after demo seed."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import pytest

pytestmark = pytest.mark.integration


def _pick_host() -> str:
    candidates = [
        os.environ.get("OS_PROBE_HOST"),
        os.environ.get("OS_HOST"),
        "http://127.0.0.1:5000",
        "http://api-gateway:5000",
        "http://localhost:5000",
    ]
    for host in candidates:
        if not host:
            continue
        try:
            with urllib.request.urlopen(f"{host.rstrip('/')}/health/live", timeout=3) as res:
                if res.status == 200:
                    return host.rstrip("/")
        except Exception:
            continue
    return ""


HOST = _pick_host()


@pytest.fixture(scope="module", autouse=True)
def _require_gateway():
    if not HOST:
        pytest.skip("OpenStack gateway unreachable")


def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    service: str | None = None,
    data: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    body = None if data is None else json.dumps(data).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Auth-Token"] = token
    if service:
        headers["X-OpenStack-Route-Service"] = service
    req = urllib.request.Request(f"{HOST}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read().decode()
            return res.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed


def _auth() -> tuple[str, str]:
    status, body = _request(
        "POST",
        "/v3/auth/tokens",
        service="keystone",
        data={
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
        },
    )
    # urllib may not expose subject token via our helper — re-auth with headers
    payload = json.dumps(
        {
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
    ).encode()
    req = urllib.request.Request(
        f"{HOST}/v3/auth/tokens",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-OpenStack-Route-Service": "keystone",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        token = res.headers.get("X-Subject-Token") or res.headers.get("x-subject-token")
        parsed = json.loads(res.read().decode() or "{}")
    assert token, (status, body)
    project_id = str(((parsed.get("token") or {}).get("project") or {}).get("id") or "")
    assert project_id
    return token, project_id


@pytest.fixture(scope="module")
def auth_ctx():
    # Ensure demo inventory is present for density assertions.
    from app.openstack.surface_probe import http_request

    http_request("POST", f"{HOST}/ui/api/demo/load", data={})
    return _auth()


def test_demo_collections_have_real_density(auth_ctx: tuple[str, str]) -> None:
    token, _pid = auth_ctx
    expectations = [
        ("nova", "/v2.1/servers", "servers", 50),
        ("nova", "/v2.1/flavors", "flavors", 4),
        ("nova", "/v2.1/os-keypairs", "keypairs", 3),
        ("nova", "/v2.1/os-server-groups", "server_groups", 4),
        ("neutron", "/v2.0/networks", "networks", 3),
        ("neutron", "/v2.0/subnets", "subnets", 3),
        ("neutron", "/v2.0/routers", "routers", 2),
        ("neutron", "/v2.0/security-groups", "security_groups", 3),
        ("neutron", "/v2.0/ports", "ports", 50),
        ("neutron", "/v2.0/quotas", "quotas", 1),
        ("glance", "/v2/images", "images", 2),
        (
            "cinder",
            "/v3/volumes/detail",
            "volumes",
            20,
        ),  # project-scoped list also on /v3/{pid}/...
        ("placement", "/resource_providers", "resource_providers", 4),
        ("octavia", "/v2/lbaas/providers", "providers", 3),
        ("octavia", "/v2/lbaas/loadbalancers", "loadbalancers", 1),
        ("barbican", "/v1/secrets", "secrets", 4),
        ("heat", f"/v1/{_pid}/stacks", "stacks", 1),
        ("heat", f"/v1/{_pid}/software_configs", "software_configs", 4),
        ("heat", f"/v1/{_pid}/software_deployments", "software_deployments", 4),
    ]
    for service, path, key, minimum in expectations:
        status, body = _request("GET", path, token=token, service=service)
        assert status == 200, (service, path, status, body)
        assert isinstance(body, dict), (service, path, body)
        items = body.get(key)
        assert isinstance(items, list), (service, path, key, body)
        assert len(items) >= minimum, f"{service} {path} {key}: got {len(items)} < {minimum}"


def test_network_crud_persists_in_db(auth_ctx: tuple[str, str]) -> None:
    token, _pid = auth_ctx
    name = "real-db-net"
    status, created = _request(
        "POST",
        "/v2.0/networks",
        token=token,
        service="neutron",
        data={"network": {"name": name, "admin_state_up": True}},
    )
    assert status in {200, 201}, created
    net_id = (created or {}).get("network", {}).get("id")
    assert net_id

    status, shown = _request("GET", f"/v2.0/networks/{net_id}", token=token, service="neutron")
    assert status == 200
    assert shown["network"]["name"] == name

    status, updated = _request(
        "PUT",
        f"/v2.0/networks/{net_id}",
        token=token,
        service="neutron",
        data={"network": {"name": f"{name}-upd"}},
    )
    assert status == 200
    assert updated["network"]["name"] == f"{name}-upd"

    status, listed = _request("GET", "/v2.0/networks", token=token, service="neutron")
    assert status == 200
    names = {n.get("name") for n in listed.get("networks") or []}
    assert f"{name}-upd" in names

    status, _ = _request("DELETE", f"/v2.0/networks/{net_id}", token=token, service="neutron")
    assert status in {200, 202, 204}
    status, _ = _request("GET", f"/v2.0/networks/{net_id}", token=token, service="neutron")
    assert status == 404


def test_server_metadata_persists_roundtrip(auth_ctx: tuple[str, str]) -> None:
    token, _pid = auth_ctx
    status, servers = _request("GET", "/v2.1/servers", token=token, service="nova")
    assert status == 200
    server_id = (servers.get("servers") or [{}])[0].get("id")
    assert server_id

    status, _ = _request(
        "POST",
        f"/v2.1/servers/{server_id}/metadata",
        token=token,
        service="nova",
        data={"metadata": {"audit": "yes", "tier": "web"}},
    )
    assert status in {200, 201}

    status, meta = _request(
        "GET", f"/v2.1/servers/{server_id}/metadata", token=token, service="nova"
    )
    assert status == 200
    assert meta["metadata"].get("audit") == "yes"
    assert meta["metadata"].get("tier") == "web"

    status, _ = _request(
        "PUT",
        f"/v2.1/servers/{server_id}/tags",
        token=token,
        service="nova",
        data={"tags": ["audit", "web", "demo"]},
    )
    assert status in {200, 201}
    status, tags = _request("GET", f"/v2.1/servers/{server_id}/tags", token=token, service="nova")
    assert status == 200
    assert set(tags.get("tags") or []) >= {"audit", "web", "demo"}


def test_schema_secret_crud_persists(auth_ctx: tuple[str, str]) -> None:
    token, _pid = auth_ctx
    status, created = _request(
        "POST",
        "/v1/secrets",
        token=token,
        service="barbican",
        data={"name": "real-db-secret", "secret_type": "passphrase"},
    )
    assert status in {200, 201}, created
    secret_id = None
    if isinstance(created, dict):
        secret_id = created.get("id") or (created.get("secret") or {}).get("id")
        ref = created.get("secret_ref")
        if not secret_id and isinstance(ref, str):
            secret_id = ref.rstrip("/").split("/")[-1]
    assert secret_id

    status, shown = _request("GET", f"/v1/secrets/{secret_id}", token=token, service="barbican")
    assert status == 200
    body = shown.get("secret") if isinstance(shown, dict) and "secret" in shown else shown
    assert isinstance(body, dict)
    assert body.get("name") == "real-db-secret" or body.get("id") == secret_id

    status, listed = _request("GET", "/v1/secrets", token=token, service="barbican")
    assert status == 200
    ids = []
    for item in listed.get("secrets") or []:
        if isinstance(item, dict):
            ids.append(str(item.get("id") or ""))
            href = item.get("secret_ref") or item.get("href")
            if isinstance(href, str):
                ids.append(href.rstrip("/").split("/")[-1])
    assert secret_id in ids

    status, _ = _request("DELETE", f"/v1/secrets/{secret_id}", token=token, service="barbican")
    assert status in {200, 202, 204}
    status, _ = _request("GET", f"/v1/secrets/{secret_id}", token=token, service="barbican")
    assert status == 404


def test_nested_demo_resources_populated(auth_ctx: tuple[str, str]) -> None:
    token, pid = auth_ctx
    status, servers = _request("GET", "/v2.1/servers", token=token, service="nova")
    sid = (servers.get("servers") or [{}])[0].get("id")
    status, routers = _request("GET", "/v2.0/routers", token=token, service="neutron")
    rid = (routers.get("routers") or [{}])[0].get("id")
    status, fips = _request("GET", "/v2.0/floatingips", token=token, service="neutron")
    fid = (fips.get("floatingips") or [{}])[0].get("id")
    status, images = _request("GET", "/v2/images", token=token, service="glance")
    iid = (images.get("images") or [{}])[0].get("id")
    assert all([sid, rid, fid, iid])

    checks = [
        ("nova", f"/v2.1/servers/{sid}/os-volume_attachments", "volumeAttachments", 1),
        ("nova", f"/v2.1/servers/{sid}/os-interface", "interfaceAttachments", 1),
        ("nova", f"/v2.1/servers/{sid}/metadata", "metadata", 1),
        ("nova", f"/v2.1/servers/{sid}/tags", "tags", 1),
        ("neutron", f"/v2.0/routers/{rid}/conntrack_helpers", "conntrack_helpers", 4),
        ("neutron", f"/v2.0/floatingips/{fid}/port_forwardings", "port_forwardings", 4),
        ("glance", f"/v2/images/{iid}/members", "members", 4),
        ("placement", f"/allocations/{sid}", "allocations", 1),
        ("heat", f"/v1/{pid}/software_deployments", "software_deployments", 4),
    ]
    for service, path, key, minimum in checks:
        status, body = _request("GET", path, token=token, service=service)
        assert status == 200, (path, status, body)
        val = body.get(key)
        if isinstance(val, dict):
            assert len(val) >= minimum, (path, key, val)
        else:
            assert isinstance(val, list) and len(val) >= minimum, (path, key, val)
