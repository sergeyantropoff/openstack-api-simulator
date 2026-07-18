"""OpenStack pack remount via /ui/api/contract/apply."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from tests.unit.test_health import FakeDatabase

_SERIES = {
    6: "yoga",
    7: "antelope",
    8: "caracal",
    9: "dalmatian",
}


def _app():
    return create_app(
        settings=Settings(contract_snapshot=None),
        database_factory=lambda _settings: FakeDatabase(True),
        worker_factories=(),
    )


async def test_contract_apply_swaps_openstack_series() -> None:
    app = _app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            versions = await client.get("/ui/api/versions")
            assert versions.status_code == 200
            assert {item["major"] for item in versions.json()["majors"]} == {6, 7, 8, 9}

            applied = await client.post("/ui/api/contract/apply", params={"major": 7})
            assert applied.status_code == 200
            payload = applied.json()
            assert payload["ok"] is True
            assert payload["major"] == 7
            assert payload["series"] == "antelope"
            assert payload["runtime_version"] == "openstack-antelope"
            assert (payload.get("method_count") or payload.get("operation_count") or 0) > 0

            versions_after = await client.get("/ui/api/versions")
            assert versions_after.json()["runtime_version"] == "openstack-antelope"

            restored = await client.post("/ui/api/contract/apply", params={"major": 9})
            assert restored.status_code == 200
            assert restored.json()["runtime_version"] == "openstack-dalmatian"
            assert (await client.get("/ui/api/versions")).json()["runtime_version"] == (
                "openstack-dalmatian"
            )


@pytest.mark.parametrize("major,series", list(_SERIES.items()))
async def test_contract_apply_sets_runtime_per_series(major: int, series: str) -> None:
    app = _app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            applied = await client.post("/ui/api/contract/apply", params={"major": major})
            assert applied.status_code == 200
            body = applied.json()
            assert body["runtime_version"] == f"openstack-{series}"
            assert body["series"] == series


async def test_contract_apply_works_without_proxmox_snapshot() -> None:
    app = _app()
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/ui/api/contract/apply", params={"major": 7})
    assert response.status_code == 200
    assert response.json()["runtime_version"] == "openstack-antelope"
