"""Schema-driven OpenStack API engine — surface-complete ops from contract packs."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from asyncpg import Connection
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from app.db.pool import AsyncpgDatabase
from app.openstack.auth import TokenContext, extract_token, validate_token
from app.openstack.contract_loader import ensure_loaded, get_runtime
from app.openstack.errors import OpenStackError
from app.openstack.opspec import OperationSpec, ServicePack
from app.openstack.singular import singular as _singular

_PATH_PARAM = re.compile(r"\{([^{}]+)\}")


def _fastapi_path(path: str) -> str:
    """Convert {param} to FastAPI {param} (already compatible)."""
    return path if path.startswith("/") else f"/{path}"


def _parent_scope(path: str, path_params: dict[str, str]) -> dict[str, str]:
    parent = {k: v for k, v in path_params.items() if k != "id"}
    # Nested collections like /resource_providers/{id}/inventories keep the parent
    # id under useful aliases so list filters can match seeded child rows.
    if "id" in path_params:
        match = re.search(r"/([^/]+)/\{id\}(?:/|$)", path)
        if match:
            segment = match.group(1)
            singular = _singular(segment)
            parent.setdefault(f"{singular}_id", path_params["id"])
            parent.setdefault(singular, path_params["id"])
            parent.setdefault("parent_id", path_params["id"])
            parent.setdefault("resource_provider", path_params["id"])
            parent.setdefault("resource_provider_id", path_params["id"])
            parent.setdefault("server_id", path_params["id"])
    return parent


def _path_ends_with_item_param(path: str) -> bool:
    """True for item show paths (/x/{id}), false for nested collections (/x/{id}/ys)."""

    trimmed = path.rstrip("/")
    return bool(re.search(r"/\{[^{}/]+\}$", trimmed))


def _row_item(row: Any) -> dict[str, Any]:
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    item = dict(data or {})
    item.setdefault("id", str(row["id"]))
    item.setdefault("name", row["name"])
    item.setdefault("status", row["status"])
    if row["project_id"] is not None:
        item.setdefault("project_id", str(row["project_id"]))
        item.setdefault("tenant_id", str(row["project_id"]))
    item.setdefault("created_at", row["created_at"].strftime("%Y-%m-%dT%H:%M:%SZ"))
    item.setdefault("updated_at", row["updated_at"].strftime("%Y-%m-%dT%H:%M:%SZ"))
    return item


def _paginate(
    items: list[dict[str, Any]], request: Request
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        limit = int(request.query_params.get("limit") or 0)
    except ValueError:
        limit = 0
    marker = request.query_params.get("marker")
    start = 0
    if marker:
        for i, item in enumerate(items):
            if str(item.get("id")) == marker or str(item.get("name")) == marker:
                start = i + 1
                break
    page = items[start:]
    links: dict[str, Any] = {}
    if limit > 0:
        page = page[:limit]
        if start + limit < len(items):
            last = page[-1] if page else None
            if last:
                links["next"] = str(last.get("id") or last.get("name"))
    return page, links


def _check_microversion(request: Request, op: OperationSpec, pack: ServicePack) -> None:
    if not op.microversion_min and not pack.max_microversion:
        return
    requested = getattr(request.state, "microversion", None)
    runtime = get_runtime()
    override = runtime.active_microversion(pack.name)
    chosen = requested or override or pack.default_microversion
    if not chosen:
        return
    maximum = pack.max_microversion or op.microversion_max
    minimum = op.microversion_min or pack.default_microversion
    if maximum and _mv_tuple(chosen) > _mv_tuple(maximum):
        raise OpenStackError(
            "VersionNotFound",
            f"Microversion {chosen} exceeds max {maximum}",
            status_code=406,
        )
    if minimum and _mv_tuple(chosen) < _mv_tuple(minimum):
        raise OpenStackError(
            "VersionNotFound",
            f"Microversion {chosen} below min {minimum}",
            status_code=406,
        )


def _mv_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for piece in value.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _fixture_or_item(
    op: OperationSpec, item: dict[str, Any] | None, *, list_mode: bool = False
) -> Any:
    if op.response_fixture is not None:
        return op.response_fixture
    key = op.collection_key
    if list_mode and key:
        return {key: item if isinstance(item, list) else []}
    if op.item_key:
        return {op.item_key: item or {}}
    if key:
        return {_singular(key): item or {}}
    return item or {}


async def _list_objects(
    conn: Connection,
    *,
    service: str,
    resource_type: str,
    project_id: Any,
    parent: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if project_id is None:
        rows = await conn.fetch(
            """SELECT * FROM os_api_objects
               WHERE service=$1 AND resource_type=$2
               ORDER BY created_at""",
            service,
            resource_type,
        )
    else:
        rows = await conn.fetch(
            """SELECT * FROM os_api_objects
               WHERE service=$1 AND resource_type=$2
                 AND (project_id=$3 OR project_id IS NULL)
               ORDER BY created_at""",
            service,
            resource_type,
            project_id,
        )
    items = [_row_item(r) for r in rows]
    if parent:
        filtered = []
        for item in items:
            ok = True
            for pk, pv in parent.items():
                if str(item.get(pk) or item.get("parent_id") or "") not in {pv, str(item.get(pk))}:
                    # soft filter: keep if parent key absent
                    if pk in item and str(item[pk]) != pv:
                        ok = False
                        break
            if ok:
                filtered.append(item)
        return filtered
    return items


def _route_priority(op: OperationSpec) -> tuple[int, int, str]:
    """Static paths before templated ones so /detail is not captured by /{id}."""

    path = op.path
    braces = path.count("{")
    detail_bias = 0 if path.rstrip("/").endswith("/detail") else 1
    return (braces, detail_bias, path)


def build_schema_router(pack: ServicePack) -> APIRouter:
    router = APIRouter(tags=[f"Schema:{pack.name}"])
    # Deduplicate by method+path so FastAPI does not register twice.
    seen: set[tuple[str, str]] = set()

    for op in sorted(pack.operations, key=_route_priority):
        key = (op.method, op.path)
        if key in seen:
            continue
        seen.add(key)
        _register_operation(router, pack, op)
    return router


def _register_operation(router: APIRouter, pack: ServicePack, op: OperationSpec) -> None:
    path = _fastapi_path(op.path)
    name = f"schema-{pack.name}-{op.operation_id}"

    async def endpoint(request: Request) -> Response:
        return await _dispatch(request, pack, op)

    router.add_api_route(
        path,
        endpoint,
        methods=[op.method],
        name=name,
        include_in_schema=True,
    )


async def _resolve_ctx(request: Request, *, need_project: bool) -> TokenContext:
    database = request.app.state.database
    assert isinstance(database, AsyncpgDatabase)
    token = extract_token({k: v for k, v in request.headers.items()})
    if not token:
        raise OpenStackError(
            "Unauthorized",
            "The request you have made requires authentication.",
            status_code=401,
        )
    async with database.pool.acquire() as conn:
        ctx = await validate_token(conn, token)
    if need_project and ctx.project_id is None:
        raise OpenStackError("Unauthorized", "Project-scoped token required", status_code=401)
    return ctx


def _has_id_param(path: str) -> bool:
    return "{id}" in path or "{name}" in path


async def _dispatch(request: Request, pack: ServicePack, op: OperationSpec) -> Response:
    _check_microversion(request, op, pack)

    ctx: TokenContext | None = None
    if op.requires_auth:
        ctx = await _resolve_ctx(request, need_project=op.requires_project)

    database = request.app.state.database
    assert isinstance(database, AsyncpgDatabase)

    async with database.pool.acquire() as conn:
        path_params = dict(request.path_params)
        if op.kind == "action" or op.path.rstrip("/").endswith("/action"):
            return await _handle_action(request, conn, pack, op, ctx, path_params)
        if op.method == "GET":
            # Literal "/detail" list views must not be treated as item show.
            if op.kind == "detail" or str(path_params.get("id") or "").lower() == "detail":
                return await _handle_list(request, conn, pack, op, ctx, path_params)
            # Nested collection paths contain {id} but list children, not show the parent id.
            if op.kind == "collection" or (
                op.collection_key
                and _has_id_param(op.path)
                and not _path_ends_with_item_param(op.path)
            ):
                return await _handle_list(request, conn, pack, op, ctx, path_params)
            if _path_ends_with_item_param(op.path) or op.kind == "item":
                return await _handle_show(request, conn, pack, op, ctx, path_params)
            return await _handle_list(request, conn, pack, op, ctx, path_params)
        if op.method == "POST":
            if _path_ends_with_item_param(op.path) and op.kind != "collection":
                return await _handle_action(request, conn, pack, op, ctx, path_params)
            if _has_id_param(op.path) and op.kind == "collection":
                return await _handle_create(request, conn, pack, op, ctx, path_params)
            if _has_id_param(op.path) and op.kind != "collection":
                return await _handle_action(request, conn, pack, op, ctx, path_params)
            return await _handle_create(request, conn, pack, op, ctx, path_params)
        if op.method in {"PUT", "PATCH"}:
            return await _handle_update(request, conn, pack, op, ctx, path_params)
        if op.method == "DELETE":
            return await _handle_delete(request, conn, pack, op, ctx, path_params)
        raise OpenStackError(
            "BadRequest", f"Unsupported operation {op.method} {op.path}", status_code=400
        )


async def _handle_list(
    request: Request,
    conn: Connection,
    pack: ServicePack,
    op: OperationSpec,
    ctx: TokenContext | None,
    path_params: dict[str, str],
) -> Response:
    if op.response_fixture is not None:
        return JSONResponse(op.response_fixture)
    # Discovery docs live in PostgreSQL (seed_discovery_documents).
    from app.openstack.db_docs import require_doc

    if op.resource_type == "ping":
        return JSONResponse(
            await require_doc(conn, service=pack.name, resource_type="ping", name="default")
        )
    if op.resource_type == "health":
        return JSONResponse(
            await require_doc(conn, service=pack.name, resource_type="health", name="default")
        )
    if op.resource_type == "limit" and op.collection_key == "limits":
        doc = await require_doc(conn, service=pack.name, resource_type="limits", name="default")
        # Overlay live usage for cinder when volumes table is present.
        if pack.name == "cinder" and ctx and ctx.project_id is not None:
            used = await conn.fetchrow(
                """SELECT count(*)::int AS volumes,
                          coalesce(sum(size), 0)::int AS gigabytes
                   FROM os_volumes WHERE project_id=$1""",
                ctx.project_id,
            )
            absolute = dict((doc.get("limits") or {}).get("absolute") or {})
            if used:
                absolute["totalVolumesUsed"] = int(used["volumes"])
                absolute["totalGigabytesUsed"] = int(used["gigabytes"])
            return JSONResponse(
                {
                    "limits": {
                        "rate": (doc.get("limits") or {}).get("rate") or [],
                        "absolute": absolute,
                    }
                }
            )
        return JSONResponse(doc)
    if op.resource_type == "version":
        return JSONResponse(
            await require_doc(
                conn, service=pack.name, resource_type="discovery_version", name="default"
            )
        )
    project_id = ctx.project_id if ctx else None
    items = await _list_objects(
        conn,
        service=pack.name,
        resource_type=op.resource_type,
        project_id=project_id,
        parent=_parent_scope(op.path, path_params) or None,
    )
    # soft filter query params
    for qk, qv in request.query_params.items():
        if qk in {"limit", "marker", "sort_key", "sort_dir", "fields"}:
            continue
        items = [i for i in items if str(i.get(qk, qv)) == qv or qk not in i]
    # Nested soft-filter may hide parent-scoped rows — re-read without parent filter
    # but still only from PostgreSQL (no synthetic templates).
    if not items and op.method == "GET" and op.kind in {"collection", "detail", "custom"}:
        parent = _parent_scope(op.path, path_params) or None
        if parent:
            items = await _list_objects(
                conn,
                service=pack.name,
                resource_type=op.resource_type,
                project_id=project_id,
                parent=None,
            )
    page, links = _paginate(items, request)
    key = op.collection_key or "items"
    body: dict[str, Any] = {key: page}
    if links:
        body[f"{key}_links"] = links
    return JSONResponse(body, status_code=op.status_code)


async def _handle_create(
    request: Request,
    conn: Connection,
    pack: ServicePack,
    op: OperationSpec,
    ctx: TokenContext | None,
    path_params: dict[str, str],
) -> Response:
    if ctx is None or ctx.project_id is None:
        raise OpenStackError("Unauthorized", "Project-scoped token required", status_code=401)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    key = op.item_key or (op.collection_key and _singular(op.collection_key)) or "resource"
    body = payload.get(key) if isinstance(payload, dict) else None
    if body is None and isinstance(payload, dict):
        body = payload.get(op.collection_key) or payload
    if not isinstance(body, dict):
        body = {"value": body}
    item_id = uuid4()
    name = str(body.get("name") or body.get("stack_name") or op.resource_type)
    status = str(body.get("status") or body.get("stack_status") or "ACTIVE")
    data = {**body, "id": str(item_id), "name": name, "status": status, **path_params}
    row = await conn.fetchrow(
        """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
           VALUES($1,$2,$3,$4,$5,$6,$7::jsonb) RETURNING *""",
        item_id,
        pack.name,
        op.resource_type,
        ctx.project_id,
        name,
        status,
        json.dumps(data),
    )
    content = _fixture_or_item(op, _row_item(row))
    return JSONResponse(
        content, status_code=op.create_status if op.method == "POST" else op.status_code
    )


async def _handle_show(
    request: Request,
    conn: Connection,
    pack: ServicePack,
    op: OperationSpec,
    ctx: TokenContext | None,
    path_params: dict[str, str],
) -> Response:
    item_id = (
        path_params.get("id") or path_params.get("name") or next(iter(path_params.values()), None)
    )
    if not item_id:
        # custom GET without id — fall back to list-like empty / fixture
        return await _handle_list(request, conn, pack, op, ctx, path_params)
    row = await conn.fetchrow(
        """SELECT * FROM os_api_objects
           WHERE service=$1 AND resource_type=$2 AND (id::text=$3 OR name=$3)
           LIMIT 1""",
        pack.name,
        op.resource_type,
        item_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"{op.resource_type} {item_id} not found", status_code=404)
    return JSONResponse(_fixture_or_item(op, _row_item(row)), status_code=op.status_code)


async def _handle_update(
    request: Request,
    conn: Connection,
    pack: ServicePack,
    op: OperationSpec,
    ctx: TokenContext | None,
    path_params: dict[str, str],
) -> Response:
    if ctx is None or ctx.project_id is None:
        raise OpenStackError("Unauthorized", "Project-scoped token required", status_code=401)
    item_id = path_params.get("id") or next(iter(path_params.values()), None)
    if not item_id:
        raise OpenStackError("BadRequest", "Missing id", status_code=400)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    key = op.item_key or (op.collection_key and _singular(op.collection_key))
    body = payload.get(key, payload) if isinstance(payload, dict) else {}
    if not isinstance(body, dict):
        body = {}
    row = await conn.fetchrow(
        """SELECT * FROM os_api_objects
           WHERE service=$1 AND resource_type=$2 AND (id::text=$3 OR name=$3) AND project_id=$4""",
        pack.name,
        op.resource_type,
        item_id,
        ctx.project_id,
    )
    if row is None:
        # Lab upsert: pack PUT/PATCH against unknown ids still succeed (surface-complete).
        try:
            new_id = UUID(str(item_id))
        except Exception:
            new_id = uuid4()
        data = {
            "id": str(new_id),
            "name": str(body.get("name") or op.resource_type),
            "status": "ACTIVE",
            **body,
            **path_params,
        }
        created = await conn.fetchrow(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)
               ON CONFLICT (id) DO UPDATE SET
                 name=EXCLUDED.name, status=EXCLUDED.status, data=EXCLUDED.data, updated_at=now()
               RETURNING *""",
            new_id,
            pack.name,
            op.resource_type,
            ctx.project_id,
            str(data.get("name") or op.resource_type),
            str(data.get("status") or "ACTIVE"),
            json.dumps(data),
        )
        if op.status_code == 204:
            return Response(status_code=204)
        return JSONResponse(_fixture_or_item(op, _row_item(created)), status_code=200)
    data = row["data"]
    if isinstance(data, str):
        data = json.loads(data)
    data = {**(data or {}), **body, "id": str(row["id"])}
    updated = await conn.fetchrow(
        """UPDATE os_api_objects
           SET name=$1, status=$2, data=$3::jsonb, updated_at=now()
           WHERE id=$4 RETURNING *""",
        str(data.get("name") or row["name"]),
        str(data.get("status") or row["status"]),
        json.dumps(data),
        row["id"],
    )
    if op.status_code == 204:
        return Response(status_code=204)
    return JSONResponse(_fixture_or_item(op, _row_item(updated)), status_code=200)


