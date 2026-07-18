"""Stable UUIDs for seeded OpenStack entities."""

from __future__ import annotations

import uuid

NAMESPACE = uuid.UUID("7e2c0f9a-4b11-4d6e-9c3a-0a0b0c0d0e0f")


def oid(name: str) -> uuid.UUID:
    return uuid.uuid5(NAMESPACE, name)
