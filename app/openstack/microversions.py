"""OpenStack API microversion middleware (Nova / Cinder / Manila style)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Fallback service -> (default, max) when contract pack is not loaded.
MICROVERSIONS: dict[str, tuple[str, str]] = {
    "nova": ("2.1", "2.96"),
    "cinder": ("3.0", "3.70"),
    "manila": ("2.0", "2.82"),
    "ironic": ("1.1", "1.90"),
    "placement": ("1.0", "1.39"),
}


def _service_from_request(request: Request) -> str | None:
    header = request.headers.get("x-openstack-service")
    if header:
        return header.lower()
    port = request.headers.get("x-forwarded-port")
    port_map = {
        "8774": "nova",
        "8776": "cinder",
        "8786": "manila",
        "6385": "ironic",
        "8003": "placement",
    }
    return port_map.get(str(port))


def _bounds(service: str) -> tuple[str, str] | None:
    try:
        from app.openstack.contract_loader import get_runtime

        runtime = get_runtime()
        pack = runtime.packs.get(service)
        if pack and pack.default_microversion and pack.max_microversion:
            return pack.default_microversion, pack.max_microversion
        override = runtime.active_microversion(service)
        if pack and override and pack.max_microversion:
            return override, pack.max_microversion
    except Exception:
        pass
    return MICROVERSIONS.get(service)


class MicroversionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        service = _service_from_request(request)
        requested = request.headers.get("openstack-api-version") or request.headers.get(
            "x-openstack-nova-api-version"
        )
        version = None
        if requested:
            parts = requested.strip().split()
            version = parts[-1] if parts else None
        bounds = _bounds(service) if service else None
        if service and bounds:
            default, maximum = bounds
            try:
                from app.openstack.contract_loader import get_runtime

                custom = get_runtime().microversion_overrides.get(service)
            except Exception:
                custom = None
            chosen = version or custom or default
            request.state.microversion = chosen
            request.state.microversion_max = maximum
            request.state.microversion_service = service
        response = await call_next(request)
        if service and bounds:
            default, maximum = bounds
            chosen = getattr(request.state, "microversion", default)
            if service == "nova":
                response.headers["OpenStack-API-Version"] = f"compute {chosen}"
                response.headers["X-OpenStack-Nova-API-Version"] = chosen
            elif service == "cinder":
                response.headers["OpenStack-API-Version"] = f"volume {chosen}"
            elif service == "placement":
                response.headers["OpenStack-API-Version"] = f"placement {chosen}"
            else:
                response.headers["OpenStack-API-Version"] = f"{service} {chosen}"
            response.headers.setdefault("Vary", "OpenStack-API-Version")
        return response
