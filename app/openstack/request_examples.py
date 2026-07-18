"""Build UI body_fields / body_example from JSON Schema request bodies."""

from __future__ import annotations

from typing import Any


def schema_example(schema: dict[str, Any] | None, *, name: str | None = None) -> Any:
    """Build a representative JSON value from a JSON Schema fragment."""

    if not schema:
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    enum_values = schema.get("enum") or []
    if enum_values:
        return enum_values[0]
    if "const" in schema:
        return schema["const"]

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((t for t in schema_type if t != "null"), schema_type[0])

    if schema_type == "object" or ("properties" in schema and schema_type is None):
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        out: dict[str, Any] = {}
        for key, child in props.items():
            if not isinstance(child, dict):
                continue
            # Include required always; also optional fields that declare example/default.
            include = key in required or "example" in child or "default" in child
            if not include:
                # Still include optional leaves for api-ref-style full previews.
                include = True
            if include:
                out[key] = schema_example(child, name=key)
        return out

    if schema_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            return [schema_example(items, name=name)]
        return []

    if schema_type == "boolean":
        return False
    if schema_type == "integer":
        minimum = schema.get("minimum")
        return int(minimum) if minimum is not None else 1
    if schema_type == "number":
        minimum = schema.get("minimum")
        return float(minimum) if minimum is not None else 1.0
    if schema_type == "null":
        return None

    # string / unknown
    fmt = schema.get("format")
    if fmt == "uri" or fmt == "url":
        return "http://example.com"
    if fmt == "email":
        return "user@example.com"
    if fmt == "uuid" or (name and (name.endswith("_id") or name == "id")):
        return "00000000-0000-0000-0000-000000000001"
    if name in {"name", "stack_name", "display_name"}:
        return "example"
    if name in {"cidr", "remote_ip_prefix"}:
        return "10.0.0.0/24"
    if name in {"password"}:
        return "secret"
    return "example"


def flatten_schema_fields(
    schema: dict[str, Any] | None,
    *,
    prefix: str = "",
    max_depth: int = 6,
) -> list[dict[str, Any]]:
    """Flatten a JSON Schema into dotted PARAM field descriptors for the console."""

    if not schema or max_depth < 0:
        return []
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((t for t in schema_type if t != "null"), schema_type[0])

    props = schema.get("properties")
    if (schema_type == "object" or props) and isinstance(props, dict):
        required = set(schema.get("required") or [])
        fields: list[dict[str, Any]] = []
        for key, child in props.items():
            if not isinstance(child, dict):
                continue
            path = f"{prefix}.{key}" if prefix else key
            child_type = child.get("type")
            if isinstance(child_type, list):
                child_type = next((t for t in child_type if t != "null"), child_type[0])
            nested_props = child.get("properties")
            if (child_type == "object" or nested_props) and isinstance(nested_props, dict):
                fields.extend(flatten_schema_fields(child, prefix=path, max_depth=max_depth - 1))
            elif child_type == "array":
                items = child.get("items")
                if isinstance(items, dict) and (
                    items.get("type") == "object" or isinstance(items.get("properties"), dict)
                ):
                    # Expand one sample element so nested array object fields appear.
                    fields.extend(
                        flatten_schema_fields(items, prefix=f"{path}.0", max_depth=max_depth - 1)
                    )
                else:
                    fields.append(
                        {
                            "name": path,
                            "type": "array",
                            "description": child.get("description") or f"Array {path}",
                            "optional": key not in required,
                            "enum": list(child.get("enum") or []),
                            "example": schema_example(child, name=key),
                        }
                    )
            else:
                fields.append(
                    {
                        "name": path,
                        "type": str(child_type or "string"),
                        "description": child.get("description"),
                        "optional": key not in required,
                        "enum": list(child.get("enum") or []),
                        "example": schema_example(child, name=key),
                    }
                )
        return fields

    if prefix:
        return [
            {
                "name": prefix,
                "type": str(schema_type or "string"),
                "description": schema.get("description"),
                "optional": False,
                "enum": list(schema.get("enum") or []),
                "example": schema_example(schema, name=prefix),
            }
        ]
    return []


def body_fields_from_example(body_example: dict[str, Any] | None) -> list[dict[str, Any]]:
    """PARAM inputs derived from body_example, including nested scalar paths.

    Mirrors oVirt console behaviour: walk the Engine/OpenStack-shaped example and
    emit one PARAM row per leaf (dotted paths, numeric segments for arrays).
    """

    if not isinstance(body_example, dict) or not body_example:
        return []

    fields: list[dict[str, Any]] = []

    def _leaf_type(value: Any) -> str:
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int) and not isinstance(value, bool):
            return "integer"
        if isinstance(value, float):
            return "number"
        if value is None:
            return "null"
        return "string"

    def _walk(prefix: str, value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                path = f"{prefix}.{key}" if prefix else str(key)
                _walk(path, child)
            return
        if isinstance(value, list):
            if not value:
                fields.append(
                    {
                        "name": prefix,
                        "type": "array",
                        "description": prefix,
                        "optional": True,
                        "enum": [],
                        "example": [],
                    }
                )
                return
            for index, child in enumerate(value):
                path = f"{prefix}.{index}" if prefix else str(index)
                _walk(path, child)
            return
        fields.append(
            {
                "name": prefix,
                "type": _leaf_type(value),
                "description": prefix,
                "optional": True,
                "enum": [],
                "example": value,
            }
        )

    _walk("", body_example)
    return fields


def unflatten_body(values: dict[str, Any]) -> dict[str, Any]:
    """Turn dotted keys into a nested dict (supports numeric array segments)."""

    root: dict[str, Any] = {}

    def _set(path: str, value: Any) -> None:
        parts = path.split(".")
        cur: Any = root
        for i, part in enumerate(parts[:-1]):
            nxt = parts[i + 1]
            want_array = nxt.isdigit()
            if part.isdigit():
                idx = int(part)
                if not isinstance(cur, list):
                    return
                while len(cur) <= idx:
                    cur.append([] if want_array else {})
                if (
                    cur[idx] is None
                    or (want_array and not isinstance(cur[idx], list))
                    or (not want_array and not isinstance(cur[idx], dict))
                ):
                    cur[idx] = [] if want_array else {}
                cur = cur[idx]
                continue
            if want_array:
                if not isinstance(cur.get(part), list):
                    cur[part] = []
            elif not isinstance(cur.get(part), dict):
                cur[part] = {}
            cur = cur[part]
        leaf = parts[-1]
        if leaf.isdigit():
            idx = int(leaf)
            if not isinstance(cur, list):
                return
            while len(cur) <= idx:
                cur.append(None)
            cur[idx] = value
            return
        if isinstance(cur, dict):
            cur[leaf] = value

    for dotted, value in sorted(values.items(), key=lambda item: item[0].count(".")):
        if value is None or value == "":
            continue
        _set(dotted, value)
    return root
