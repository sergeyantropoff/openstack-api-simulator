"""Keystone Identity API v3 (lab subset)."""

from __future__ import annotations

from typing import Annotated, Any

from asyncpg import Connection, Pool
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse

from app.openstack.auth import extract_token, issue_token, validate_token
from app.openstack.catalog import build_catalog_from_db
from app.openstack.db_docs import require_doc
from app.openstack.deps import (
    get_conn,
    get_pool,
    request_public_host,
    request_scheme,
    require_token,
)
from app.openstack.errors import OpenStackError
from app.openstack.auth import TokenContext

router = APIRouter(tags=["Keystone"])


@router.get("/v3")
@router.get("/v3/")
async def v3_root(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
) -> dict[str, object]:
    doc = await require_doc(
        conn, service="keystone", resource_type="discovery_version", name="default"
    )
    # Prefer nested version object when present; otherwise wrap values[0].
    if "version" in doc:
        return doc
    values = (doc.get("versions") or {}).get("values") or []
    if values:
        host = request_public_host(request)
        scheme = request_scheme(request)
        version = dict(values[0])
        version["links"] = [{"rel": "self", "href": f"{scheme}://{host}:5000/v3/"}]
        return {"version": version}
    return doc


@router.post("/v3/auth/tokens")
async def create_token(
    request: Request,
    pool: Annotated[Pool, Depends(get_pool)],
) -> Response:
    payload = await request.json()
    auth = payload.get("auth") or {}
    identity = auth.get("identity") or {}
    methods = identity.get("methods") or []
    if "password" not in methods:
        raise OpenStackError(
            "BadRequest", "Only password authentication is supported", status_code=400
        )
    password_block = (identity.get("password") or {}).get("user") or {}
    user_name = password_block.get("name")
    password = password_block.get("password")
    domain_name = ((password_block.get("domain") or {}).get("name")) or "Default"
    if not user_name or password is None:
        raise OpenStackError("BadRequest", "user name and password are required", status_code=400)

    scope = auth.get("scope") or {}
    project_name = None
    if "project" in scope:
        project_name = (scope["project"] or {}).get("name")
        if not project_name and (scope["project"] or {}).get("id"):
            # resolve by id later via SQL
            project_name = None
            project_id = scope["project"]["id"]
        else:
            project_id = None
    else:
        project_id = None

    host = request_public_host(request)
    scheme = request_scheme(request)

    async with pool.acquire() as conn:
        if project_id and not project_name:
            row = await conn.fetchrow(
                "SELECT name FROM os_projects WHERE id = $1::uuid", project_id
            )
            if row is None:
                raise OpenStackError("Unauthorized", "Project not found", status_code=401)
            project_name = str(row["name"])

        token_id, body = await issue_token(
            conn,
            user_name=str(user_name),
            password=str(password),
            project_name=str(project_name) if project_name else None,
            domain_name=str(domain_name),
            host=host,
            scheme=scheme,
        )
    return JSONResponse(status_code=201, content=body, headers={"X-Subject-Token": token_id})


@router.get("/v3/auth/tokens")
async def show_token(
    request: Request,
    pool: Annotated[Pool, Depends(get_pool)],
) -> Response:
    subject = request.headers.get("X-Subject-Token") or extract_token(
        {k: v for k, v in request.headers.items()}
    )
    if not subject:
        raise OpenStackError("Unauthorized", "X-Subject-Token required", status_code=401)
    # Also require caller token in normal Keystone, but lab accepts subject alone or auth token.
    async with pool.acquire() as conn:
        ctx = await validate_token(conn, subject)
        domain = await conn.fetchrow(
            """SELECT d.id, d.name FROM os_domains d
               JOIN os_users u ON u.domain_id = d.id WHERE u.id = $1""",
            ctx.user_id,
        )
        host = request_public_host(request)
        scheme = request_scheme(request)
        body: dict[str, Any] = {
            "token": {
                "methods": ["password"],
                "expires_at": ctx.expires_at.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "user": {
                    "id": str(ctx.user_id),
                    "name": ctx.user_name,
                    "domain": {
                        "id": str(domain["id"]) if domain else "",
                        "name": str(domain["name"]) if domain else "Default",
                    },
                },
                "roles": [{"id": r, "name": r} for r in ctx.roles],
            }
        }
        if ctx.project_id is not None:
            body["token"]["project"] = {
                "id": str(ctx.project_id),
                "name": ctx.project_name,
                "domain": {
                    "id": str(domain["id"]) if domain else "",
                    "name": str(domain["name"]) if domain else "Default",
                },
            }
            body["token"]["catalog"] = await build_catalog_from_db(conn, host, scheme=scheme)
    return JSONResponse(content=body, headers={"X-Subject-Token": subject})


