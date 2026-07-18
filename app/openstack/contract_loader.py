"""Load and hot-swap OpenStack series contract packs from contracts/openstack/."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.openstack.opspec import OperationSpec, SeriesManifest, ServicePack
from app.openstack.request_bodies import attach_request_schemas, clear_request_body_cache

_CONTRACTS_ROOT = Path(__file__).resolve().parents[2] / "contracts" / "openstack"

_SERIES_MAJOR = {
    "yoga": 6,
    "antelope": 7,
    "caracal": 8,
    "dalmatian": 9,
}
_MAJOR_SERIES = {v: k for k, v in _SERIES_MAJOR.items()}


def contracts_root() -> Path:
    return _CONTRACTS_ROOT


def series_for_major(major: int) -> str:
    return _MAJOR_SERIES.get(major, "dalmatian")


def major_for_series(series: str) -> int:
    return _SERIES_MAJOR.get(series.lower(), 9)


def list_series() -> list[dict[str, Any]]:
    root = contracts_root()
    if not root.exists():
        return []
    result: list[dict[str, Any]] = []
    for path in sorted(root.iterdir()):
        man = path / "manifest.json"
        if not man.is_file():
            continue
        data = json.loads(man.read_text())
        microversions = [
            {
                "name": str(svc.get("name") or ""),
                "default_microversion": svc.get("default_microversion"),
                "max_microversion": svc.get("max_microversion"),
            }
            for svc in data.get("services") or []
            if isinstance(svc, dict)
            and svc.get("name")
            and (svc.get("default_microversion") or svc.get("max_microversion"))
        ]
        result.append(
            {
                "series": data.get("series", path.name),
                "major": data.get("major", major_for_series(path.name)),
                "operation_count": data.get("operation_count", 0),
                "service_count": data.get("service_count", 0),
                "checksum": data.get("checksum", ""),
                "generated_at": data.get("generated_at", ""),
                "microversions": microversions,
            }
        )
    return result


def _op_from_dict(service: str, raw: dict[str, Any]) -> OperationSpec:
    return OperationSpec(
        operation_id=str(raw["operation_id"]),
        method=raw["method"],  # type: ignore[arg-type]
        path=str(raw["path"]),
        service=service,
        resource_type=str(raw.get("resource_type") or "object"),
        collection_key=raw.get("collection_key"),
        item_key=raw.get("item_key"),
        kind=raw.get("kind") or "collection",  # type: ignore[arg-type]
        status_code=int(raw.get("status_code") or 200),
        create_status=int(raw.get("create_status") or raw.get("status_code") or 201),
        microversion_min=raw.get("microversion_min"),
        microversion_max=raw.get("microversion_max"),
        requires_auth=bool(raw.get("requires_auth", True)),
        requires_project=bool(raw.get("requires_project", True)),
        action_name=raw.get("action_name"),
        response_fixture=raw.get("response_fixture"),
        notes=str(raw.get("notes") or ""),
    )


def load_series_pack(series: str) -> dict[str, ServicePack]:
    series = series.lower()
    series_dir = contracts_root() / series
    man_path = series_dir / "manifest.json"
    if not man_path.is_file():
        raise FileNotFoundError(f"OpenStack contract pack not found: {series_dir}")
    packs: dict[str, ServicePack] = {}
    for svc_dir in sorted(series_dir.iterdir()):
        api = svc_dir / "api.json"
        if not api.is_file():
            continue
        data = json.loads(api.read_text())
        name = str(data["service"])
        ops = [_op_from_dict(name, raw) for raw in data.get("operations") or []]
        ops = attach_request_schemas(name, ops)
        packs[name] = ServicePack(
            name=name,
            typ=str(data.get("type") or name),
            port=int(data["port"]),
            version_path=str(data.get("version_path") or "/"),
            default_microversion=data.get("default_microversion"),
            max_microversion=data.get("max_microversion"),
            operations=ops,
        )
    return packs


def load_manifest(series: str) -> SeriesManifest:
    data = json.loads((contracts_root() / series.lower() / "manifest.json").read_text())
    services = list(data.get("services") or [])
    return SeriesManifest(
        series=str(data["series"]),
        major=int(data["major"]),
        services=services,
        checksum=str(data.get("checksum") or ""),
        generated_at=str(data.get("generated_at") or ""),
        operation_count=int(data.get("operation_count") or 0),
        service_count=int(data.get("service_count") or len(services)),
    )


@dataclass
class ContractRuntime:
    """Process-wide active OpenStack contract pack + per-service microversion overrides."""

    series: str = "dalmatian"
    packs: dict[str, ServicePack] = field(default_factory=dict)
    microversion_overrides: dict[str, str] = field(default_factory=dict)
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def reload(self, series: str | None = None) -> dict[str, Any]:
        with self._lock:
            clear_request_body_cache()
            target = (series or self.series).lower()
            series_changed = target != self.series
            self.packs = load_series_pack(target)
            self.series = target
            if series_changed:
                self.microversion_overrides.clear()
            man = load_manifest(target)
            return {
                "series": man.series,
                "major": man.major,
                "operation_count": man.operation_count,
                "service_count": man.service_count,
                "checksum": man.checksum,
                "services": sorted(self.packs.keys()),
            }

    def summary(self) -> dict[str, Any]:
        with self._lock:
            man = None
            try:
                man = load_manifest(self.series)
            except FileNotFoundError:
                pass
            return {
                "series": self.series,
                "major": major_for_series(self.series),
                "operation_count": sum(p.operation_count() for p in self.packs.values()),
                "service_count": len(self.packs),
                "checksum": man.checksum if man else "",
                "microversion_overrides": dict(self.microversion_overrides),
                "services": [
                    {
                        "name": p.name,
                        "type": p.typ,
                        "port": p.port,
                        "operation_count": p.operation_count(),
                        "default_microversion": p.default_microversion,
                        "max_microversion": p.max_microversion,
                        "active_microversion": self.microversion_overrides.get(
                            p.name, p.default_microversion
                        ),
                    }
                    for p in sorted(self.packs.values(), key=lambda x: x.name)
                ],
            }

    def set_microversion(self, service: str, version: str | None) -> None:
        with self._lock:
            if version is None:
                self.microversion_overrides.pop(service, None)
            else:
                self.microversion_overrides[service] = version

    def active_microversion(self, service: str) -> str | None:
        with self._lock:
            if service in self.microversion_overrides:
                return self.microversion_overrides[service]
            pack = self.packs.get(service)
            return pack.default_microversion if pack else None


_RUNTIME = ContractRuntime()


def get_runtime() -> ContractRuntime:
    return _RUNTIME


def ensure_loaded(series: str = "dalmatian") -> ContractRuntime:
    rt = get_runtime()
    if not rt.packs:
        try:
            rt.reload(series)
        except FileNotFoundError:
            pass
    return rt
