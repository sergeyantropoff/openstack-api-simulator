#!/usr/bin/env python3
"""Write-path conformance sample: create → show → delete across core services."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from uuid import uuid4

HOST = os.environ.get("OS_HOST", "127.0.0.1")
KEYSTONE = sys.argv[1] if len(sys.argv) > 1 else f"http://{HOST}:5000"


def _u(port: int, path: str) -> str:
    return f"http://{HOST}:{port}{path}"


def request(method: str, url: str, *, data: dict | None = None, token: str | None = None):
    body = None if data is None else json.dumps(data).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Auth-Token"] = token
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
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
    # Allow full URL host override via argv keystone URL.
    global HOST
    if KEYSTONE.startswith("http"):
        # http://api-gateway:5000 → api-gateway
        from urllib.parse import urlparse

        parsed = urlparse(KEYSTONE)
        if parsed.hostname:
            HOST = parsed.hostname

    auth = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {"name": "admin", "domain": {"name": "Default"}, "password": "secret"}
                },
            },
            "scope": {"project": {"name": "demo", "domain": {"name": "Default"}}},
        }
    }
    status, headers, body = request("POST", f"{KEYSTONE.rstrip('/')}/v3/auth/tokens", data=auth)
    token = headers.get("X-Subject-Token") or headers.get("x-subject-token")
    if not token and isinstance(body, dict):
        token = (body.get("token") or {}).get("id")
    if status != 201 or not token:
        print("auth failed", status, body)
        return 1
    project_id = (body or {}).get("token", {}).get("project", {}).get("id")
    failed = 0

    name = f"conf-{uuid4().hex[:8]}"
    st, _, created = request(
        "POST",
        _u(9311, "/v1/secrets"),
        token=token,
        data={"secret": {"name": name, "payload_content_type": "text/plain"}},
    )
    print("barbican.create", st)
    sid = ((created or {}).get("secret") or {}).get("id")
    if st >= 400 or not sid:
        failed += 1
    else:
        st, _, _ = request("GET", _u(9311, f"/v1/secrets/{sid}"), token=token)
        print("barbican.show", st)
        if st >= 400:
            failed += 1
        st, _, _ = request("DELETE", _u(9311, f"/v1/secrets/{sid}"), token=token)
        print("barbican.delete", st)
        if st >= 400 and st != 204:
            failed += 1

    st, _, sgs = request("GET", _u(9696, "/v2.0/security-groups"), token=token)
    sg_id = ((sgs or {}).get("security_groups") or [{}])[0].get("id")
    if sg_id:
        st, _, rule = request(
            "POST",
            _u(9696, "/v2.0/security-group-rules"),
            token=token,
            data={
                "security_group_rule": {
                    "security_group_id": sg_id,
                    "direction": "ingress",
                    "protocol": "tcp",
                    "port_range_min": 8080,
                    "port_range_max": 8080,
                    "ethertype": "IPv4",
                    "remote_ip_prefix": "0.0.0.0/0",
                }
            },
        )
        print(
            "neutron.sg_rule.create", st, ((rule or {}).get("security_group_rule") or {}).get("id")
        )
        if st >= 400:
            failed += 1

    st, _, servers = request("GET", _u(8774, "/v2.1/servers"), token=token)
    server_id = ((servers or {}).get("servers") or [{}])[0].get("id")
    if server_id:
        req = urllib.request.Request(
            _u(8774, f"/v2.1/servers/{server_id}/action"),
            data=json.dumps({"os-getConsoleOutput": {"length": 20}}).encode(),
            headers={
                "Content-Type": "application/json",
                "X-Auth-Token": token,
                "OpenStack-API-Version": "compute 2.79",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                print("nova.console", res.status)
        except urllib.error.HTTPError as exc:
            print("nova.console", exc.code)
            failed += 1

    if project_id:
        st, _, stacks = request("GET", _u(8004, f"/v1/{project_id}/stacks"), token=token)
        print("heat.stacks", st, len((stacks or {}).get("stacks") or []))
        if st >= 400:
            failed += 1

    st, _, contracts = request("GET", _u(5000, "/ui/api/openstack/contracts"))
    print("ui.contracts", st, (contracts or {}).get("active", {}).get("operation_count"))
    if st != 200 or not (contracts or {}).get("active", {}).get("operation_count"):
        failed += 1

    if failed:
        print(f"FAILED checks={failed}")
        return 1
    print("OK conformance write-paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
