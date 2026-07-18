"""Integration tests for OpenStack demo cloud seed (requires PostgreSQL)."""

from __future__ import annotations

import os

import asyncpg
import pytest

from app.openstack.demo_cloud import (
    DEMO_PROFILE,
    DEMO_SERVER_COUNT,
    clear_openstack_state,
    openstack_demo_summary,
    seed_openstack_demo,
)
from app.openstack.seed import seed_openstack

pytestmark = pytest.mark.integration


def _dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        os.environ.get(
            "DATABASE_URL",
            "postgresql://openstack:openstack@127.0.0.1:5433/openstack_simulator",
        ),
    )


@pytest.fixture
async def conn():
    try:
        connection = await asyncpg.connect(_dsn())
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"postgres unavailable: {exc}")
    try:
        yield connection
    finally:
        await connection.close()


async def test_demo_seed_roundtrip(conn: asyncpg.Connection) -> None:
    await seed_openstack_demo(conn)
    summary = await openstack_demo_summary(conn)
    assert summary["loaded"] is True
    assert summary["servers"] == DEMO_SERVER_COUNT
    assert summary["hypervisors"] == 16
    assert summary["projects"] == 5
    assert summary["volumes"] == 600
    assert summary["profile"] == DEMO_PROFILE

    await clear_openstack_state(conn)
    result = await seed_openstack(conn)
    assert result["profile"] == "minimal"
    summary = await openstack_demo_summary(conn)
    assert summary["loaded"] is False
    assert summary["servers"] == 1
    assert summary["profile"] == "minimal"

    # Restore demo so a shared lab DB stays usable after the test.
    await seed_openstack_demo(conn)
    summary = await openstack_demo_summary(conn)
    assert summary["loaded"] is True
    assert summary["servers"] == DEMO_SERVER_COUNT
