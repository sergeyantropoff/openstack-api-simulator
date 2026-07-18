"""Rewrite incoming requests onto /_os/<service>/… based on gateway port/header.

All OpenStack service routers are mounted under /_os/<service> so that
overlapping paths (/v3 for Keystone vs Cinder, /v1 for Heat vs Swift, …)
do not collide inside a single FastAPI process.

When the browser UI is served from the Keystone port (5000), relative fetches
like ``/v2.1/servers`` still arrive with ``X-OpenStack-Service: keystone``.
In that case we re-resolve the target service from the URL path (or from
``X-OpenStack-Route-Service`` set by the console).
"""

from __future__ import annotations

import re

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.openstack.surface import SERVICES

_PORT_TO_SERVICE = {spec.port: spec.name for spec in SERVICES}

_SKIP_PREFIXES = (
    "/_os/",
    "/api2",
    "/docs",
    "/redoc",
    "/openapi",
    "/health",
    "/metrics",
    "/static",
    "/ui",
    "/favicon",
    "/assets",
    "/console",
)

_AMBIGUOUS_SERVICES = frozenset({"", "keystone", "horizon", "simulator", "https"})

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

_KEYSTONE_V3_ROOTS = frozenset(
    {
        "auth",
        "users",
        "groups",
        "projects",
        "domains",
        "roles",
        "regions",
        "services",
        "endpoints",
        "credentials",
        "policies",
        "role_assignments",
        "OS-INHERIT",
        "OS-FEDERATION",
        "OS-TRUST",
        "OS-EP-FILTER",
        "OS-OAUTH1",
        "OS-SIMPLE-CERT",
        "OS-EC2",
        "application_credentials",
        "system",
        "limits",
        "registered_limits",
        "project_tags",
    }
)

_CINDER_V3_ROOTS = frozenset(
    {
        "volumes",
        "snapshots",
        "backups",
        "types",
        "qos-specs",
        "groups",
        "group_snapshots",
        "consistencygroups",
        "attachments",
        "volume-transfers",
        "os-services",
        "os-quota-sets",
        "clusters",
        "messages",
        "resource_filters",
        "scheduler-stats",
    }
)

_GLANCE_V2_ROOTS = frozenset({"images", "schemas", "metadefs", "tasks", "info"})
_MANILA_V2_ROOTS = frozenset(
    {
        "shares",
        "snapshots",
        "share-networks",
        "share-servers",
        "share-groups",
        "security-services",
        "types",
        "share-replicas",
    }
)
_DESIGNATE_V2_ROOTS = frozenset(
    {"zones", "tlds", "blacklists", "pools", "service_statuses", "tsigkeys", "reverse"}
)


