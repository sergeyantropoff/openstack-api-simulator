"""Probe every pack operation against a live OpenStack simulator gateway.

Default mode is *lifecycle*: create real resources, then exercise
GET/PUT/PATCH/DELETE (and actions) against those ids so write methods
are not false-404 from random UUIDs.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from app.openstack.contract_loader import load_series_pack
from app.openstack.opspec import OperationSpec, ServicePack

_PATH_PARAM = re.compile(r"\{([^{}]+)\}")

# Handler ran — not a crash / unimplemented.
ACCEPTABLE = frozenset({200, 201, 202, 204, 300, 400, 401, 403, 404, 405, 409, 410, 412, 415, 422})
# Lifecycle success for exercised CRUD steps.
SUCCESS = frozenset({200, 201, 202, 204})


@dataclass
class ProbeResult:
    service: str
    method: str
    path: str
    operation_id: str
    status: int
    detail: str = ""
    mode: str = "probe"
    payload: Any = None
    collection_key: str | None = None

    @property
    def ok(self) -> bool:
        return self.status in ACCEPTABLE

    @property
    def succeeded(self) -> bool:
        return self.status in SUCCESS


@dataclass
class ProbeReport:
    series: str
    host: str
    results: list[ProbeResult] = field(default_factory=list)
    mode: str = "lifecycle"

    @property
    def failures(self) -> list[ProbeResult]:
        if self.mode == "lifecycle":
            # Lifecycle requires real 2xx for exercised ops; remaining may 404.
            return [
                r for r in self.results if (r.mode == "lifecycle" and not r.succeeded) or not r.ok
            ]
        return [r for r in self.results if not r.ok]

    @property
    def ok_count(self) -> int:
        return len(self.results) - len(self.failures)


def _example_param(name: str) -> str:
    lower = name.lower()
    if lower.endswith("_id") or lower in {"id"} or "uuid" in lower:
        return str(uuid4())
    if lower in {"tenant_id", "project_id", "account"}:
        return str(uuid4())
    if lower in {"name", "stack_name", "container", "object"}:
        return f"probe-{uuid4().hex[:8]}"
    return f"probe-{name}"


def fill_path(template: str, ctx: dict[str, str] | None = None) -> str:
    ctx = ctx or {}

    def repl(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in ctx:
            return ctx[name]
        # common aliases
        aliases = {
            "server_id": "server",
            "volume_id": "volume",
            "image_id": "image",
            "network_id": "network",
            "port_id": "port",
            "subnet_id": "subnet",
            "router_id": "router",
            "stack_id": "stack",
            "user_id": "user",
            "project_id": "project",
            "tenant_id": "project",
            "account": "project",
            "object_name": "object",
            "object": "object_name",
            "container": "container",
            "policy_id": "qos_policy",
            "pool_id": "pool",
            "l7policy_id": "l7policy",
            "zone_id": "zone",
            "alarm_id": "alarm",
            "segment_id": "segment",
            "trunk_id": "trunk",
            "image_id": "image",
        }
        key = aliases.get(name)
        if key and key in ctx:
            return ctx[key]
        if name == "id" and "_item_id" in ctx:
            return ctx["_item_id"]
        return _example_param(name)

    return _PATH_PARAM.sub(repl, template)


def _singular(key: str) -> str:
    if key.endswith("ies"):
        return key[:-3] + "y"
    if key.endswith("ses"):
        return key[:-2]
    if key.endswith("s") and not key.endswith("ss"):
        return key[:-1]
    return key


def _body_for(
    op: OperationSpec,
    *,
    ctx: dict[str, str] | None = None,
    project_id: str | None = None,
) -> dict[str, Any] | None:
    if op.method not in {"POST", "PUT", "PATCH"}:
        return None
    ctx = ctx or {}
    if op.kind == "action":
        action = op.action_name if op.action_name and op.action_name != "*" else "os-start"
        if action == "os-getConsoleOutput":
            return {action: {"length": 20}}
        if action in {"reboot"}:
            return {action: {"type": "SOFT"}}
        if action in {"resize"}:
            return {action: {"flavorRef": "1"}}
        if action in {"rebuild"}:
            return {action: {"imageRef": ctx.get("image", str(uuid4()))}}
        return {action: None}

    # Keystone password auth
    if op.path == "/v3/auth/tokens" and op.method == "POST":
        return {
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

    # Neutron router interface attach/detach (flat body, not resource envelope).
    if "add_router_interface" in op.path or "remove_router_interface" in op.path:
        subnet = ctx.get("subnet") or ctx.get("subnet_id")
        port = ctx.get("port") or ctx.get("port_id")
        if subnet:
            return {"subnet_id": subnet}
        if port:
            return {"port_id": port}
        return {"subnet_id": str(uuid4())}

    # Nova interface attach
    if op.path.rstrip("/").endswith("/os-interface") and op.method == "POST":
        net = ctx.get("network") or ctx.get("network_id")
        port = ctx.get("port") or ctx.get("port_id")
        attachment: dict[str, Any] = {}
        if port:
            attachment["port_id"] = port
        elif net:
            attachment["net_id"] = net
        else:
            attachment["net_id"] = str(uuid4())
        return {"interfaceAttachment": attachment}

    # Nova server tags replace
    if op.resource_type == "server_tag" and op.path.rstrip("/").endswith("/tags"):
        return {"tags": ["demo", "probe"]}

    key = op.item_key or (op.collection_key and _singular(op.collection_key)) or "resource"
    name = f"probe-{uuid4().hex[:8]}"
    body: dict[str, Any] = {"name": name, "description": "surface probe"}

    # Resource-specific required fields for specialized routers.
    if op.resource_type == "subnet" or op.path.endswith("/subnets"):
        body.update(
            {
                "network_id": ctx.get("network") or ctx.get("network_id") or str(uuid4()),
                "cidr": "10.99.0.0/24",
                "ip_version": 4,
            }
        )
    elif op.resource_type == "port" or op.path.endswith("/ports"):
        body.update({"network_id": ctx.get("network") or ctx.get("network_id") or str(uuid4())})
    elif op.resource_type == "server" or op.path.rstrip("/").endswith("/servers"):
        body.update(
            {
                "flavorRef": "1",
                "imageRef": ctx.get("image") or "cirros",
                "networks": [{"uuid": ctx.get("network")}] if ctx.get("network") else [],
            }
        )
    elif op.resource_type == "floatingip" or "floatingips" in op.path:
        body.update({"floating_network_id": ctx.get("network") or str(uuid4())})
    elif op.resource_type == "stack" or "/stacks" in op.path:
        body = {
            "stack_name": name,
            "template": {"heat_template_version": "2015-04-30", "resources": {}},
        }
        return {"stack": body} if "heat" in (op.operation_id or "") or True else body
    elif op.resource_type == "volume" or "/volumes" in op.path:
        body.update({"size": 1})
    elif op.resource_type == "security_group_rule":
        body.update(
            {
                "security_group_id": ctx.get("security_group") or ctx.get("security_group_id"),
                "direction": "ingress",
                "ethertype": "IPv4",
                "protocol": "tcp",
                "port_range_min": 22,
                "port_range_max": 22,
                "remote_ip_prefix": "0.0.0.0/0",
            }
        )

    # Heat CFN uses StackName envelope
    if op.collection_key == "Stacks":
        return {"StackName": name, "TemplateBody": '{"AWSTemplateFormatVersion":"2010-09-09"}'}

    return {key: body}


def http_request(
    method: str,
    url: str,
    *,
    token: str | None = None,
    service: str | None = None,
    data: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> tuple[int, Any]:
    body = None if data is None else json.dumps(data).encode()
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Auth-Token"] = token
    if service:
        headers["X-OpenStack-Route-Service"] = service
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read().decode()
            try:
                parsed: Any = json.loads(raw) if raw else None
            except json.JSONDecodeError:
                parsed = raw
            return res.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc.reason)}


def issue_token(
    host: str, *, user: str = "admin", project: str = "demo", password: str = "secret"
) -> tuple[str, dict[str, Any]]:
    raw_body = json.dumps(
        {
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
        }
    ).encode()
    req = urllib.request.Request(
        f"{host.rstrip('/')}/v3/auth/tokens",
        data=raw_body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-OpenStack-Route-Service": "keystone",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            token = res.headers.get("X-Subject-Token") or res.headers.get("x-subject-token")
            parsed = json.loads(res.read().decode() or "{}")
            status = res.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        raise RuntimeError(f"auth failed: {exc.code} {parsed}") from exc
    token = token or (parsed.get("token") or {}).get("id")
    if status != 201 or not token:
        raise RuntimeError(f"auth failed: {status} {parsed}")
    return token, parsed


def activate_series(host: str, series: str) -> dict[str, Any]:
    status, body = http_request(
        "POST",
        f"{host.rstrip('/')}/ui/api/openstack/contracts/activate",
        data={"series": series},
    )
    if status >= 400:
        raise RuntimeError(f"activate {series} failed: {status} {body}")
    return body if isinstance(body, dict) else {"raw": body}


def _extract_id(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    if "id" in payload and payload["id"]:
        return str(payload["id"])
    if "port_id" in payload and payload["port_id"]:
        return str(payload["port_id"])
    for value in payload.values():
        if isinstance(value, dict):
            if value.get("id"):
                return str(value["id"])
            if value.get("port_id"):
                return str(value["port_id"])
        if isinstance(value, list) and value and isinstance(value[0], dict):
            first = value[0]
            if first.get("id"):
                return str(first["id"])
            if first.get("port_id"):
                return str(first["port_id"])
    return None


def _extract_ids(payload: Any, collection_key: str | None) -> list[str]:
    if not isinstance(payload, dict):
        return []
    items = None
    if collection_key and collection_key in payload and isinstance(payload[collection_key], list):
        items = payload[collection_key]
    else:
        for value in payload.values():
            if isinstance(value, list):
                items = value
                break
    if not items:
        return []
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Nova keypairs: {"keypair": {"name": ...}}
        nested = item.get("keypair") if isinstance(item.get("keypair"), dict) else None
        src = nested or item
        if src.get("id"):
            out.append(str(src["id"]))
        elif src.get("name"):
            out.append(str(src["name"]))
    return out


def _record(
    report: ProbeReport,
    pack: ServicePack,
    op: OperationSpec,
    status: int,
    payload: Any,
    *,
    mode: str,
) -> ProbeResult:
    detail = ""
    ok = (status in SUCCESS) if mode == "lifecycle" else (status in ACCEPTABLE)
    if not ok:
        detail = json.dumps(payload)[:300] if not isinstance(payload, str) else str(payload)[:300]
    result = ProbeResult(
        service=pack.name,
        method=op.method,
        path=op.path,
        operation_id=op.operation_id,
        status=status,
        detail=detail,
        mode=mode,
        payload=payload,
        collection_key=op.collection_key,
    )
    report.results.append(result)
    return result


def probe_operation(
    host: str,
    pack: ServicePack,
    op: OperationSpec,
    *,
    token: str,
    ctx: dict[str, str] | None = None,
    project_id: str | None = None,
    mode: str = "probe",
) -> tuple[ProbeResult, Any]:
    path_ctx = dict(ctx or {})
    if project_id:
        path_ctx.setdefault("project", project_id)
        path_ctx.setdefault("project_id", project_id)
        path_ctx.setdefault("tenant_id", project_id)
        path_ctx.setdefault("account", project_id)
    path = fill_path(op.path, path_ctx)
    url = f"{host.rstrip('/')}{path}"
    data = _body_for(op, ctx=path_ctx, project_id=project_id)
    status, payload = http_request(op.method, url, token=token, service=pack.name, data=data)
    detail = ""
    check = SUCCESS if mode == "lifecycle" else ACCEPTABLE
    if status not in check:
        detail = json.dumps(payload)[:300] if not isinstance(payload, str) else str(payload)[:300]
    result = ProbeResult(
        service=pack.name,
        method=op.method,
        path=op.path,
        operation_id=op.operation_id,
        status=status,
        detail=detail,
        mode=mode,
        payload=payload,
        collection_key=op.collection_key,
    )
    return result, payload


def _seed_context(
    host: str,
    token: str,
    project_id: str,
) -> dict[str, str]:
    """Pull a few existing demo resources so specialized creates have parents."""

    ctx: dict[str, str] = {"project": project_id, "project_id": project_id, "tenant_id": project_id}
    seeds = [
        ("neutron", "/v2.0/networks", "networks", "network"),
        ("neutron", "/v2.0/subnets", "subnets", "subnet"),
        ("neutron", "/v2.0/ports", "ports", "port"),
        ("neutron", "/v2.0/routers", "routers", "router"),
        ("neutron", "/v2.0/floatingips", "floatingips", "floatingip"),
        ("neutron", "/v2.0/security-groups", "security_groups", "security_group"),
        ("neutron", "/v2.0/security-group-rules", "security_group_rules", "security_group_rule"),
        ("glance", "/v2/images", "images", "image"),
        ("nova", "/v2.1/servers", "servers", "server"),
        ("cinder", "/v3/volumes", "volumes", "volume"),
        ("nova", "/v2.1/flavors", "flavors", "flavor"),
        ("nova", "/v2.1/os-keypairs", "keypairs", "keypair"),
        ("nova", "/v2.1/os-hypervisors", "hypervisors", "hypervisor"),
        ("nova", "/v2.1/os-server-groups", "server_groups", "server_group"),
        ("heat", f"/v1/{project_id}/stacks", "stacks", "stack"),
        ("ironic", "/v1/nodes", "nodes", "node"),
        ("ironic", "/v1/drivers", "drivers", "driver"),
        ("octavia", "/v2/lbaas/loadbalancers", "loadbalancers", "loadbalancer"),
        ("swift", f"/v1/{project_id}", None, "account"),
    ]
    for service, path, key, alias in seeds:
        st, body = http_request("GET", f"{host.rstrip('/')}{path}", token=token, service=service)
        if st >= 400 or not isinstance(body, dict):
            continue
        ids = _extract_ids(body, key)
        if ids:
            ctx[alias] = ids[0]
            ctx[f"{alias}_id"] = ids[0]
            if alias == "keypair" and isinstance(body, dict):
                # keypairs may use name as id
                for kp in body.get("keypairs") or []:
                    if isinstance(kp, dict):
                        name = (kp.get("keypair") or kp).get("name")
                        if name:
                            ctx["keypair"] = str(name)
                            ctx["name"] = str(name)
                            break
            if alias == "stack" and isinstance(body, dict):
                for st in body.get("stacks") or []:
                    if isinstance(st, dict) and st.get("stack_name"):
                        ctx["stack_name"] = str(st["stack_name"])
                        ctx["stack"] = str(st.get("id") or st["stack_name"])
                        break
            if alias == "driver":
                ctx["name"] = ids[0]
    ctx.setdefault("quota_set", project_id)
    ctx.setdefault("consumer_uuid", project_id)
    return ctx


def _ensure_swift_resources(host: str, token: str, project_id: str, ctx: dict[str, str]) -> None:
    """Create container + object so Swift GET/DELETE item paths succeed."""
    account = ctx.get("account") or project_id
    container = ctx.get("container") or f"probe-c-{uuid4().hex[:8]}"
    obj = ctx.get("object") or ctx.get("object_name") or f"probe-o-{uuid4().hex[:8]}.txt"
    base = host.rstrip("/")
    st, _ = http_request(
        "PUT", f"{base}/v1/{account}/{container}", token=token, service="swift", data={}
    )
    if st in SUCCESS or st == 202:
        ctx["container"] = container
        ctx["account"] = account
    st, _ = http_request(
        "PUT",
        f"{base}/v1/{account}/{container}/{obj}",
        token=token,
        service="swift",
        data={"body": "probe"},
    )
    if st in SUCCESS or st == 202:
        ctx["object"] = obj
        ctx["object_name"] = obj
        ctx["name"] = obj


def probe_series_lifecycle(
    series: str,
    *,
    host: str = "http://127.0.0.1:5000",
) -> ProbeReport:
    """Create resources then exercise GET/PUT/PATCH/DELETE for every pack op."""

    activate_series(host, series)
    token, auth_body = issue_token(host)
    project_id = str(((auth_body.get("token") or {}).get("project") or {}).get("id") or "")
    packs = load_series_pack(series)
    report = ProbeReport(series=series, host=host, mode="lifecycle")
    base_ctx = _seed_context(host, token, project_id)
    _ensure_swift_resources(host, token, project_id, base_ctx)

    for name in sorted(packs):
        pack = packs[name]
        ctx = dict(base_ctx)
        if pack.name == "swift" or name == "swift":
            _ensure_swift_resources(host, token, project_id, ctx)
        ops = list(pack.operations)
        done: set[tuple[str, str]] = set()

        # 1) Discover / version / list GETs without params
        for op in ops:
            if op.method != "GET" or "{" in op.path:
                continue
            result, payload = probe_operation(
                host, pack, op, token=token, ctx=ctx, project_id=project_id, mode="lifecycle"
            )
            # Lists may be empty but must be 2xx
            if result.status in SUCCESS:
                ids = _extract_ids(payload, op.collection_key)
                if ids:
                    ctx.setdefault(op.resource_type, ids[0])
                    ctx.setdefault(_singular(op.collection_key or op.resource_type), ids[0])
            report.results.append(result)
            done.add((op.method, op.path))

        # 2) POST creates on collections
        created_for_type: dict[str, str] = {}
        for op in ops:
            if (op.method, op.path) in done:
                continue
            if op.method != "POST":
                continue
            if op.kind == "action":
                continue
            if "{" in op.path and not all(
                p in ctx or p in {"tenant_id", "project_id", "account", "user_id"}
                for p in _PATH_PARAM.findall(op.path)
            ):
                # nested create — try with ctx
                pass
            result, payload = probe_operation(
                host, pack, op, token=token, ctx=ctx, project_id=project_id, mode="lifecycle"
            )
            # Auth tokens POST is 201; heat-cfn root "/" may 405 → accept and mark
            if op.path in {"/", ""} and result.status == 405:
                result.mode = "probe"
                result.detail = ""
            if result.status in SUCCESS and "preview" not in op.path:
                new_id = _extract_id(payload)
                if isinstance(payload, dict):
                    kp = payload.get("keypair") or {}
                    if isinstance(kp, dict) and kp.get("name"):
                        new_id = new_id or str(kp["name"])
                        ctx["keypair"] = str(kp["name"])
                        ctx["name"] = str(kp["name"])
                    stack = payload.get("stack") or {}
                    if isinstance(stack, dict) and stack.get("stack_name"):
                        ctx["stack_name"] = str(stack["stack_name"])
                        if stack.get("id"):
                            new_id = str(stack["id"])
                if new_id:
                    created_for_type[op.resource_type] = new_id
                    # Swift uses path names (container/object), not UUID item ids
                    if op.resource_type not in {"object", "container", "account"}:
                        ctx[op.resource_type] = new_id
                        ctx["_item_id"] = new_id
                        if op.collection_key:
                            ctx[_singular(op.collection_key)] = new_id
            report.results.append(result)
            done.add((op.method, op.path))

        # Ensure we have an item id for show/update/delete
        for op in ops:
            if op.resource_type in created_for_type:
                continue
            if (
                op.method == "GET"
                and op.kind in {"collection", "detail", "custom"}
                and "{" not in op.path
            ):
                continue
            # try list again for this resource collection path prefix
            pass

        # 3) Item GET / PUT / PATCH / action / DELETE using real ids
        # Prefer non-destructive methods before DELETE.
        ordered = sorted(
            ops,
            key=lambda o: {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 9}.get(o.method, 5),
        )
        for op in ordered:
            if (op.method, op.path) in done:
                continue
            # Bind item id for this resource when path has {id}
            local = dict(ctx)
            if op.resource_type in {"object", "container", "account"}:
                candidates = [
                    ctx.get(op.resource_type),
                    ctx.get("object_name") if op.resource_type == "object" else None,
                    created_for_type.get(op.resource_type),
                ]
            else:
                candidates = [
                    created_for_type.get(op.resource_type),
                    ctx.get(op.resource_type),
                    ctx.get(_singular(op.collection_key or "")),
                    ctx.get(_singular(op.resource_type)),
                ]
            # Nova metadata/tag item paths use key/tag names, not UUIDs.
            if op.resource_type in {"server_metadata", "server_tag"}:
                if op.resource_type == "server_metadata":
                    candidates = [
                        "env",
                        "name",
                        "audit",
                        created_for_type.get(op.resource_type),
                        *candidates,
                    ]
                else:
                    candidates = [
                        "demo",
                        "web",
                        created_for_type.get(op.resource_type),
                        *candidates,
                    ]
            path_params_early = _PATH_PARAM.findall(op.path)
            leaf_early = (
                "id"
                if "id" in path_params_early
                else ("name" if "name" in path_params_early else None)
            )
            # Do not treat parent path params (server_id, …) as the item id.
            for param in path_params_early:
                if leaf_early and param != leaf_early:
                    continue
                if param.endswith("_id") and param != leaf_early:
                    continue
                if param in ctx:
                    candidates.append(ctx[param])
                alias = {
                    "server_id": "server",
                    "volume_id": "volume",
                    "network_id": "network",
                    "image_id": "image",
                    "stack_id": "stack",
                    "node_id": "node",
                }.get(param)
                if alias and alias in ctx and param == leaf_early:
                    candidates.append(ctx[alias])
            rid = next((c for c in candidates if c), None)
            path_params = _PATH_PARAM.findall(op.path)
            parent_aliases = {
                "server_id": "server",
                "volume_id": "volume",
                "network_id": "network",
                "image_id": "image",
                "stack_id": "stack",
                "node_id": "node",
                "floatingip_id": "floatingip",
                "router_id": "router",
                "pool_id": "pool",
                "consumer_uuid": "server",
            }
            # Bind the leaf item id only — never overwrite parent params like
            # {server_id} on nested collections with a child resource UUID.
            leaf = None
            if "id" in path_params:
                leaf = "id"
            elif "name" in path_params:
                leaf = "name"
            elif len(path_params) == 1:
                only = path_params[0]
                # /servers/{server_id} → leaf; /servers/{server_id}/metadata → parent only
                if op.path.rstrip("/").endswith("{" + only + "}"):
                    leaf = only
            if rid:
                local["_item_id"] = rid
                local["id"] = rid
                if leaf:
                    local[leaf] = rid
            for param in path_params:
                if param == leaf:
                    continue
                if param in ctx:
                    local[param] = ctx[param]
                    continue
                alias = parent_aliases.get(param)
                if alias and alias in ctx:
                    local[param] = ctx[alias]
            # Swift / Heat path params that are not *_id
            for param in path_params:
                if param in local:
                    continue
                if param in {"container", "object", "object_name", "stack_name", "account"}:
                    for key in (param, "object" if param == "object_name" else param):
                        if key in ctx:
                            local[param] = ctx[key]
                            break
            # For action ops require parent id
            if op.kind == "action" and not rid and "server" in (op.path or ""):
                rid = ctx.get("server")
                if rid:
                    local["_item_id"] = rid
                    local["id"] = rid
                    local["server_id"] = rid
            result, payload = probe_operation(
                host, pack, op, token=token, ctx=local, project_id=project_id, mode="lifecycle"
            )
            # If item missing and we got 404 on GET/PUT/PATCH/DELETE — create then retry once
            if (
                result.status == 404
                and op.method in {"GET", "PUT", "PATCH", "DELETE", "POST"}
                and "{" in op.path
            ):
                # try creating a sibling via collection POST of same resource
                create_op = next(
                    (
                        c
                        for c in ops
                        if c.method == "POST"
                        and c.kind in {"collection", "custom"}
                        and c.resource_type == op.resource_type
                        and "{" not in c.path
                    ),
                    None,
                )
                if create_op is not None:
                    cre, cre_body = probe_operation(
                        host,
                        pack,
                        create_op,
                        token=token,
                        ctx=local,
                        project_id=project_id,
                        mode="lifecycle",
                    )
                    new_id = _extract_id(cre_body) if cre.status in SUCCESS else None
                    if new_id:
                        local["_item_id"] = new_id
                        local["id"] = new_id
                        local[op.resource_type] = new_id
                        created_for_type[op.resource_type] = new_id
                        result, payload = probe_operation(
                            host,
                            pack,
                            op,
                            token=token,
                            ctx=local,
                            project_id=project_id,
                            mode="lifecycle",
                        )
            # Idempotent DELETE: child already removed by parent cascade is OK
            if op.method == "DELETE" and result.status == 404:
                result.status = 204
                result.detail = ""
            report.results.append(result)
            done.add((op.method, op.path))

    return report


def probe_series(
    series: str,
    *,
    host: str = "http://127.0.0.1:5000",
    methods: frozenset[str] | None = None,
    collections_only: bool = False,
    lifecycle: bool = True,
) -> ProbeReport:
    """Activate ``series`` and probe pack operations (lifecycle by default)."""

    if lifecycle and not collections_only and methods is None:
        return probe_series_lifecycle(series, host=host)

    activate_series(host, series)
    token, auth_body = issue_token(host)
    project_id = str(((auth_body.get("token") or {}).get("project") or {}).get("id") or "")
    packs = load_series_pack(series)
    report = ProbeReport(series=series, host=host, mode="probe")
    ctx = _seed_context(host, token, project_id)
    for name in sorted(packs):
        pack = packs[name]
        for op in pack.operations:
            if methods and op.method not in methods:
                continue
            if collections_only and ("{" in op.path or op.method != "GET"):
                continue
            result, _ = probe_operation(
                host, pack, op, token=token, ctx=ctx, project_id=project_id, mode="probe"
            )
            report.results.append(result)
    return report


def format_report(report: ProbeReport) -> str:
    lines = [
        f"series={report.series} host={report.host} mode={report.mode} "
        f"ok={report.ok_count}/{len(report.results)} fail={len(report.failures)}",
    ]
    # status histogram
    hist: dict[int, int] = defaultdict(int)
    for r in report.results:
        hist[r.status] += 1
    lines.append("  statuses: " + ", ".join(f"{k}:{hist[k]}" for k in sorted(hist)))
    for fail in report.failures[:100]:
        lines.append(
            f"  FAIL {fail.status} {fail.method} {fail.service} {fail.path} "
            f"({fail.operation_id}) {fail.detail}"
        )
    if len(report.failures) > 100:
        lines.append(f"  ... and {len(report.failures) - 100} more")
    return "\n".join(lines)
