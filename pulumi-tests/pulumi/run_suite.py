#!/usr/bin/env python3
"""Pulumi OpenStack coverage runner.

For each series (yoga → dalmatian):
  1. Activate the OpenStack pack
  2. ``pulumi up`` a pulumi_openstack program (maximises provider coverage)
  3. Assert every stack export is non-empty
  4. HTTP-probe remaining pack operations; require non-empty GET/POST bodies
  5. ``pulumi destroy``
  6. Emit JUnit + HTML report
"""

from __future__ import annotations

import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SERIES_ORDER = ("yoga", "antelope", "caracal", "dalmatian")
ROOT = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("WORKSPACE", "/workspace"))
PROGRAM = ROOT / "pulumi" / "programs" / "os_coverage"
REPORT_DIR = Path(os.environ.get("REPORT_DIR", "/reports"))

sys.path.insert(0, str(REPO))
sys.path.insert(0, str(ROOT / "pulumi"))


def _smoke() -> bool:
    return os.environ.get("TEST_SMOKE", "").strip().lower() in {"1", "true", "yes"}


def _series_list() -> list[str]:
    raw = os.environ.get("OPENSTACK_SERIES_LIST", "").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return list(SERIES_ORDER)


def _host() -> str:
    return os.environ.get("OS_GATEWAY_URL") or os.environ.get(
        "OS_AUTH_URL", "http://api-gateway:5000/v3"
    ).removesuffix("/v3").rstrip("/")


def _env_vars(series: str) -> dict[str, str]:
    backend = os.environ.get("PULUMI_BACKEND_URL", "file:///tmp/pulumi-state")
    if backend.startswith("file://"):
        Path(backend.removeprefix("file://").split("?", 1)[0]).mkdir(parents=True, exist_ok=True)
    return {
        "OS_AUTH_URL": os.environ.get("OS_AUTH_URL", f"{_host()}/v3"),
        "OS_USERNAME": os.environ.get("OS_USERNAME", "admin"),
        "OS_PASSWORD": os.environ.get("OS_PASSWORD", "secret"),
        "OS_PROJECT_NAME": os.environ.get("OS_PROJECT_NAME", "demo"),
        "OS_USER_DOMAIN_NAME": os.environ.get("OS_USER_DOMAIN_NAME", "Default"),
        "OS_PROJECT_DOMAIN_NAME": os.environ.get("OS_PROJECT_DOMAIN_NAME", "Default"),
        "OS_REGION_NAME": os.environ.get("OS_REGION_NAME", "RegionOne"),
        "OS_INTERFACE": "public",
        "OS_IDENTITY_API_VERSION": "3",
        "OPENSTACK_SERIES": series,
        "PULUMI_CONFIG_PASSPHRASE": os.environ.get("PULUMI_CONFIG_PASSPHRASE", "lab"),
        "PULUMI_BACKEND_URL": backend,
        "PYTHONPATH": f"{REPO}:{ROOT / 'pulumi'}:{os.environ.get('PYTHONPATH', '')}",
        "WORKSPACE": str(REPO),
    }


def run_pulumi_stack(series: str) -> dict[str, Any]:
    from pulumi import automation as auto

    from _lib.validate import activate_series, assert_outputs_nonempty

    host = _host()
    activate_series(host, series)
    env_vars = _env_vars(series)
    stack_name = f"os-coverage-{series}"
    t0 = time.time()

    stack = auto.create_or_select_stack(
        stack_name=stack_name,
        work_dir=str(PROGRAM),
        opts=auto.LocalWorkspaceOptions(
            env_vars=env_vars,
            # Install program requirements into workspace on first run.
        ),
    )
    try:
        stack.workspace.install_plugin("openstack", "v5.3.1")
    except Exception:  # noqa: BLE001
        pass

    try:
        # Ensure python deps for the program
        stack.workspace.run_cmd(["python3", "-m", "pip", "install", "-q", "-r", "requirements.txt"])
    except Exception:  # noqa: BLE001
        # LocalWorkspace may not expose run_cmd on all versions — pip in image instead.
        pass

    empty: list[str] = []
    outputs: dict[str, Any] = {}
    error: str | None = None
    try:
        up = stack.up(on_output=lambda _: None)
        outputs = {
            k: (v.value if hasattr(v, "value") else v) for k, v in (up.outputs or {}).items()
        }
        empty = assert_outputs_nonempty(outputs, min_count=25)
    except Exception as exc:  # noqa: BLE001
        error = str(exc)[:4000]
    finally:
        try:
            stack.destroy(on_output=lambda _: None)
        except Exception:  # noqa: BLE001
            pass

    return {
        "series": series,
        "elapsed_s": round(time.time() - t0, 2),
        "error": error,
        "outputs": {k: outputs[k] for k in sorted(outputs)},
        "empty_exports": empty,
        "ok": error is None and not empty,
    }


def run_http_coverage(series: str, *, collections_only: bool) -> dict[str, Any]:
    from _lib.http_coverage import probe_pack_operations

    return probe_pack_operations(
        series,
        host=_host(),
        collections_only=collections_only,
        require_nonempty=True,
    )