def resolve_service_from_path(path: str) -> str | None:
    """Map an absolute OpenStack API path to a service name."""

    p = (path or "/").split("?", 1)[0]
    if not p.startswith("/"):
        p = f"/{p}"

    if p.startswith("/v2.1"):
        return "nova"
    if p.startswith("/v2.0"):
        return "neutron"

    if p.startswith("/resource_providers") or p.startswith("/resource_classes"):
        return "placement"
    if p.startswith("/allocation_candidates") or p.startswith("/allocations"):
        return "placement"
    if p.startswith("/traits") or p.startswith("/usages"):
        return "placement"

    if p.startswith("/v2/lbaas") or p.startswith("/v2/octavia"):
        return "octavia"

    if p.startswith("/v2/"):
        root = p.split("/", 3)[2] if p.count("/") >= 2 else ""
        if root in _GLANCE_V2_ROOTS:
            return "glance"
        if root in _MANILA_V2_ROOTS:
            return "manila"
        if root in _DESIGNATE_V2_ROOTS:
            return "designate"
        # Default glance for bare /v2/
        return "glance"

    if p.startswith("/v3"):
        parts = [seg for seg in p.split("/") if seg]
        if len(parts) == 1:
            return "keystone"
        root = parts[1]
        if root in _KEYSTONE_V3_ROOTS or root.startswith("OS-"):
            return "keystone"
        if root in _CINDER_V3_ROOTS:
            return "cinder"
        # /v3/{project_id}/volumes|…
        if _UUID_RE.match(root) and len(parts) >= 3 and parts[2] in _CINDER_V3_ROOTS | {"limits"}:
            return "cinder"
        return "keystone"

    if p.startswith("/info") or p.startswith("/v1/AUTH_"):
        return "swift"
    if p == "/stacks" or p.startswith("/stacks"):
        return "heat-cfn"

    if p.startswith("/v1/"):
        parts = [seg for seg in p.split("/") if seg]
        root = parts[1] if len(parts) > 1 else ""
        if root in {
            "nodes",
            "drivers",
            "chassis",
            "portgroups",
            "conductors",
            "allocations",
            "deploy_templates",
        }:
            return "ironic"
        if root in {"ports", "volume"} and (
            len(parts) > 2 or root == "volume" or "portgroups" in p
        ):
            # /v1/ports is ironic; avoid stealing neutron
            return "ironic"
        if root in {"secrets", "containers", "orders", "secret-stores"}:
            return "barbican"
        if root in {"clusters", "clustertemplates", "certificates", "mservices"}:
            return "magnum"
        if root in {"containers", "services", "hosts", "capsules"} and "magnum" not in root:
            if root == "containers":
                return "zun"
        if root in {"instances", "datastores", "configurations", "backups"}:
            return "trove"
        if root in {"jobs", "clients", "actions", "sessions"}:
            return "freezer"
        if (
            "stacks" in parts
            or "software_configs" in parts
            or "software_deployments" in parts
            or "resource_types" in parts
        ):
            return "heat"
        if root.startswith("AUTH_") or (len(parts) >= 2 and parts[1].startswith("AUTH_")):
            return "swift"
        # Heat style /v1/{tenant}/stacks
        if len(parts) >= 3 and parts[2] == "stacks":
            return "heat"
        if root in {"workflows", "actions", "executions", "workbooks", "cron_triggers"}:
            return "mistral"
        if root in {"alarms", "alarm"}:
            return "aodh"
        if root in {"leases", "hosts", "floatingips"}:
            return "blazar"
        if root in {"segments", "notifications", "hosts"}:
            return "masakari"
        if root in {"vnfs", "vnffgs", "vim", "nsds"}:
            return "tacker"
        if root in {"tasks", "tokens", "status"}:
            return "adjutant"
        if root in {"rating", "collect", "storage", "info"}:
            return "cloudkitty"

    if p.startswith("/v2/alarms") or p.startswith("/v2/query"):
        return "aodh"
    if p.startswith("/v2/workflows") or p.startswith("/v2/executions"):
        return "mistral"
    if p.startswith("/v1.0/"):
        return "trove"
    if p.startswith("/leases"):
        return "blazar"

    return None


def resolve_service(headers: dict[str, str], path: str | None = None) -> str | None:
    path_service = resolve_service_from_path(path or "") if path else None

    # Identity auth must never be stolen by a stale UI route-service header.
    if path and (path.startswith("/v3/auth") or path == "/v3" or path == "/v3/"):
        return "keystone"

    route = (headers.get("x-openstack-route-service") or "").lower().strip()
    if route and route not in _AMBIGUOUS_SERVICES:
        return route

    header = (headers.get("x-openstack-service") or "").lower().strip()
    port_raw = headers.get("x-forwarded-port") or ""
    try:
        port_service = _PORT_TO_SERVICE.get(int(port_raw))
    except ValueError:
        port_service = None

    # Dedicated service ports win when path is empty or matches.
    if header and header not in _AMBIGUOUS_SERVICES:
        if path_service and path_service != header and header == "keystone":
            return path_service
        return header

    if port_service and port_service not in _AMBIGUOUS_SERVICES:
        if path_service and path_service != port_service and port_service == "keystone":
            return path_service
        return port_service

    return path_service or header or port_service


class ServiceDispatchMiddleware:
    """Pure ASGI middleware — rewrites scope['path'] before the app sees it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path = scope.get("path") or "/"
            if path == "/" or any(path.startswith(p) for p in _SKIP_PREFIXES):
                await self.app(scope, receive, send)
                return
            headers = {
                k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in scope.get("headers") or []
            }
            service = resolve_service(headers, path)
            if service:
                scope = dict(scope)
                scope["path"] = f"/_os/{service}{path}"
                scope["root_path"] = scope.get("root_path") or ""
        await self.app(scope, receive, send)


class ServiceStateMiddleware(BaseHTTPMiddleware):
    """Expose resolved service name on request.state for handlers/microversions."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path or "/"
        if path.startswith("/_os/"):
            parts = path.split("/", 3)
            service = parts[2] if len(parts) > 2 else None
        else:
            service = resolve_service(
                {k.lower(): v for k, v in request.headers.items()},
                path,
            )
        if service:
            request.state.openstack_service = service
        return await call_next(request)
