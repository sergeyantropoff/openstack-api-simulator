"""Helpers for series activation and non-empty validation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


def activate_series(host: str, series: str) -> None:
    body = json.dumps({"series": series}).encode()
    req = urllib.request.Request(
        f"{host.rstrip('/')}/ui/api/openstack/contracts/activate",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            if res.status >= 400:
                raise RuntimeError(f"activate {series}: HTTP {res.status}")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        raise RuntimeError(f"activate {series}: HTTP {exc.code} {raw[:300]}") from exc


def is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    if isinstance(value, (list, tuple, set, dict)) and len(value) == 0:
        return False
    return True


def assert_outputs_nonempty(outputs: dict[str, Any], *, min_count: int = 15) -> list[str]:
    """Return list of failing export names (empty if all good)."""
    failures: list[str] = []
    if len(outputs) < min_count:
        failures.append(f"__export_count__={len(outputs)}<{min_count}")
    for key, value in sorted(outputs.items()):
        if not is_nonempty(value):
            failures.append(f"{key}={value!r}")
    return failures


def payload_nonempty(
    payload: Any, *, collection_key: str | None = None, method: str = "GET"
) -> bool:
    """True when a successful response body has meaningful content.

    For GET list/show and POST create we require real data — empty ``[]`` /
    ``{}`` / blank strings fail. DELETE/204-style empties are not checked here.
    """
    if payload is None:
        return False
    if isinstance(payload, str):
        return bool(payload.strip())
    if isinstance(payload, list):
        return len(payload) > 0
    if not isinstance(payload, dict):
        return True
    if collection_key and collection_key in payload:
        value = payload[collection_key]
        if isinstance(value, list):
            return len(value) > 0
        return is_nonempty(value)
    # Common OpenStack envelopes
    for key, value in payload.items():
        if key in {"versions", "version", "id", "token", "links", "status", "name"}:
            if is_nonempty(value):
                return True
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and (value.get("id") or value.get("name") or value.get("uuid")):
            return True
        if isinstance(value, str) and value.strip():
            return True
        if isinstance(value, (int, float, bool)):
            return True
    # Non-empty dict with any nested content
    return any(is_nonempty(v) for v in payload.values())
