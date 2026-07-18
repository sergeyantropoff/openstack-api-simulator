"""Web console route tests."""

from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.unit.test_health import FakeDatabase


async def test_root_console_is_served() -> None:
    app = create_app(database_factory=lambda _settings: FakeDatabase(True), worker_factories=())
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/console")
    assert response.status_code == 200
    assert "OpenStack API Emulator" in response.text
    assert "openstack" in response.text
    assert 'id="catalog-drawer"' in response.text
    assert "catalog-drawer" in response.text
    assert 'id="help-drawer"' in response.text
    assert 'id="help-badge"' in response.text
    assert 'id="data-badge"' in response.text
    assert 'id="data-drawer"' in response.text
    assert "data-badge-btn" in response.text
    assert 'id="endpoints-badge-count"' in response.text
    assert 'id="endpoints-drawer-count"' in response.text
    assert 'id="ui-modal"' in response.text
    assert 'role="alertdialog"' in response.text
    assert "Request body" in response.text


async def test_ui_method_server_list_is_implemented() -> None:
    app = create_app(database_factory=lambda _settings: FakeDatabase(True), worker_factories=())
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            method = await client.get(
                "/ui/api/method",
                params={"major": 9, "path": "/v2.1/servers", "verb": "GET"},
            )
            assert method.status_code == 200
            payload = method.json()
            assert payload["implemented"] is True
            assert payload["name"] == "server_list"
            assert payload["service"] == "nova"


async def test_ui_catalog_server_list_is_implemented() -> None:
    app = create_app(database_factory=lambda _settings: FakeDatabase(True), worker_factories=())
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            catalog = await client.get("/ui/api/catalog", params={"major": 9})
            assert catalog.status_code == 200
            body = catalog.json()
            assert body["source_version"] == "openstack-dalmatian"
            methods = {
                (path["path"], method["name"]): method["implemented"]
                for category in body["categories"]
                for path in category["paths"]
                for method in path["methods"]
            }
            assert methods[("/v2.1/servers", "server_list")] is True


async def test_demo_api_requires_database() -> None:
    app = create_app(database_factory=lambda _settings: FakeDatabase(True), worker_factories=())
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            state = await client.get("/ui/api/demo/state")
            load = await client.post("/ui/api/demo/load")
    assert state.status_code == 503
    assert load.status_code == 503


async def test_ui_versions_and_catalog_endpoints() -> None:
    app = create_app(database_factory=lambda _settings: FakeDatabase(True), worker_factories=())
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            versions = await client.get("/ui/api/versions")
            assert versions.status_code == 200
            majors = versions.json()["majors"]
            assert {item["major"] for item in majors} == {6, 7, 8, 9}
            assert {item["latest_version"] for item in majors} == {
                "yoga",
                "antelope",
                "caracal",
                "dalmatian",
            }
            catalog = await client.get("/ui/api/catalog", params={"major": 9})
            assert catalog.status_code == 200
            assert catalog.json()["source_version"] == "openstack-dalmatian"
            method = await client.get(
                "/ui/api/method",
                params={"major": 9, "path": "/v2.1/servers", "verb": "GET"},
            )
            assert method.status_code == 200
            assert method.json()["path"] == "/v2.1/servers"
            assert method.json()["name"] == "server_list"
