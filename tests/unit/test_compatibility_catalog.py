"""Catalog-scoped compatibility payload tests."""

from datetime import UTC, datetime
from typing import cast

from httpx import ASGITransport, AsyncClient

from app.compatibility import CompatibilityDimension, build_report
from app.config import Settings
from app.contracts.model import Method, PathContract, Schema, Snapshot
from app.main import create_app
from app.web.compatibility_catalog import compatibility_payload
from tests.unit.test_health import FakeDatabase


def _snapshot(source_version: str, path: str) -> Snapshot:
    method = Method(
        verb="GET",
        name="index",
        returns=Schema(type="object"),
        checksum="1" * 64,
    )
    return Snapshot(
        source_version=source_version,
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        raw_sha256="0" * 64,
        paths=(PathContract(path=path, methods=(method,)),),
        path_count=1,
        method_count=1,
    )


def test_catalog_compatibility_uses_selected_snapshot_version() -> None:
    runtime_snapshot = _snapshot("9.2.3", "/version")
    catalog_snapshot = _snapshot("7.4-16", "/nodes")
    runtime_report = build_report(
        runtime_snapshot,
        implemented=frozenset({("/version", "GET")}),
        dimensions={CompatibilityDimension.ROUTE_METHOD: frozenset({("/version", "GET")})},
    )
    payload = compatibility_payload(
        catalog_snapshot,
        7,
        implemented_methods=frozenset({("/nodes", "GET"), ("/version", "GET")}),
        runtime_report=runtime_report,
        runtime_version="9.2.3",
        settings=None,
    )
    assert payload["catalog_version"] == "7.4-16"
    assert payload["runtime_version"] == "9.2.3"
    assert payload["evidence_scope"] == "catalog"
    assert payload["total_declared"] == 1
    levels = cast(dict[str, dict[str, object]], payload["levels"])
    assert levels["implemented"]["count"] == 1


def test_catalog_compatibility_reuses_runtime_report_for_matching_version() -> None:
    runtime_snapshot = _snapshot("9.2.3", "/version")
    runtime_report = build_report(
        runtime_snapshot,
        implemented=frozenset({("/version", "GET")}),
        dimensions={CompatibilityDimension.ROUTE_METHOD: frozenset({("/version", "GET")})},
    )
    payload = compatibility_payload(
        runtime_snapshot,
        9,
        implemented_methods=frozenset({("/version", "GET")}),
        runtime_report=runtime_report,
        runtime_version="9.2.3",
        settings=None,
    )
    assert payload["catalog_version"] == "9.2.3"
    assert payload["evidence_scope"] == "full"


async def test_ui_compatibility_endpoint_follows_selected_major() -> None:
    app = create_app(
        settings=Settings(contract_snapshot=None),
        database_factory=lambda _settings: FakeDatabase(True),
        worker_factories=(),
    )
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            major7 = await client.get("/ui/api/compatibility", params={"major": 7})
            major9 = await client.get("/ui/api/compatibility", params={"major": 9})
    assert major7.status_code == 200
    assert major9.status_code == 200
    body7 = major7.json()
    body9 = major9.json()
    assert body7["catalog_version"] == "openstack-antelope"
    assert body9["catalog_version"] == "openstack-dalmatian"
    assert body7["total_declared"] >= 1100
    assert body9["total_declared"] >= 1300
    assert body7["major"] == 7
    assert body9["major"] == 9
    assert body7["levels"]["implemented"]["count"] == body7["total_declared"]
    assert body9["levels"]["implemented"]["count"] == body9["total_declared"]


async def test_ui_compatibility_covers_all_openstack_series() -> None:
    app = create_app(
        settings=Settings(contract_snapshot=None, compatibility_evidence=None),
        database_factory=lambda _settings: FakeDatabase(True),
        worker_factories=(),
    )
    expected = {
        6: "openstack-yoga",
        7: "openstack-antelope",
        8: "openstack-caracal",
        9: "openstack-dalmatian",
    }
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for major, catalog_version in expected.items():
                response = await client.get("/ui/api/compatibility", params={"major": major})
                assert response.status_code == 200
                body = response.json()
                assert body["catalog_version"] == catalog_version
                assert body["levels"]["implemented"]["count"] == body["total_declared"]
