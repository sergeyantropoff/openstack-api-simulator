"""Contract-driven OpenStack route registry (Proxmox-style per-path registration)."""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute, APIRouter

from app.api.openapi import service_openapi_tag
from app.openstack.opspec import OperationSpec, ServicePack

Handler = Callable[[Request], Awaitable[Response]]

_PATH_PARAM = re.compile(r"\{([^{}]+)\}")
_ROUTE_NAME_PREFIX = "os-contract:"


class RouteCollisionError(ValueError):
    pass


def normalize_path_template(path: str) -> str:
    """Collapse `{param}` names so `/servers/{id}` matches `/servers/{server_id}`."""

    return _PATH_PARAM.sub("{}", path if path.startswith("/") else f"/{path}")


def _param_names(path: str) -> list[str]:
    """Path param names without FastAPI converters (``{object_name:path}`` → ``object_name``)."""

    return [name.split(":", 1)[0] for name in _PATH_PARAM.findall(path)]


@dataclass(slots=True)
class HandlerRegistry:
    """Semantic handlers keyed by (service, path, verb)."""

    _handlers: dict[tuple[str, str, str], Handler] = field(default_factory=dict)
    _normalized: dict[tuple[str, str, str], tuple[str, Handler]] = field(default_factory=dict)

    def register(self, service: str, path: str, verb: str, handler: Handler) -> None:
        key = (service, path, verb.upper())
        if key in self._handlers:
            raise RouteCollisionError(f"duplicate semantic handler: {verb} {service} {path}")
        self._handlers[key] = handler
        norm_key = (service, normalize_path_template(path), verb.upper())
        # First registration wins for structural lookup (prefer exact contract names).
        self._normalized.setdefault(norm_key, (path, handler))

    def get(self, service: str, path: str, verb: str) -> Handler | None:
        verb_u = verb.upper()
        exact = self._handlers.get((service, path, verb_u))
        if exact is not None:
            return exact
        hit = self._normalized.get((service, normalize_path_template(path), verb_u))
        return hit[1] if hit else None

    def get_specialized_path(self, service: str, path: str, verb: str) -> str | None:
        """Return the path template the handler was registered under (for param remap)."""

        verb_u = verb.upper()
        if (service, path, verb_u) in self._handlers:
            return path
        hit = self._normalized.get((service, normalize_path_template(path), verb_u))
        return hit[0] if hit else None

    def keys(self) -> frozenset[tuple[str, str, str]]:
        return frozenset(self._handlers)


def _fastapi_path(path: str) -> str:
    return path if path.startswith("/") else f"/{path}"


def _route_priority(op: OperationSpec) -> tuple[int, int, str]:
    """Static paths before templated ones so /detail is not captured by /{id}."""

    path = op.path
    braces = path.count("{")
    detail_bias = 0 if path.rstrip("/").endswith("/detail") else 1
    return (braces, detail_bias, path)


def _remap_path_params(request: Request, contract_path: str, specialized_path: str) -> None:
    """Align request.path_params names with the specialized route template."""

    contract_names = _param_names(contract_path)
    specialized_names = _param_names(specialized_path)
    if not specialized_names:
        return
    current = dict(request.path_params)
    if set(specialized_names) <= set(current):
        return
    values: list[str] = []
    for name in contract_names:
        if name in current:
            values.append(str(current[name]))
    if len(values) != len(specialized_names):
        # Fall back to positional values already present.
        values = [str(v) for v in current.values()]
        if len(values) != len(specialized_names):
            return
    remapped = dict(zip(specialized_names, values, strict=True))
    # Keep any non-path extras (unlikely) under original keys.
    for key, value in current.items():
        if key not in remapped and key not in contract_names:
            remapped[key] = value
    request.scope["path_params"] = remapped


def _bridge_route_handler(specialized_path: str, route_handler: Handler) -> Handler:
    async def handler(request: Request) -> Response:
        contract_path = getattr(request.state, "os_contract_path", specialized_path)
        _remap_path_params(request, contract_path, specialized_path)
        return await route_handler(request)

    return handler


def register_specialized_handlers(
    registry: HandlerRegistry,
    service: str,
    router: APIRouter,
) -> int:
    """Import FastAPI router endpoints into the semantic handler registry."""

    count = 0
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = route.methods or set()
        route_handler = route.get_route_handler()
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            path = route.path
            key = (service, path, method.upper())
            if key in registry._handlers:
                continue
            registry.register(
                service,
                path,
                method,
                _bridge_route_handler(path, route_handler),
            )
            count += 1
    return count


def clear_os_contract_routes(app: FastAPI) -> None:
    """Drop previously registered ``os-contract:`` routes for rebuild / hot-swap."""

    app.router.routes = [
        route
        for route in app.router.routes
        if not (
            isinstance(getattr(route, "name", None), str)
            and str(route.name).startswith(_ROUTE_NAME_PREFIX)
        )
    ]
    app.openapi_schema = None


