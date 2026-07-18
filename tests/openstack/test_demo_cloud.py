"""Integration tests for OpenStack demo cloud seed (requires PostgreSQL)."""

from __future__ import annotations

import os

import asyncpg
import pytest

from app.openstack.demo_cloud import (
    DEMO_CLUSTER_SIZES,
    DEMO_PROFILE,
    clear_openstack_state,
    demo_profile_name,
    is_demo_profile,
    openstack_demo_summary,
    resolve_demo_size,
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


def test_resolve_demo_sizes() -> None:
    small = resolve_demo_size("small")
    large = resolve_demo_size("demo")
    big = resolve_demo_size("big")
    assert small.hypervisors == 3 and small.servers == 50
    assert large.hypervisors == 10 and large.servers == 1000
    assert big.hypervisors == 20 and big.servers == 2000
    assert big.volumes == large.volumes * 2
    assert small.extra_networks < large.extra_networks < big.extra_networks
    assert small.keypairs_per_user < large.keypairs_per_user < big.keypairs_per_user
    assert is_demo_profile(demo_profile_name("large"))
    assert is_demo_profile(DEMO_PROFILE)
    assert not is_demo_profile("minimal")
    assert {cfg.name for cfg in DEMO_CLUSTER_SIZES.values()} == {"small", "large", "big"}


async def test_demo_seed_roundtrip(conn: asyncpg.Connection) -> None:
    # Prefer small for CI speed; still exercises full topology.
    await seed_openstack_demo(conn, size="small")
    summary = await openstack_demo_summary(conn)
    small = DEMO_CLUSTER_SIZES["small"]
    assert summary["loaded"] is True
    assert summary["servers"] == small.servers
    assert summary["hypervisors"] == small.hypervisors
    assert summary["volumes"] == small.volumes
    assert summary["size"] == "small"
    assert summary["profile"] == demo_profile_name("small")
    assert summary["projects"] == 5
    assert len(summary["sizes"]) == 3

    await clear_openstack_state(conn)
    result = await seed_openstack(conn)
    assert result["profile"] == "minimal"
    summary = await openstack_demo_summary(conn)
    assert summary["loaded"] is False
    assert summary["servers"] == 1
    assert summary["profile"] == "minimal"

    # Restore large so a shared lab DB stays usable after the test.
    await seed_openstack_demo(conn, size="large")
    summary = await openstack_demo_summary(conn)
    large = DEMO_CLUSTER_SIZES["large"]
    assert summary["loaded"] is True
    assert summary["servers"] == large.servers
    assert summary["hypervisors"] == large.hypervisors
