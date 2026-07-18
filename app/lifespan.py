"""Application resource ownership."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

from fastapi import FastAPI

from app.config import Settings
from app.db.pool import AsyncpgDatabase, Database

DatabaseFactory = Callable[[Settings], Database]
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


class LifespanWorker(Protocol):
    async def run(self) -> None: ...

    def stop(self) -> None: ...


WorkerFactory = Callable[[Database], LifespanWorker]


def create_lifespan(
    settings: Settings,
    database_factory: DatabaseFactory,
    worker_factories: tuple[WorkerFactory, ...] = (),
) -> Lifespan:
    """Build a lifespan context so tests can inject a database implementation."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = database_factory(settings)
        await database.connect()
        app.state.database = database
        if isinstance(database, AsyncpgDatabase):
            from app.openstack.demo_cloud import is_demo_profile
            from app.openstack.seed import seed_openstack

            async with database.pool.acquire() as connection:
                # Preserve a loaded demo cloud across restarts; only seed minimal lab otherwise.
                try:
                    profile = await connection.fetchval(
                        "SELECT value FROM os_demo_meta WHERE key = 'profile'"
                    )
                except Exception:
                    profile = None
                if not is_demo_profile(profile):
                    await seed_openstack(connection)
        workers = tuple(factory(database) for factory in worker_factories)
        worker_tasks = tuple(asyncio.create_task(worker.run()) for worker in workers)
        try:
            yield
        finally:
            for worker in workers:
                worker.stop()
            if worker_tasks:
                await asyncio.gather(*worker_tasks)
            await database.close()

    return lifespan


def default_database_factory(settings: Settings) -> Database:
    """Create the production asyncpg adapter."""

    return AsyncpgDatabase(settings)
