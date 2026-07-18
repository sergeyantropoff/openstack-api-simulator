"""Shared plural→singular helpers for OpenStack resource keys."""

from __future__ import annotations

# Words that already look plural-ending but must not lose a trailing "s".
_IRREGULAR: dict[str, str] = {
    "status": "status",
    "statuses": "status",
    "addresses": "address",
    "quotas": "quota",
    "metadata": "metadata",
    "series": "series",
    "os-services": "os-service",
    "os-hosts": "os-host",
}


def singular(collection_key: str) -> str:
    """Return a singular resource key for an OpenStack collection name."""

    key = collection_key.strip()
    if not key:
        return key
    lower = key.lower()
    if lower in _IRREGULAR:
        return _IRREGULAR[lower]
    if key.endswith("ies") and len(key) > 3:
        return key[:-3] + "y"
    if key.endswith("ses") and len(key) > 3:
        return key[:-2]
    if key.endswith("s") and not key.endswith("ss"):
        return key[:-1]
    return key
