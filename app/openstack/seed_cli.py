"""CLI entrypoint for OpenStack lab / demo cloud seeding."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

from app.config import get_settings
from app.openstack.demo_cloud import clear_openstack_state, seed_openstack_demo
from app.openstack.seed import seed_openstack


async def _run(profile: str, password: str) -> dict[str, object]:
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url.get_secret_value())
    try:
        async with conn.transaction():
            if profile in {"demo", "demo-cloud", "openstack-demo-cloud"}:
                return await seed_openstack_demo(conn, password=password)
            if profile in {"minimal", "lab", "small"}:
                await clear_openstack_state(conn)
                return await seed_openstack(conn, password=password)
            raise SystemExit(f"unknown profile: {profile} (use minimal|demo)")
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default=os.environ.get("SEED_PROFILE", "minimal"),
        help="minimal | demo",
    )
    parser.add_argument("--password", default=os.environ.get("OS_PASSWORD", "secret"))
    args = parser.parse_args(argv)
    result = asyncio.run(_run(args.profile, args.password))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
