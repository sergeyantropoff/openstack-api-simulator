"""Generic OpenStack collection/item CRUD backed by os_api_objects."""

from __future__ import annotations

import json
import re
from typing import Any
from uuid import uuid4

from asyncpg import Connection
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.openstack.auth import TokenContext
from app.openstack.deps import get_conn, require_project_token, require_token
from app.openstack.errors import OpenStackError
from app.openstack.surface import SERVICES, ServiceSpec

_PATH_PARAM = re.compile(r"\{([^{}]+)\}")


def _singular(collection_key: str) -> str:
    if collection_key.endswith("ies"):
        return collection_key[:-3] + "y"
    if collection_key.endswith("ses"):
        return collection_key[:-2]
    if collection_key.endswith("s") and not collection_key.endswith("ss"):
        return collection_key[:-1]
    return collection_key


def _wrap_list(collection_key: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {collection_key: items}


def _wrap_item(collection_key: str, item: dict[str, Any]) -> dict[str, Any]:
    return {_singular(collection_key): item}


def _row_to_item(row: Any) -> dict[str, Any]:
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


def _has_path_params(path: str) -> bool:
    return bool(_PATH_PARAM.search(path))


def build_generic_router(spec: ServiceSpec) -> APIRouter:
    router = APIRouter(tags=[spec.name.title()])

    version_path = (spec.version_path or "").rstrip("/")
    if version_path and version_path != "/":
        service_name = spec.name

        async def version_discovery(
            conn: Connection = Depends(get_conn),
        ) -> dict[str, object]:
            from app.openstack.db_docs import require_doc

            return await require_doc(
                conn, service=service_name, resource_type="discovery_version", name="default"
            )

        router.add_api_route(
            version_path,
            version_discovery,
            methods=["GET"],
            name=f"gen-{spec.name}-version",
        )
        router.add_api_route(
            version_path + "/",
            version_discovery,
            methods=["GET"],
            name=f"gen-{spec.name}-version-slash",
        )

    for resource_type, collection_path, collection_key in spec.resources:
        if collection_path in {"", "/"} or _has_path_params(collection_path):
            # Nested templates / bare roots need specialized routers.
            continue
        _register_collection(
            router,
            spec=spec,
            resource_type=resource_type,
            collection_path=collection_path,
            collection_key=collection_key,
        )
    return router


def _register_collection(
    router: APIRouter,
    *,
    spec: ServiceSpec,
    resource_type: str,
    collection_path: str,
    collection_key: str,
) -> None:
    item_path = f"{collection_path.rstrip('/')}/{{item_id}}"

    async def list_items(
        conn: Connection = Depends(get_conn),
        ctx: TokenContext = Depends(require_token),
    ) -> dict[str, Any]:
        if ctx.project_id is None:
            rows = await conn.fetch(
                """SELECT * FROM os_api_objects
                   WHERE service = $1 AND resource_type = $2
                   ORDER BY created_at""",
                spec.name,
                resource_type,
            )
        else:
            rows = await conn.fetch(
                """SELECT * FROM os_api_objects
                   WHERE service = $1 AND resource_type = $2
                     AND (project_id = $3 OR project_id IS NULL)
                   ORDER BY created_at""",
                spec.name,
                resource_type,
                ctx.project_id,
            )
        return _wrap_list(collection_key, [_row_to_item(r) for r in rows])

    async def create_item(
        request: Request,
        conn: Connection = Depends(get_conn),
        ctx: TokenContext = Depends(require_project_token),
    ) -> JSONResponse:
        payload = await request.json()
        body = payload.get(_singular(collection_key)) or payload.get(collection_key) or payload
        if not isinstance(body, dict):
            body = {"value": body}
        item_id = uuid4()
        name = str(body.get("name") or body.get("stack_name") or resource_type)
        status = str(body.get("status") or body.get("stack_status") or "ACTIVE")
        data = {**body, "id": str(item_id), "name": name, "status": status}
        row = await conn.fetchrow(
            """INSERT INTO os_api_objects(id, service, resource_type, project_id, name, status, data)
               VALUES($1, $2, $3, $4, $5, $6, $7::jsonb)
               RETURNING *""",
            item_id,
            spec.name,
            resource_type,
            ctx.project_id,
            name,
            status,
            json.dumps(data),
        )
        return JSONResponse(status_code=201, content=_wrap_item(collection_key, _row_to_item(row)))

    async def show_item(
        item_id: str,
        conn: Connection = Depends(get_conn),
        ctx: TokenContext = Depends(require_token),
    ) -> dict[str, Any]:
        row = await conn.fetchrow(
            """SELECT * FROM os_api_objects
               WHERE service = $1 AND resource_type = $2 AND id::text = $3""",
            spec.name,
            resource_type,
            item_id,
        )
        if row is None:
            # also allow name lookup
            row = await conn.fetchrow(
                """SELECT * FROM os_api_objects
                   WHERE service = $1 AND resource_type = $2 AND name = $3
                   LIMIT 1""",
                spec.name,
                resource_type,
                item_id,
            )
        if row is None:
            raise OpenStackError(
                "NotFound", f"{resource_type} {item_id} not found", status_code=404
            )
        if (
            ctx.project_id is not None
            and row["project_id"] is not None
            and row["project_id"] != ctx.project_id
            and not ctx.is_admin
        ):
            raise OpenStackError(
                "NotFound", f"{resource_type} {item_id} not found", status_code=404
            )
        return _wrap_item(collection_key, _row_to_item(row))

    async def update_item(
        item_id: str,
        request: Request,
        conn: Connection = Depends(get_conn),
        ctx: TokenContext = Depends(require_project_token),
    ) -> dict[str, Any]:
        payload = await request.json()
        body = payload.get(_singular(collection_key), payload)
        if not isinstance(body, dict):
            raise OpenStackError("BadRequest", "JSON object required", status_code=400)
        row = await conn.fetchrow(
            """SELECT * FROM os_api_objects
               WHERE service = $1 AND resource_type = $2 AND id::text = $3 AND project_id = $4""",
            spec.name,
            resource_type,
            item_id,
            ctx.project_id,
        )
        if row is None:
            raise OpenStackError(
                "NotFound", f"{resource_type} {item_id} not found", status_code=404
            )
        data = row["data"]
        if isinstance(data, str):
            data = json.loads(data)
        data = {**(data or {}), **body, "id": str(row["id"])}
        name = str(data.get("name") or row["name"])
        status = str(data.get("status") or row["status"])
        updated = await conn.fetchrow(
            """UPDATE os_api_objects
               SET name = $1, status = $2, data = $3::jsonb, updated_at = now()
               WHERE id = $4
               RETURNING *""",
            name,
            status,
            json.dumps(data),
            row["id"],
        )
        return _wrap_item(collection_key, _row_to_item(updated))

    async def delete_item(
        item_id: str,
        conn: Connection = Depends(get_conn),
        ctx: TokenContext = Depends(require_project_token),
    ) -> Response:
        result = await conn.execute(
            """DELETE FROM os_api_objects
               WHERE service = $1 AND resource_type = $2 AND id::text = $3 AND project_id = $4""",
            spec.name,
            resource_type,
            item_id,
            ctx.project_id,
        )
        if result.endswith("0"):
            raise OpenStackError(
                "NotFound", f"{resource_type} {item_id} not found", status_code=404
            )
        return Response(status_code=204)

    # Bind with defaults to capture loop variables.
    router.add_api_route(
        collection_path, list_items, methods=["GET"], name=f"gen-{spec.name}-{resource_type}-list"
    )
    router.add_api_route(
        collection_path,
        create_item,
        methods=["POST"],
        name=f"gen-{spec.name}-{resource_type}-create",
    )
    router.add_api_route(
        item_path, show_item, methods=["GET"], name=f"gen-{spec.name}-{resource_type}-show"
    )
    router.add_api_route(
        item_path,
        update_item,
        methods=["PUT", "PATCH"],
        name=f"gen-{spec.name}-{resource_type}-update",
    )
    router.add_api_route(
        item_path, delete_item, methods=["DELETE"], name=f"gen-{spec.name}-{resource_type}-delete"
    )


def mount_generic_services(app: Any, *, skip: set[str] | None = None) -> int:
    """Mount generic routers under /_os/<service> for every service not in skip."""

    skipped = skip or set()
    count = 0
    for spec in SERVICES:
        if spec.name in skipped:
            continue
        app.include_router(build_generic_router(spec), prefix=f"/_os/{spec.name}")
        count += 1 + sum(
            1
            for _, path, _ in spec.resources
            if path not in {"", "/"} and not _has_path_params(path)
        )
    return count
