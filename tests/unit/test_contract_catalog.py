"""Contract catalog helpers."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.config import Settings
from app.contracts.model import Method, Parameter, PathContract, Schema, Snapshot
from app.web.contract_catalog import catalog_payload, list_majors, method_payload


def _snapshot() -> Snapshot:
    method = Method(
        verb="POST",
        name="create",
        description="Create a VM.",
        parameters=(
            Parameter(name="node", definition=Schema(type="string")),
            Parameter(name="vmid", definition=Schema(type="integer", minimum=100)),
            Parameter(name="name", definition=Schema(type="string")),
            Parameter(name="memory", definition=Schema(type="integer", optional=True)),
            Parameter(name="scsi[n]", definition=Schema(type="string", optional=True)),
        ),
        returns=Schema(type="string"),
        checksum="a" * 64,
    )
    return Snapshot(
        source_version="9.2.3",
        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        raw_sha256="b" * 64,
        paths=(PathContract(path="/nodes/{node}/qemu", methods=(method,)),),
        path_count=1,
        method_count=1,
    )


def test_list_majors_includes_latest_releases() -> None:
    payload = list_majors(runtime_version="9.2.3")
    majors_list = cast(list[dict[str, Any]], payload["majors"])
    majors = {item["major"] for item in majors_list}
    series = {item["series"] for item in majors_list}
    assert majors == {6, 7, 8, 9}
    assert series == {"Yoga", "Antelope", "Caracal", "Dalmatian"}
    assert payload["runtime_version"] == "9.2.3"


def test_list_majors_includes_artifact_urls() -> None:
    payload = list_majors(runtime_version="9.2.3")
    majors_list = cast(list[dict[str, Any]], payload["majors"])
    dalmatian = next(item for item in majors_list if item["major"] == 9)
    assert dalmatian["series"] == "Dalmatian"
    assert dalmatian["artifact_url"] == "stub://openstack/dalmatian/api-contract"
    assert dalmatian["bundled"] is True


def test_list_majors_honors_settings_overrides() -> None:
    settings = Settings(catalog_artifact_url_9="https://example.test/dalmatian/apidoc.js")
    payload = list_majors(runtime_version=None, settings=settings)
    majors_list = cast(list[dict[str, Any]], payload["majors"])
    dalmatian = next(item for item in majors_list if item["major"] == 9)
    assert dalmatian["artifact_url"] == "https://example.test/dalmatian/apidoc.js"


def test_catalog_payload_groups_paths_by_tag() -> None:
    payload = catalog_payload(
        _snapshot(),
        9,
        implemented_methods=frozenset({("/nodes/{node}/qemu", "POST")}),
    )
    assert payload["source_version"] == "9.2.3"
    assert payload["series"] == "Dalmatian"
    assert cast(str, payload["artifact_url"]).endswith("dalmatian/api-contract")
    assert payload["latest_version"] == "9.2.3"
    assert payload["path_count"] == 1
    categories = cast(list[dict[str, Any]], payload["categories"])
    method = categories[0]["paths"][0]["methods"][0]
    assert method["verb"] == "POST"
    assert method["implemented"] is True


def test_method_payload_builds_examples() -> None:
    payload = method_payload(
        _snapshot(),
        major=9,
        path="/nodes/{node}/qemu",
        verb="POST",
        runtime_version="9.2.3",
        implemented_methods=frozenset({("/nodes/{node}/qemu", "POST")}),
    )
    assert payload["resolved_path"] == "/nodes/pve01/qemu"
    assert payload["body_example"] == {"vmid": 100, "name": "example"}
    assert payload["implemented"] is True


@pytest.mark.asyncio
async def test_load_snapshot_uses_bundled_revision() -> None:
    from app.web import contract_catalog

    contract_catalog._SNAPSHOT_CACHE.clear()
    root = Path("contracts")
    snapshot = await contract_catalog.load_snapshot(9, root)
    assert snapshot.source_version == "9.2.3"
