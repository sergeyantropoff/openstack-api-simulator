"""OperationSpec — declarative OpenStack API operation descriptor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"]


@dataclass(frozen=True, slots=True)
class OperationSpec:
    """One OpenStack API operation (method + path) within a service pack."""

    operation_id: str
    method: HttpMethod
    path: str
    service: str
    resource_type: str
    collection_key: str | None = None
    item_key: str | None = None
    kind: Literal["collection", "item", "action", "detail", "custom"] = "collection"
    status_code: int = 200
    create_status: int = 201
    microversion_min: str | None = None
    microversion_max: str | None = None
    requires_auth: bool = True
    requires_project: bool = True
    action_name: str | None = None
    response_fixture: dict[str, Any] | None = None
    notes: str = ""
    # Full JSON Schema for the HTTP request body (merged from request_bodies/).
    request_schema: dict[str, Any] | None = None

    def path_params(self) -> list[str]:
        import re

        return re.findall(r"\{([^{}]+)\}", self.path)


@dataclass
class ServicePack:
    name: str
    typ: str
    port: int
    version_path: str
    default_microversion: str | None
    max_microversion: str | None
    operations: list[OperationSpec] = field(default_factory=list)

    def operation_count(self) -> int:
        return len(self.operations)


@dataclass
class SeriesManifest:
    series: str
    major: int
    services: list[dict[str, Any]]
    checksum: str = ""
    generated_at: str = ""
    operation_count: int = 0
    service_count: int = 0