def register_openstack_contract_routes(
    app: FastAPI,
    packs: dict[str, ServicePack],
    handlers: HandlerRegistry,
    *,
    dispatch_fn: Callable[[Request, ServicePack, OperationSpec], Awaitable[Response]],
) -> int:
    """Register one FastAPI route per unique (service, method, path) from packs.

    Endpoint looks up a semantic handler first; otherwise falls back to ``dispatch_fn``
    (schema engine generic CRUD/action behaviour).
    """

    registered = 0
    for pack in packs.values():
        seen: set[tuple[str, str]] = set()
        for op in sorted(pack.operations, key=_route_priority):
            key = (op.method, op.path)
            if key in seen:
                continue
            seen.add(key)
            path = _fastapi_path(op.path)
            full_path = f"/_os/{pack.name}{path}"
            name = f"{_ROUTE_NAME_PREFIX}{pack.name}:{op.method}:{op.path}"
            endpoint = _make_contract_endpoint(pack, op, handlers, dispatch_fn)
            # FastAPI only auto-adds HEAD for @app.get(); contract routes use
            # add_api_route — register HEAD beside every GET for the matrix.
            methods = [op.method]
            if op.method.upper() == "GET":
                methods.append("HEAD")

            app.add_api_route(
                full_path,
                endpoint,
                methods=methods,
                name=name,
                include_in_schema=True,
                tags=[service_openapi_tag(pack.name)],
            )
            registered += 1
    return registered


def _make_contract_endpoint(
    pack: ServicePack,
    op: OperationSpec,
    handlers: HandlerRegistry,
    dispatch_fn: Callable[[Request, ServicePack, OperationSpec], Awaitable[Response]],
) -> Handler:
    async def endpoint(request: Request) -> Response:
        request.state.os_contract_path = op.path
        request.state.os_contract_op = op
        handler = handlers.get(pack.name, op.path, op.method)
        if handler is not None:
            return await handler(request)
        return await dispatch_fn(request, pack, op)

    return endpoint


def register_specialized_orphan_routes(
    app: FastAPI,
    packs: dict[str, ServicePack],
    handlers: HandlerRegistry,
) -> int:
    """Register specialized handler paths that are not declared in the contract pack.

    Keeps trailing-slash version roots, PUT collection aliases, etc. that exist on
    stateful routers but are missing from generated ``api.json`` packs.
    """

    declared: set[tuple[str, str, str]] = set()
    declared_norm: set[tuple[str, str, str]] = set()
    for pack in packs.values():
        for op in pack.operations:
            declared.add((pack.name, op.method.upper(), op.path))
            declared_norm.add((pack.name, op.method.upper(), normalize_path_template(op.path)))

    # Paths already mounted by the contract loop.
    mounted: set[tuple[str, str, str]] = set()
    for route in app.router.routes:
        name = getattr(route, "name", None)
        if not isinstance(name, str) or not name.startswith(_ROUTE_NAME_PREFIX):
            continue
        # os-contract:{service}:{METHOD}:{path}
        rest = name[len(_ROUTE_NAME_PREFIX) :]
        service, _, remainder = rest.partition(":")
        method, _, path = remainder.partition(":")
        mounted.add((service, method.upper(), path))

    registered = 0
    for service, path, verb in sorted(handlers.keys()):
        verb_u = verb.upper()
        if (service, verb_u, path) in declared or (service, verb_u, path) in mounted:
            continue
        if (service, verb_u, normalize_path_template(path)) in declared_norm:
            continue
        handler = handlers.get(service, path, verb_u)
        if handler is None:
            continue
        full_path = f"/_os/{service}{_fastapi_path(path)}"
        name = f"{_ROUTE_NAME_PREFIX}{service}:{verb_u}:{path}"
        endpoint = _make_handler_only_endpoint(path, handler)
        app.add_api_route(
            full_path,
            endpoint,
            methods=[verb_u],
            name=name,
            include_in_schema=True,
            tags=[service_openapi_tag(service)],
        )
        registered += 1
    return registered


def _make_handler_only_endpoint(specialized_path: str, handler: Handler) -> Handler:
    async def endpoint(request: Request) -> Response:
        request.state.os_contract_path = specialized_path
        return await handler(request)

    return endpoint


def mount_contract_services(
    app: FastAPI,
    *,
    packs: dict[str, ServicePack],
    handlers: HandlerRegistry,
    dispatch_fn: Callable[[Request, ServicePack, OperationSpec], Awaitable[Response]],
) -> int:
    """Clear previous contract routes and register from packs. Returns route count."""

    # Preserve non-contract routes; insert contract routes before gen-* so static
    # schema paths are not stolen by generic /{item_id}.
    non_gen: list[Any] = []
    gen: list[Any] = []
    for route in app.router.routes:
        name = getattr(route, "name", "") or ""
        if isinstance(name, str) and name.startswith(_ROUTE_NAME_PREFIX):
            continue
        if isinstance(name, str) and name.startswith("schema-"):
            # Legacy schema-* routes from older mounts — drop on rebuild.
            continue
        if isinstance(name, str) and name.startswith("gen-"):
            gen.append(route)
        else:
            non_gen.append(route)
    app.router.routes = non_gen
    app.openapi_schema = None
    count = register_openstack_contract_routes(app, packs, handlers, dispatch_fn=dispatch_fn)
    count += register_specialized_orphan_routes(app, packs, handlers)
    app.router.routes.extend(gen)
    return count
