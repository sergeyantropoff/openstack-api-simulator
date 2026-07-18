"""Mount OpenStack service routers onto the FastAPI application."""

from __future__ import annotations

from fastapi import FastAPI

from app.openstack.contract_loader import ensure_loaded, load_series_pack
from app.openstack.dispatch import ServiceDispatchMiddleware, ServiceStateMiddleware
from app.openstack.engine import mount_generic_services
from app.openstack.errors import OpenStackError, openstack_error_handler
from app.openstack.microversions import MicroversionMiddleware
from app.openstack.registry import HandlerRegistry, register_specialized_handlers
from app.openstack.routes import (
    cinder,
    glance,
    heat,
    ironic,
    keystone,
    neutron,
    nova,
    octavia,
    placement,
    root,
    swift,
)
from app.openstack.schema_engine import mount_schema_services


# Specialized routers provide stateful handlers; contract packs register every
# path. Legacy generic engine remains as a final fallback for undeclared services.
_SPECIALIZED_ROUTERS: list[tuple[str, object]] = [
    ("keystone", keystone.router),
    ("nova", nova.router),
    ("neutron", neutron.router),
    ("glance", glance.router),
    ("cinder", cinder.router),
    ("placement", placement.router),
    ("heat", heat.router),
    ("swift", swift.router),
    ("ironic", ironic.router),
    ("octavia", octavia.router),
]


def build_openstack_handlers() -> HandlerRegistry:
    """Collect stateful handlers from specialized routers into a registry."""

    registry = HandlerRegistry()
    for name, router in _SPECIALIZED_ROUTERS:
        register_specialized_handlers(registry, name, router)  # type: ignore[arg-type]
    return registry


def mount_openstack_routes(app: FastAPI, *, series: str = "dalmatian") -> None:
    """Register all OpenStack Identity + IaaS + schema-complete APIs."""

    app.add_exception_handler(OpenStackError, openstack_error_handler)

    # Order matters: last added = outermost. Dispatch must be outermost so
    # rewritten paths reach routers; microversions see original headers.
    app.add_middleware(MicroversionMiddleware)
    app.add_middleware(ServiceStateMiddleware)
    app.add_middleware(ServiceDispatchMiddleware)

    # Port-aware version discovery stays on bare "/".
    app.include_router(root.router)

    # Contract is the sole path source; specialized routers contribute handlers only.
    handlers = build_openstack_handlers()
    ensure_loaded(series)
    mounted = mount_schema_services(app, series=series, handlers=handlers)
    app.state.openstack_schema_ops = mounted
    app.state.openstack_handlers = handlers

    # Legacy generic CRUD only for services without a schema pack (avoid
    # /{item_id} stealing /detail and other static schema paths).
    schema_services = set(load_series_pack(series).keys())
    mount_generic_services(app, skip=schema_services)
