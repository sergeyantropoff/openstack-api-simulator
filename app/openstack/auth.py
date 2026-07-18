"""Keystone token issue / validation helpers."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from asyncpg import Connection

from app.openstack.catalog import build_catalog_from_db
from app.openstack.errors import OpenStackError
from app.security.auth import verify_secret


@dataclass(frozen=True, slots=True)
class TokenContext:
    token_id: str
    user_id: UUID
    user_name: str
    project_id: UUID | None
    project_name: str | None
    roles: tuple[str, ...]
    expires_at: datetime
    is_admin: bool


async def issue_token(
    conn: Connection,
    *,
    user_name: str,
    password: str,
    project_name: str | None,
    domain_name: str = "Default",
    host: str = "localhost",
    scheme: str = "http",
    ttl_seconds: int = 3600,
) -> tuple[str, dict[str, Any]]:
    domain = await conn.fetchrow(
        "SELECT id, name FROM os_domains WHERE name = $1 AND enabled", domain_name
    )
    if domain is None:
        raise OpenStackError("Unauthorized", "Invalid user credentials", status_code=401)

    user = await conn.fetchrow(
        """SELECT id, name, password_hash, enabled
           FROM os_users WHERE domain_id = $1 AND name = $2""",
        domain["id"],
        user_name,
    )
    if user is None or not user["enabled"] or not verify_secret(password, user["password_hash"]):
        raise OpenStackError(
            "Unauthorized", "The request you have made requires authentication.", status_code=401
        )

    project = None
    if project_name:
        project = await conn.fetchrow(
            """SELECT id, name, enabled FROM os_projects
               WHERE domain_id = $1 AND name = $2""",
            domain["id"],
            project_name,
        )
        if project is None or not project["enabled"]:
            raise OpenStackError("Unauthorized", "Project not found or disabled", status_code=401)
        assignment = await conn.fetchval(
            """SELECT 1 FROM os_role_assignments
               WHERE user_id = $1 AND project_id = $2 LIMIT 1""",
            user["id"],
            project["id"],
        )
        if assignment is None:
            raise OpenStackError("Forbidden", "User is not authorized for project", status_code=403)

    roles_rows = []
    if project is not None:
        roles_rows = await conn.fetch(
            """SELECT r.name FROM os_role_assignments a
               JOIN os_roles r ON r.id = a.role_id
               WHERE a.user_id = $1 AND a.project_id = $2""",
            user["id"],
            project["id"],
        )
    role_names = [str(row["name"]) for row in roles_rows]

    token_id = secrets.token_hex(16)
    now = datetime.now(UTC)
    expires = now + timedelta(seconds=ttl_seconds)
    await conn.execute(
        """INSERT INTO os_tokens(id, user_id, project_id, expires_at, issued_at, revoked)
           VALUES($1, $2, $3, $4, $5, false)""",
        token_id,
        user["id"],
        project["id"] if project else None,
        expires,
        now,
    )

    catalog = await build_catalog_from_db(conn, host, scheme=scheme) if project is not None else []
    body = {
        "token": {
            # Lab convenience: token id also in body so browser UIs need not rely on
            # Access-Control-Expose-Headers for X-Subject-Token.
            "id": token_id,
            "methods": ["password"],
            "expires_at": expires.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "issued_at": now.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "user": {
                "id": str(user["id"]),
                "name": user["name"],
                "domain": {"id": str(domain["id"]), "name": domain["name"]},
            },
            "audit_ids": [secrets.token_urlsafe(8)],
            "roles": [{"id": name, "name": name} for name in role_names],
        }
    }
    if project is not None:
        body["token"]["project"] = {
            "id": str(project["id"]),
            "name": project["name"],
            "domain": {"id": str(domain["id"]), "name": domain["name"]},
        }
        body["token"]["catalog"] = catalog
    return token_id, body


async def validate_token(conn: Connection, token_id: str) -> TokenContext:
    if not token_id:
        raise OpenStackError(
            "Unauthorized",
            "The request you have made requires authentication.",
            status_code=401,
        )
    row = await conn.fetchrow(
        """SELECT t.id, t.user_id, t.project_id, t.expires_at, t.revoked,
                  u.name AS user_name, p.name AS project_name
           FROM os_tokens t
           JOIN os_users u ON u.id = t.user_id
           LEFT JOIN os_projects p ON p.id = t.project_id
           WHERE t.id = $1""",
        token_id,
    )
    if row is None or row["revoked"]:
        raise OpenStackError("Unauthorized", "Invalid token", status_code=401)
    expires = row["expires_at"]
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires <= datetime.now(UTC):
        raise OpenStackError("Unauthorized", "Token has expired", status_code=401)

    roles: list[str] = []
    if row["project_id"] is not None:
        roles = [
            str(r["name"])
            for r in await conn.fetch(
                """SELECT r.name FROM os_role_assignments a
                   JOIN os_roles r ON r.id = a.role_id
                   WHERE a.user_id = $1 AND a.project_id = $2""",
                row["user_id"],
                row["project_id"],
            )
        ]
    is_admin = "admin" in roles
    return TokenContext(
        token_id=str(row["id"]),
        user_id=row["user_id"],
        user_name=str(row["user_name"]),
        project_id=row["project_id"],
        project_name=str(row["project_name"]) if row["project_name"] else None,
        roles=tuple(roles),
        expires_at=expires,
        is_admin=is_admin,
    )


def extract_token(headers: dict[str, str]) -> str | None:
    # Case-insensitive lookup
    lower = {k.lower(): v for k, v in headers.items()}
    if "x-auth-token" in lower:
        return lower["x-auth-token"]
    auth = lower.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return None