@router.delete("/v3/auth/tokens", status_code=204)
async def revoke_token(
    request: Request,
    pool: Annotated[Pool, Depends(get_pool)],
) -> Response:
    subject = request.headers.get("X-Subject-Token")
    if not subject:
        raise OpenStackError("BadRequest", "X-Subject-Token required", status_code=400)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE os_tokens SET revoked = true WHERE id = $1", subject)
    return Response(status_code=204)


@router.get("/v3/auth/catalog")
async def auth_catalog(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    if ctx.project_id is None:
        raise OpenStackError("Forbidden", "Project-scoped token required", status_code=403)
    catalog = await build_catalog_from_db(
        conn,
        request_public_host(request),
        scheme=request_scheme(request),
    )
    return {"catalog": catalog}


def _project_body(row: Any) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"],
        "enabled": row["enabled"],
        "domain_id": str(row["domain_id"]),
        "is_domain": False,
        "parent_id": str(row["domain_id"]),
        "links": {"self": f"/v3/projects/{row['id']}"},
    }


def _user_body(row: Any) -> dict[str, object]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "enabled": row["enabled"],
        "domain_id": str(row["domain_id"]),
        "links": {"self": f"/v3/users/{row['id']}"},
    }


@router.get("/v3/projects")
async def list_projects(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    if ctx.is_admin:
        rows = list(
            await conn.fetch(
                "SELECT id, name, description, enabled, domain_id FROM os_projects ORDER BY name, id"
            )
        )
    else:
        rows = list(
            await conn.fetch(
                """SELECT p.id, p.name, p.description, p.enabled, p.domain_id
                   FROM os_projects p
                   JOIN os_role_assignments a ON a.project_id = p.id
                   WHERE a.user_id = $1
                   ORDER BY p.name, p.id""",
                ctx.user_id,
            )
        )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {
        "projects": [_project_body(r) for r in page],
        "links": {"next": None, "previous": None, "self": "/v3/projects"},
    }
    if links:
        body["projects_links"] = links
    return body


@router.get("/v3/projects/{project_id}")
async def show_project(
    project_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT id, name, description, enabled, domain_id FROM os_projects WHERE id = $1::uuid",
        project_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Could not find project: {project_id}", status_code=404)
    if not ctx.is_admin:
        allowed = await conn.fetchval(
            """SELECT 1 FROM os_role_assignments
               WHERE user_id = $1 AND project_id = $2::uuid LIMIT 1""",
            ctx.user_id,
            project_id,
        )
        if not allowed and str(ctx.project_id or "") != project_id:
            raise OpenStackError(
                "Forbidden", "Not authorized to access this project", status_code=403
            )
    return {"project": _project_body(row)}


@router.get("/v3/users")
async def list_users(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from app.openstack.paging import paginate_rows

    if not ctx.is_admin:
        rows = list(
            await conn.fetch(
                "SELECT id, name, enabled, domain_id FROM os_users WHERE id = $1",
                ctx.user_id,
            )
        )
    else:
        rows = list(
            await conn.fetch("SELECT id, name, enabled, domain_id FROM os_users ORDER BY name, id")
        )
    page, links = paginate_rows(rows, request, id_attr=lambda r: str(r["id"]))
    body: dict[str, object] = {"users": [_user_body(r) for r in page]}
    if links:
        body["users_links"] = links
    return body


@router.get("/v3/users/{user_id}")
async def show_user(
    user_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    if not ctx.is_admin and str(ctx.user_id) != user_id:
        raise OpenStackError("Forbidden", "Not authorized to access this user", status_code=403)
    row = await conn.fetchrow(
        "SELECT id, name, enabled, domain_id FROM os_users WHERE id = $1::uuid",
        user_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Could not find user: {user_id}", status_code=404)
    return {"user": _user_body(row)}


@router.get("/v3/domains")
async def list_domains(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    rows = await conn.fetch(
        "SELECT id, name, description, enabled FROM os_domains ORDER BY name, id"
    )
    return {
        "domains": [
            {
                "id": str(r["id"]),
                "name": r["name"],
                "description": r["description"],
                "enabled": r["enabled"],
                "links": {"self": f"/v3/domains/{r['id']}"},
            }
            for r in rows
        ]
    }


@router.get("/v3/domains/{domain_id}")
async def show_domain(
    domain_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        """SELECT id, name, description, enabled FROM os_domains
           WHERE id::text = $1 OR name = $1""",
        domain_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Could not find domain: {domain_id}", status_code=404)
    return {
        "domain": {
            "id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "enabled": row["enabled"],
            "links": {"self": f"/v3/domains/{row['id']}"},
        }
    }


@router.get("/v3/roles")
async def list_roles(
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    rows = await conn.fetch("SELECT id, name FROM os_roles ORDER BY name")
    return {"roles": [{"id": str(r["id"]), "name": r["name"]} for r in rows]}


@router.get("/v3/roles/{role_id}")
async def show_role(
    role_id: str,
    conn: Annotated[Connection, Depends(get_conn)],
    _ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    row = await conn.fetchrow(
        "SELECT id, name FROM os_roles WHERE id::text = $1 OR name = $1",
        role_id,
    )
    if row is None:
        raise OpenStackError("NotFound", f"Could not find role: {role_id}", status_code=404)
    return {"role": {"id": str(row["id"]), "name": row["name"]}}


@router.post("/v3/projects", status_code=201)
async def create_project(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from uuid import uuid4

    payload = (await request.json()).get("project") or {}
    domain_id = payload.get("domain_id") or await conn.fetchval(
        "SELECT id FROM os_domains ORDER BY name LIMIT 1"
    )
    row = await conn.fetchrow(
        """INSERT INTO os_projects(id, domain_id, name, description, enabled)
           VALUES($1,$2,$3,$4,$5) RETURNING id, name, description, enabled, domain_id""",
        uuid4(),
        domain_id,
        str(payload.get("name") or f"project-{uuid4().hex[:8]}"),
        payload.get("description") or "",
        bool(payload.get("enabled", True)),
    )
    _ = ctx
    return {"project": _project_body(row)}


@router.post("/v3/users", status_code=201)
async def create_user(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from uuid import uuid4

    from app.security.auth import hash_secret

    payload = (await request.json()).get("user") or {}
    domain_id = payload.get("domain_id") or await conn.fetchval(
        "SELECT id FROM os_domains ORDER BY name LIMIT 1"
    )
    password = str(payload.get("password") or "secret")
    row = await conn.fetchrow(
        """INSERT INTO os_users(id, domain_id, name, password_hash, enabled)
           VALUES($1,$2,$3,$4,$5) RETURNING id, name, enabled, domain_id""",
        uuid4(),
        domain_id,
        str(payload.get("name") or f"user-{uuid4().hex[:8]}"),
        hash_secret(password, salt=b"openstack-sim-v1"),
        bool(payload.get("enabled", True)),
    )
    _ = ctx
    return {"user": _user_body(row)}


@router.post("/v3/domains", status_code=201)
async def create_domain(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from uuid import uuid4

    payload = (await request.json()).get("domain") or {}
    row = await conn.fetchrow(
        """INSERT INTO os_domains(id, name, description, enabled)
           VALUES($1,$2,$3,$4) RETURNING id, name, description, enabled""",
        uuid4(),
        str(payload.get("name") or f"domain-{uuid4().hex[:8]}"),
        payload.get("description") or "",
        bool(payload.get("enabled", True)),
    )
    _ = ctx
    return {
        "domain": {
            "id": str(row["id"]),
            "name": row["name"],
            "description": row["description"],
            "enabled": row["enabled"],
            "links": {"self": f"/v3/domains/{row['id']}"},
        }
    }


@router.post("/v3/roles", status_code=201)
async def create_role(
    request: Request,
    conn: Annotated[Connection, Depends(get_conn)],
    ctx: Annotated[TokenContext, Depends(require_token)],
) -> dict[str, object]:
    from uuid import uuid4

    payload = (await request.json()).get("role") or {}
    row = await conn.fetchrow(
        """INSERT INTO os_roles(id, name) VALUES($1,$2) RETURNING id, name""",
        uuid4(),
        str(payload.get("name") or f"role-{uuid4().hex[:8]}"),
    )
    _ = ctx
    return {"role": {"id": str(row["id"]), "name": row["name"]}}