def write_junit(series_reports: list[dict[str, Any]], path: Path) -> None:
    cases: list[tuple[str, bool, str]] = []
    for rep in series_reports:
        series = rep["series"]
        pu = rep["pulumi"]
        cases.append(
            (
                f"{series}.pulumi_openstack.stack",
                not pu.get("ok", False),
                pu.get("error") or (", ".join(pu.get("empty_exports") or []) or "ok"),
            )
        )
        for empty in pu.get("empty_exports") or []:
            cases.append((f"{series}.pulumi_openstack.nonempty.{empty.split('=')[0]}", True, empty))
        http = rep.get("http") or {}
        for item in http.get("results") or []:
            name = f"{series}.http.{item.get('service')}.{item.get('operation_id')}"
            failed = (
                http.get("mode") == "lifecycle"
                and item.get("mode") == "lifecycle"
                and not item.get("succeeded")
            ) or (not item.get("ok"))
            # nonempty failures are separate entries in failures list
            cases.append(
                (
                    name,
                    bool(failed),
                    f"{item.get('method')} {item.get('path')} → {item.get('status')}",
                )
            )
        for fail in http.get("failures") or []:
            detail = str(fail.get("detail") or "")
            if detail == "empty response body":
                cases.append(
                    (
                        f"{series}.http.nonempty.{fail.get('service')}.{fail.get('operation_id')}",
                        True,
                        "empty response body",
                    )
                )
            elif fail.get("operation_id") == "coverage_incomplete" or detail.startswith(
                "coverage_incomplete"
            ):
                cases.append(
                    (
                        f"{series}.http.coverage_incomplete",
                        True,
                        detail,
                    )
                )

    suite = ET.Element(
        "testsuite",
        name="pulumi-openstack-coverage",
        tests=str(len(cases)),
        failures=str(sum(1 for _, failed, _ in cases if failed)),
    )
    for name, failed, detail in cases:
        case = ET.SubElement(suite, "testcase", classname="pulumi", name=name)
        if failed:
            node = ET.SubElement(case, "failure", message=detail[:300])
            node.text = detail
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(suite).write(path, encoding="utf-8", xml_declaration=True)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    collections_only = _smoke() or os.environ.get("COLLECTIONS_ONLY", "").lower() in {
        "1",
        "true",
        "yes",
    }
    skip_http = os.environ.get("SKIP_HTTP_COVERAGE", "").lower() in {"1", "true", "yes"}
    series_list = _series_list()
    print(
        f"Pulumi coverage: series={','.join(series_list)} "
        f"collections_only={collections_only} host={_host()}"
    )

    series_reports: list[dict[str, Any]] = []
    for series in series_list:
        print(f"==> series {series}: pulumi_openstack")
        pu = run_pulumi_stack(series)
        print(
            f"{series}: pulumi ok={pu.get('ok')} empty_exports={len(pu.get('empty_exports') or [])} "
            f"error={'yes' if pu.get('error') else 'no'}"
        )
        http: dict[str, Any]
        if skip_http:
            http = {
                "series": series,
                "total": 0,
                "expected_ops": 0,
                "coverage_incomplete": False,
                "methods": {
                    "GET": 0,
                    "POST": 0,
                    "PUT": 0,
                    "PATCH": 0,
                    "DELETE": 0,
                    "HEAD": 0,
                },
                "ok_count": 0,
                "fail_count": 0,
                "nonempty_fail_count": 0,
                "critical": 0,
                "declared_ops": 0,
                "head_ops": 0,
                "results": [],
                "failures": [],
            }
        else:
            print(f"==> series {series}: HTTP pack probe (nonempty)")
            http = run_http_coverage(series, collections_only=collections_only)
            methods = http.get("methods") or {}
            methods_s = " ".join(
                f"{m}={methods.get(m, 0)}"
                for m in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD")
            )
            print(
                f"{series}: http ok={http.get('ok_count')} fail={http.get('fail_count')} "
                f"nonempty_fail={http.get('nonempty_fail_count')} "
                f"critical={http.get('critical')} "
                f"total={http.get('total')}/{http.get('expected_ops')} "
                f"(declared={http.get('declared_ops')}+HEAD={http.get('head_ops')}) "
                f"coverage_incomplete={http.get('coverage_incomplete')} "
                f"methods[{methods_s}]"
            )
        rep = {"series": series, "pulumi": pu, "http": http}
        series_reports.append(rep)
        (REPORT_DIR / f"series-{series}.json").write_text(
            json.dumps(rep, indent=2) + "\n", encoding="utf-8"
        )

    write_junit(series_reports, REPORT_DIR / "pulumi-junit.xml")

    from _lib.report_html import write_html

    summary = {
        "series_count": len(series_reports),
        "pulumi_ok": sum(1 for r in series_reports if r["pulumi"].get("ok")),
        "pulumi_fail": sum(1 for r in series_reports if not r["pulumi"].get("ok")),
        "http_ok": sum(int(r["http"].get("ok_count", 0)) for r in series_reports),
        "http_fail": sum(
            int(r["http"].get("fail_count", 0)) + int(r["http"].get("nonempty_fail_count", 0))
            for r in series_reports
        ),
        "http_critical": sum(int(r["http"].get("critical", 0)) for r in series_reports),
        "http_declared": sum(int(r["http"].get("declared_ops", 0)) for r in series_reports),
        "http_head": sum(int(r["http"].get("head_ops", 0)) for r in series_reports),
        "http_total": sum(int(r["http"].get("total", 0)) for r in series_reports),
        "http_expected": sum(int(r["http"].get("expected_ops", 0)) for r in series_reports),
        "coverage_incomplete": sum(
            1 for r in series_reports if r["http"].get("coverage_incomplete")
        ),
        "collections_only": collections_only,
        "definition": "100% = HTTP contract matrix (pack ops + synthetic HEAD), not pulumi_openstack resource count",
    }
    html_path = write_html(REPORT_DIR, summary, series_reports)
    (REPORT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"JUnit: {REPORT_DIR / 'pulumi-junit.xml'}")
    print(f"HTML:  {html_path}")
    print(json.dumps(summary, indent=2))

    failed = (
        summary["pulumi_fail"] > 0
        or summary["http_fail"] > 0
        or summary["coverage_incomplete"] > 0
        or summary["http_critical"] > 0
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
