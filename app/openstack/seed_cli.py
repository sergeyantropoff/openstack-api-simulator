"""CLI entrypoint for OpenStack lab / demo cloud seeding."""

from __future__ import annotations

import argparse
import asyncio
import json
import os

import asyncpg

from app.config import get_settings
from app.openstack.demo_cloud import (
    DEMO_CLUSTER_SIZES,
    clear_openstack_state,
    resolve_demo_size,
    seed_openstack_demo,
)
from app.openstack.seed import seed_openstack


async def _run(profile: str, password: str) -> dict[str, object]:
    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url.get_secret_value())
    try:
        async with conn.transaction():
            key = profile.strip().lower()
            if key in {"minimal", "lab"}:
                await clear_openstack_state(conn)
                return await seed_openstack(conn, password=password)
            # demo / demo-small / small / large / big / openstack-demo-cloud:…
            try:
                cfg = resolve_demo_size(key)
            except ValueError as exc:
                known = "minimal | demo | demo-small | demo-large | demo-big | small | large | big"
                raise SystemExit(f"unknown profile: {profile} (use {known})") from exc
            return await seed_openstack_demo(conn, size=cfg.name, password=password)
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    sizes = ", ".join(sorted(DEMO_CLUSTER_SIZES))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default=os.environ.get("SEED_PROFILE", "minimal"),
        help=f"minimal | demo | demo-small | demo-large | demo-big | {sizes}",
    )
    parser.add_argument("--password", default=os.environ.get("OS_PASSWORD", "secret"))
    args = parser.parse_args(argv)
    result = asyncio.run(_run(args.profile, args.password))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
