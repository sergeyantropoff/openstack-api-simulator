#!/usr/bin/env python3
"""Import requestBody schemas from gtema/openstack-openapi into request_bodies/.

Discovers versioned OpenAPI YAML under ``specs/<service>/`` and merges request
schemas into ``contracts/openstack/request_bodies/<service>.json``.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "contracts" / "openstack" / "request_bodies"

SERVICE_MAP = {
    "compute": "nova",
    "network": "neutron",
    "identity": "keystone",
    "image": "glance",
    "block-storage": "cinder",
    "load-balancing": "octavia",
    "object-store": "swift",
    "placement": "placement",
}

API_CONTENTS = (
    "https://api.github.com/repos/gtema/openstack-openapi/contents/specs/{svc}?ref=main"
)


def _load_yaml(text: str) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("PyYAML is required: pip install pyyaml") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("OpenAPI root must be a mapping")
    return data


def _http_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def _http_text(url: str, *, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=180) as resp:
                chunks: list[bytes] = []
                while True:
                    block = resp.read(1024 * 1024)
                    if not block:
                        break
                    chunks.append(block)
                return b"".join(chunks).decode()
        except Exception as exc:
            last_error = exc
            print(f"  download attempt {attempt}/{attempts} failed: {exc}")
    if last_error is None:
        raise RuntimeError("download failed without error")
    raise last_error


def _pick_spec_url(openapi_name: str) -> str:
    entries = _http_json(API_CONTENTS.format(svc=openapi_name))
    yaml_files = [
        item
        for item in entries
        if item.get("type") == "file" and str(item.get("name", "")).endswith(".yaml")
    ]
    if not yaml_files:
        raise FileNotFoundError(f"No OpenAPI YAML under specs/{openapi_name}")

    def sort_key(item: dict[str, Any]) -> tuple[int, ...]:
        name = str(item["name"])
        nums = [int(x) for x in re.findall(r"\d+", name)]
        return tuple(nums) if nums else (0,)

    # Prefer the highest versioned file (e.g. v2.96.yaml over v2.yaml).
    best = sorted(yaml_files, key=sort_key)[-1]
    url = best.get("download_url")
    if not url:
        raise FileNotFoundError(best)
    return str(url)


def _resolve_ref(doc: dict[str, Any], node: Any) -> Any:
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/"):
        return {k: _resolve_ref(doc, v) for k, v in node.items() if k != "$ref"}
    cursor: Any = doc
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        cursor = cursor[part]
    return _resolve_ref(doc, cursor)


def _request_schema(doc: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any] | None:
    body = operation.get("requestBody")
    if not body:
        return None
    body = _resolve_ref(doc, body)
    content = body.get("content") or {}
    for key in ("application/json", "application/openstack-images-v2.1-json-patch"):
        if key in content:
            media = _resolve_ref(doc, content[key])
            schema = media.get("schema")
            if schema:
                return _resolve_ref(doc, schema)
    for media in content.values():
        media = _resolve_ref(doc, media)
        schema = media.get("schema")
        if schema:
            return _resolve_ref(doc, schema)
    return None


def _normalize_path(path: str) -> str:
    parts = [p for p in path.split("/") if p not in {"{project_id}", "{tenant_id}"}]
    normalized = "/" + "/".join(p for p in parts if p)
    return normalized.replace("//", "/")


def import_service(openapi_name: str, pack_name: str) -> int:
    url = _pick_spec_url(openapi_name)
    print(f"Fetching {url}")
    doc = _load_yaml(_http_text(url))
    paths = doc.get("paths") or {}
    by_path: dict[str, dict[str, Any]] = {}
    for path, item in paths.items():
        if not isinstance(item, dict):
            continue
        norm = _normalize_path(str(path))
        for method, operation in item.items():
            if method.upper() not in {"POST", "PUT", "PATCH"}:
                continue
            if not isinstance(operation, dict):
                continue
            schema = _request_schema(doc, operation)
            if not schema:
                continue
            by_path[f"{method.upper()} {norm}"] = schema

    out_path = OUT_DIR / f"{pack_name}.json"
    existing: dict[str, Any] = {"service": pack_name, "operations": {}, "by_path": {}}
    if out_path.is_file():
        existing = json.loads(out_path.read_text())
    operations = dict(existing.get("operations") or {})
    existing_by_path = dict(existing.get("by_path") or {})
    # OpenAPI schemas override generated stubs for matching paths.
    existing_by_path.update(by_path)

    matched = 0
    pack_api = ROOT / "contracts" / "openstack" / "dalmatian" / pack_name / "api.json"
    if pack_api.is_file():
        pack = json.loads(pack_api.read_text())
        for op in pack.get("operations") or []:
            if op.get("method") not in {"POST", "PUT", "PATCH"}:
                continue
            key = f"{op['method']} {op['path']}"
            schema = existing_by_path.get(key)
            if schema is None:
                continue
            operations[op["operation_id"]] = schema
            matched += 1

    payload = {
        "service": pack_name,
        "source": f"openstack-openapi:{openapi_name}",
        "operations": operations,
        "by_path": existing_by_path,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"  {pack_name}: openapi_paths={len(by_path)} matched_ops={matched} → {out_path}")
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--service",
        action="append",
        choices=sorted(SERVICE_MAP),
        help="OpenAPI service dir (repeatable). Default: all Tier-1",
    )
    args = parser.parse_args()
    selected = args.service or list(SERVICE_MAP)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = 0
    for openapi_name in selected:
        total += import_service(openapi_name, SERVICE_MAP[openapi_name])
    print(f"Done. matched operation schemas: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
