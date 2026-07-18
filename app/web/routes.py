"""Browser console for exercising the simulator API."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from asyncpg import Pool  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.registry import HandlerRegistry
from app.config import Settings
from app.contracts.runtime import apply_runtime_contract_locked, contract_store_root
from app.contracts.source import SourceError
from app.db.pool import AsyncpgDatabase
from app.dependencies import get_database
from app.openstack.demo_cloud import openstack_demo_summary, seed_openstack_demo
from app.openstack.seed import seed_openstack
from app.web.assets import console_html
from app.web.compatibility_catalog import compatibility_payload
from app.web.contract_catalog import catalog_payload, list_majors, load_snapshot, method_payload

router = APIRouter(tags=["Simulator"])


@router.get("/console", response_class=HTMLResponse, include_in_schema=True)
async def console() -> HTMLResponse:
    """Interactive API console and cluster overview."""

    return HTMLResponse(
        console_html(),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/ui/api/versions", include_in_schema=False)
async def ui_versions(request: Request) -> JSONResponse:
    from app.web.openstack_catalog import openstack_series_majors

    runtime_version = _runtime_version(request)
    # Prefer OpenStack contract packs when present.
    try:
        return JSONResponse(openstack_series_majors(runtime_version))
    except Exception:
        settings = _settings(request)
        return JSONResponse(list_majors(runtime_version=runtime_version, settings=settings))


@router.get("/ui/api/catalog", include_in_schema=False)
async def ui_catalog(
    request: Request,
    major: Annotated[int, Query(ge=6, le=9)],
) -> JSONResponse:
    from app.web.openstack_catalog import openstack_catalog_payload

    try:
        return JSONResponse(openstack_catalog_payload(major))
    except FileNotFoundError:
        settings = _settings(request)
        try:
            snapshot = await load_snapshot(major, _store_root(request), settings=settings)
        except SourceError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        implemented = getattr(request.app.state, "implemented_methods", None)
        return JSONResponse(
            catalog_payload(snapshot, major, implemented_methods=implemented, settings=settings)
        )


@router.get("/ui/api/method", include_in_schema=False)
async def ui_method(
    request: Request,
    major: Annotated[int, Query(ge=6, le=9)],
    path: Annotated[str, Query(min_length=1)],
    verb: Annotated[str, Query(min_length=1)],
) -> JSONResponse:
    from app.web.openstack_catalog import openstack_method_payload

    runtime_version = _runtime_version(request)
    try:
        return JSONResponse(
            openstack_method_payload(
                major=major,
                path=path,
                verb=verb,
                runtime_version=runtime_version,
            )
        )
    except (FileNotFoundError, KeyError):
        pass
    settings = _settings(request)
    try:
        snapshot = await load_snapshot(major, _store_root(request), settings=settings)
    except SourceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    implemented = getattr(request.app.state, "implemented_methods", None)
    try:
        payload = method_payload(
            snapshot,
            major=major,
            path=path,
            verb=verb,
            runtime_version=runtime_version,
            implemented_methods=implemented,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"unknown contract method: {error}") from error
    return JSONResponse(payload)


@router.get("/ui/api/compatibility", include_in_schema=False)
async def ui_compatibility(
    request: Request,
    major: Annotated[int, Query(ge=6, le=9)],
) -> JSONResponse:
    from app.web.openstack_catalog import openstack_compatibility_payload

    runtime_version = _runtime_version(request)
    # Prefer OpenStack pack coverage (Yoga→Dalmatian).
    try:
        return JSONResponse(
            openstack_compatibility_payload(
                major,
                runtime_version=runtime_version,
                schema_ops_mounted=getattr(request.app.state, "openstack_schema_ops", None),
            )
        )
    except (FileNotFoundError, KeyError, ValueError):
        pass

    settings = _settings(request)
    try:
        snapshot = await load_snapshot(major, _store_root(request), settings=settings)
    except SourceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    implemented = getattr(request.app.state, "implemented_methods", None)
    runtime_report = getattr(request.app.state, "compatibility_report", None)
    return JSONResponse(
        compatibility_payload(
            snapshot,
            major,
            implemented_methods=implemented,
            runtime_report=runtime_report,
            runtime_version=runtime_version,
            settings=settings,
        )
    )


@router.post("/ui/api/contract/apply", include_in_schema=False)
async def ui_contract_apply(
    request: Request,
    major: Annotated[int, Query(ge=6, le=9)],
) -> JSONResponse:
    """Hot-swap the in-memory runtime contract to a catalog major (memory-only).

    Prefer OpenStack series packs when present; fall back to legacy Proxmox
    snapshot swap when ``CONTRACT_SNAPSHOT`` / handler registry are configured.
    """

    from app.openstack.contract_loader import series_for_major
    from app.openstack.schema_engine import remount_schema_services

    # OpenStack pack path (Yoga=6 … Dalmatian=9).
    try:
        series = series_for_major(major)
    except Exception:
        series = None
    if series:
        async with request.app.state.contract_swap_lock:
            try:
                summary = remount_schema_services(request.app, series)
            except FileNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        request.app.state.openstack_schema_ops = summary.get(
            "routes_mounted", summary.get("operation_count", 0)
        )
        request.app.state.runtime_version = f"openstack-{series}"
        return JSONResponse(
            {
                "ok": True,
                "major": major,
                "series": series,
                "runtime_version": f"openstack-{series}",
                "path_count": summary.get("service_count"),
                "method_count": summary.get("routes_mounted", summary.get("operation_count")),
                **{k: v for k, v in summary.items() if k not in {"ok"}},
            }
        )

    settings = _settings(request)
    handlers = getattr(request.app.state, "handlers", None)
    if (
        settings is None
        or settings.contract_snapshot is None
        or not isinstance(handlers, HandlerRegistry)
    ):
        raise HTTPException(status_code=503, detail="runtime contract is not available")
    store_root = _store_root(request)
    try:
        snapshot = await load_snapshot(major, store_root, settings=settings)
    except SourceError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    await apply_runtime_contract_locked(
        request.app,
        snapshot,
        handlers=handlers,
        store_root=store_root,
        fallback=settings.contract_fallback,
        settings=settings,
        require_evidence_match=False,
        register_admin=True,
    )
    method_count = sum(len(path.methods) for path in snapshot.paths)
    return JSONResponse(
        {
            "ok": True,
            "major": major,
            "runtime_version": snapshot.source_version,
            "path_count": len(snapshot.paths),
            "method_count": method_count,
        }
    )


@router.get("/ui/api/demo/state", include_in_schema=False)
async def ui_demo_state(request: Request) -> JSONResponse:
    pool = _database_pool(request)
    async with pool.acquire() as connection:
        return JSONResponse(await openstack_demo_summary(connection))


@router.get("/ui/api/openstack/contracts", include_in_schema=False)
async def ui_openstack_contracts(request: Request) -> JSONResponse:
    """Active OpenStack API contract pack + available series."""

    from app.openstack.contract_loader import ensure_loaded, get_runtime, list_series

    ensure_loaded("dalmatian")
    runtime = get_runtime()
    return JSONResponse(
        {
            "active": runtime.summary(),
            "available": list_series(),
            "schema_ops_mounted": getattr(request.app.state, "openstack_schema_ops", 0),
        }
    )


@router.post("/ui/api/openstack/contracts/activate", include_in_schema=False)
async def ui_openstack_contracts_activate(request: Request) -> JSONResponse:
    """Hot-swap the active OpenStack series contract pack."""

    from app.openstack.schema_engine import remount_schema_services

    payload = await request.json()
    series = str(payload.get("series") or "").lower().strip()
    if not series:
        raise HTTPException(status_code=400, detail="series is required")
    async with request.app.state.contract_swap_lock:
        try:
            summary = remount_schema_services(request.app, series)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    request.app.state.openstack_schema_ops = summary.get(
        "routes_mounted", summary.get("operation_count", 0)
    )
    request.app.state.runtime_version = f"openstack-{series}"
    return JSONResponse({"ok": True, "runtime_version": f"openstack-{series}", **summary})


@router.post("/ui/api/openstack/microversions", include_in_schema=False)
async def ui_openstack_microversions(request: Request) -> JSONResponse:
    """Set or clear a per-service microversion override for the lab."""

    from app.openstack.contract_loader import ensure_loaded, get_runtime

    ensure_loaded("dalmatian")
    payload = await request.json()
    service = str(payload.get("service") or "").lower().strip()
    version = payload.get("version")
    if not service:
        raise HTTPException(status_code=400, detail="service is required")
    runtime = get_runtime()
    if service not in runtime.packs:
        raise HTTPException(status_code=404, detail=f"unknown service {service}")
    runtime.set_microversion(service, None if version in (None, "", "default") else str(version))
    return JSONResponse({"ok": True, "active": runtime.summary()})


@router.post("/ui/api/demo/load", include_in_schema=False)
async def ui_demo_load(request: Request) -> JSONResponse:
    """Load synthetic OpenStack cloud (~1000 servers + full topology)."""

    pool = _database_pool(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await seed_openstack_demo(connection)
            summary = await openstack_demo_summary(connection)
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"failed to load OpenStack demo cloud: {error}"
        ) from error
    return JSONResponse(
        {"ok": True, "profile": result["profile"], "summary": summary, "seed": result}
    )


@router.post("/ui/api/demo/unload", include_in_schema=False)
async def ui_demo_unload(request: Request) -> JSONResponse:
    """Reset OpenStack state to the minimal lab seed."""

    pool = _database_pool(request)
    try:
        async with pool.acquire() as connection:
            async with connection.transaction():
                from app.openstack.demo_cloud import clear_openstack_state

                await clear_openstack_state(connection)
                result = await seed_openstack(connection)
            summary = await openstack_demo_summary(connection)
    except Exception as error:
        raise HTTPException(
            status_code=500, detail=f"failed to remove demo data: {error}"
        ) from error
    return JSONResponse(
        {"ok": True, "profile": result.get("profile", "minimal"), "summary": summary}
    )


def _database_pool(request: Request) -> Pool:
    database = get_database(request)
    if not isinstance(database, AsyncpgDatabase):
        raise HTTPException(status_code=503, detail="database is not available")
    return database.pool


def _settings(request: Request) -> Settings | None:
    return getattr(request.app.state, "settings", None)


def _runtime_version(request: Request) -> str | None:
    for attr in ("runtime_source_version", "runtime_version"):
        active = getattr(request.app.state, attr, None)
        if isinstance(active, str) and active:
            return active
    # Prefer active OpenStack pack series when Proxmox snapshot is absent.
    try:
        from app.openstack.contract_loader import get_runtime

        runtime = get_runtime()
        if runtime.series:
            return f"openstack-{runtime.series}"
    except Exception:
        pass
    settings = _settings(request)
    if settings is None or settings.contract_snapshot is None:
        return None
    from app.contracts.model import Snapshot

    snapshot = Snapshot.model_validate_json(settings.contract_snapshot.read_bytes())
    return snapshot.source_version


def _store_root(request: Request) -> Path:
    stored = getattr(request.app.state, "contract_store_root", None)
    if isinstance(stored, Path):
        return stored
    settings = _settings(request)
    if settings is not None:
        return contract_store_root(settings)
    return Path("contracts")
