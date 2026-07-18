"""Live gateway probe: every pack operation must be handled (no 5xx / 501)."""

from __future__ import annotations

import os
import urllib.request

import pytest

from app.openstack.surface_probe import format_report, probe_series

pytestmark = pytest.mark.integration


def _pick_host() -> str:
    candidates = [
        os.environ.get("OS_PROBE_HOST"),
        os.environ.get("OS_HOST"),
        "http://127.0.0.1:5000",
        "http://api-gateway:5000",
        "http://localhost:5000",
    ]
    for host in candidates:
        if not host:
            continue
        try:
            with urllib.request.urlopen(f"{host.rstrip('/')}/health/live", timeout=3) as res:
                if res.status == 200:
                    return host.rstrip("/")
        except Exception:
            continue
    return ""


HOST = _pick_host()


@pytest.fixture(scope="module", autouse=True)
def _require_gateway():
    if not HOST:
        pytest.skip("OpenStack gateway unreachable")


@pytest.mark.parametrize("series", ["yoga", "antelope", "caracal", "dalmatian"])
def test_all_get_collections_live(series: str) -> None:
    report = probe_series(series, host=HOST, collections_only=True)
    assert report.results, series
    if report.failures:
        pytest.fail(format_report(report))


@pytest.mark.parametrize("series", ["yoga", "antelope", "caracal", "dalmatian"])
def test_all_operations_live(series: str) -> None:
    report = probe_series(series, host=HOST)
    assert len(report.results) >= 900
    if report.failures:
        pytest.fail(format_report(report))