async def _handle_delete(
    request: Request,
    conn: Connection,
    pack: ServicePack,
    op: OperationSpec,
    ctx: TokenContext | None,
    path_params: dict[str, str],
) -> Response:
    item_id = path_params.get("id") or next(iter(path_params.values()), None)
    if not item_id:
        return Response(status_code=204)
    project_id = ctx.project_id if ctx else None
    if project_id is not None:
        await conn.execute(
            """DELETE FROM os_api_objects
               WHERE service=$1 AND resource_type=$2 AND (id::text=$3 OR name=$3) AND project_id=$4""",
            pack.name,
            op.resource_type,
            item_id,
            project_id,
        )
    else:
        await conn.execute(
            """DELETE FROM os_api_objects
               WHERE service=$1 AND resource_type=$2 AND (id::text=$3 OR name=$3)""",
            pack.name,
            op.resource_type,
            item_id,
        )
    return Response(status_code=op.status_code if op.status_code in {202, 204} else 204)


async def _handle_action(
    request: Request,
    conn: Connection,
    pack: ServicePack,
    op: OperationSpec,
    ctx: TokenContext | None,
    path_params: dict[str, str],
) -> Response:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    action = op.action_name if op.action_name and op.action_name != "*" else None
    if action is None and isinstance(payload, dict) and payload:
        action = next(iter(payload.keys()))
    item_id = path_params.get("id") or path_params.get("server_id")
    # record action history for nova-like resources
    if ctx and item_id:
        await conn.execute(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb)
               ON CONFLICT DO NOTHING""",
            uuid4(),
            pack.name,
            "instance_action" if pack.name == "nova" else f"{op.resource_type}_action",
            ctx.project_id,
            action or "action",
            "DONE",
            json.dumps(
                {
                    "action": action,
                    "instance_uuid": item_id,
                    "request_id": request.headers.get("x-openstack-request-id") or str(uuid4()),
                    "message": None,
                    "start_time": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
            ),
        )
        # update parent status for common power actions
        if action in {"os-start", "unshelve", "resume", "unpause", "unrescue"}:
            new_status = "ACTIVE"
        elif action in {"os-stop", "shelve", "shelveOffload"}:
            new_status = "SHUTOFF"
        elif action in {"pause"}:
            new_status = "PAUSED"
        elif action in {"suspend"}:
            new_status = "SUSPENDED"
        else:
            new_status = None
        if new_status and pack.name == "nova":
            await conn.execute(
                "UPDATE os_servers SET status=$1, updated_at=now() WHERE id::text=$2",
                new_status,
                item_id,
            )
            await conn.execute(
                """UPDATE os_api_objects SET status=$1, data = jsonb_set(data, '{status}', to_jsonb($1::text)), updated_at=now()
                   WHERE service=$2 AND resource_type='server' AND id::text=$3""",
                new_status,
                pack.name,
                item_id,
            )
    if op.status_code == 204:
        return Response(status_code=204)
    if action in {"os-getConsoleOutput"} and item_id:
        from app.openstack.db_docs import require_doc

        row = await conn.fetchrow(
            """SELECT data FROM os_api_objects
               WHERE service='nova' AND resource_type='console_output'
                 AND (name=$1 OR data->>'server_id'=$1)
               ORDER BY updated_at DESC LIMIT 1""",
            item_id,
        )
        if row is not None:
            data = row["data"]
            if isinstance(data, str):
                data = json.loads(data)
            output = str((data or {}).get("output") or "")
        else:
            template = await require_doc(
                conn, service="nova", resource_type="console_output_template", name="default"
            )
            output = str(template.get("output") or "")
            await conn.execute(
                """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                   VALUES($1,'nova','console_output',$2,$3,'ACTIVE',$4::jsonb)""",
                uuid4(),
                ctx.project_id if ctx else None,
                item_id,
                json.dumps({"server_id": item_id, "output": output}),
            )
        return JSONResponse({"output": output})
    if action in {"os-getVNCConsole", "remote-consoles"} or "console" in (action or "").lower():
        from app.openstack.db_docs import require_doc

        console_type = ""
        console_url = ""
        if item_id:
            row = await conn.fetchrow(
                """SELECT data FROM os_api_objects
                   WHERE service='nova' AND resource_type='console'
                     AND (name=$1 OR data->>'server_id'=$1)
                   ORDER BY updated_at DESC LIMIT 1""",
                item_id,
            )
            if row is not None:
                data = row["data"]
                if isinstance(data, str):
                    data = json.loads(data)
                console_type = str((data or {}).get("type") or "")
                console_url = str((data or {}).get("url") or "")
            else:
                template = await require_doc(
                    conn, service="nova", resource_type="console_template", name="default"
                )
                console_type = str(template.get("type") or "")
                console_url = str(template.get("url") or "").replace("__SERVER_ID__", item_id)
                await conn.execute(
                    """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
                       VALUES($1,'nova','console',$2,$3,'ACTIVE',$4::jsonb)""",
                    uuid4(),
                    ctx.project_id if ctx else None,
                    item_id,
                    json.dumps({"server_id": item_id, "type": console_type, "url": console_url}),
                )
        return JSONResponse({"console": {"type": console_type, "url": console_url}})
    if action == "createImage" and item_id and ctx is not None:
        from app.openstack.db_docs import fetch_doc

        image_id = uuid4()
        body = payload.get("createImage") if isinstance(payload, dict) else None
        defaults = (
            await fetch_doc(conn, service="glance", resource_type="image_defaults", name="default")
            or {}
        )
        name = "snapshot"
        if isinstance(body, dict):
            name = str(body.get("name") or name)
        await conn.execute(
            """INSERT INTO os_images(id, name, status, visibility, size, disk_format,
                   container_format, owner_project_id)
               VALUES($1,$2,'active',$3,0,$4,$5,$6)""",
            image_id,
            name,
            defaults.get("visibility") or "private",
            defaults.get("disk_format") or "qcow2",
            defaults.get("container_format") or "bare",
            ctx.project_id,
        )
        return JSONResponse({"image_id": str(image_id)}, status_code=202)
    return Response(status_code=op.status_code)


def mount_schema_services(
    app: Any,
    *,
    series: str = "dalmatian",
    handlers: Any | None = None,
) -> int:
    """Register one FastAPI route per contract (method, path). Returns route count."""

    from app.openstack.registry import HandlerRegistry, mount_contract_services

    runtime = ensure_loaded(series)
    registry = handlers if isinstance(handlers, HandlerRegistry) else HandlerRegistry()
    count = mount_contract_services(
        app,
        packs=runtime.packs,
        handlers=registry,
        dispatch_fn=_dispatch,
    )
    app.state.openstack_contract = runtime
    app.state.openstack_handlers = registry
    return count


def remount_schema_services(app: Any, series: str) -> dict[str, Any]:
    """Reload pack metadata and rebuild per-path contract routes on the app router."""

    from app.openstack.registry import HandlerRegistry, mount_contract_services

    runtime = get_runtime()
    summary = runtime.reload(series)
    handlers = getattr(app.state, "openstack_handlers", None)
    if not isinstance(handlers, HandlerRegistry):
        handlers = HandlerRegistry()
        app.state.openstack_handlers = handlers
    count = mount_contract_services(
        app,
        packs=runtime.packs,
        handlers=handlers,
        dispatch_fn=_dispatch,
    )
    app.state.openstack_contract = runtime
    app.state.openstack_schema_ops = count
    summary = {**summary, "routes_mounted": count}
    return summary
