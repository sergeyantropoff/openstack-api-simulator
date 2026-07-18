"""Per-series OpenStack surface deltas (Yoga → Dalmatian).

Dalmatian keeps the full inventory. Older series drop paths introduced later
and use lower microversion ceilings.
"""

from __future__ import annotations

from typing import Any

SERIES_ORDER = ("yoga", "antelope", "caracal", "dalmatian")

# Approximate public API microversion ceilings per coordinated release.
SERIES_MICROVERSIONS: dict[str, dict[str, tuple[str, str]]] = {
    "yoga": {
        "nova": ("2.1", "2.90"),
        "cinder": ("3.0", "3.68"),
        "placement": ("1.0", "1.36"),
        "ironic": ("1.1", "1.82"),
        "manila": ("2.0", "2.70"),
    },
    "antelope": {
        "nova": ("2.1", "2.93"),
        "cinder": ("3.0", "3.69"),
        "placement": ("1.0", "1.37"),
        "ironic": ("1.1", "1.84"),
        "manila": ("2.0", "2.74"),
    },
    "caracal": {
        "nova": ("2.1", "2.95"),
        "cinder": ("3.0", "3.70"),
        "placement": ("1.0", "1.38"),
        "ironic": ("1.1", "1.88"),
        "manila": ("2.0", "2.79"),
    },
    "dalmatian": {
        "nova": ("2.1", "2.96"),
        "cinder": ("3.0", "3.70"),
        "placement": ("1.0", "1.39"),
        "ironic": ("1.1", "1.90"),
        "manila": ("2.0", "2.82"),
    },
}

# Path prefixes first available in a given series (inclusive).
# Anything not matched is available from Yoga.
PATH_INTRODUCED: list[tuple[str, str]] = [
    # Antelope
    ("/v2.1/servers/{server_id}/diagnostics", "antelope"),
    ("/v2.1/servers/{server_id}/remote-consoles", "antelope"),
    ("/v2.1/os-simple-tenant-usage", "antelope"),
    ("/v2.1/flavors/{id}/os-extra_specs", "antelope"),
    ("/v2.1/servers/{server_id}/os-instance-actions/{request_id}", "antelope"),
    ("/v2.0/local_ips", "antelope"),
    ("/v2.0/ndp_proxies", "antelope"),
    ("/v2.0/log/", "antelope"),
    ("/v2/lbaas/flavorprofiles", "antelope"),
    ("/v2/octavia/amphorae", "antelope"),
    ("/v2/share-groups", "antelope"),
    ("/v2/shares/{id}/action", "antelope"),
    # Caracal
    ("/v2.1/os-hosts", "caracal"),
    ("/v2.1/os-assisted-volume-snapshots", "caracal"),
    ("/v2.1/os-server-external-events", "caracal"),
    ("/v2.1/os-instance_usage_audit_log", "caracal"),
    ("/v2.0/routers/{router_id}/conntrack_helpers", "caracal"),
    ("/v2.0/bgpvpn/", "caracal"),
    ("/v2.0/vpn/", "caracal"),
    ("/v2/lbaas/providers", "caracal"),
    ("/v2/lbaas/l7policies", "caracal"),
    ("/v2/zones/{zone_id}/recordsets", "caracal"),  # keep zones themselves in yoga
    ("/v2/tlds", "caracal"),
    ("/v2/blacklists", "caracal"),
    ("/vnfpkgm/", "caracal"),
    ("/vnflcm/", "caracal"),
    # Dalmatian
    ("/v2.0/network-ip-availabilities", "dalmatian"),
    ("/v2.0/auto-allocated-topology", "dalmatian"),
    ("/v2.0/qos/rule-types", "dalmatian"),
    ("/v2.0/fwaas/", "dalmatian"),
    ("/v2.0/address-groups", "dalmatian"),
    ("/v2.0/bgp-speakers", "dalmatian"),
    ("/v2.0/bgp-peers", "dalmatian"),
    ("/v2.0/segments", "dalmatian"),
    ("/v2.0/network_segment_ranges", "dalmatian"),
    ("/v2.0/default-security-group-rules", "dalmatian"),
    ("/v2.0/vpn/ikepolicies", "dalmatian"),
    ("/v2.0/vpn/ipsecpolicies", "dalmatian"),
    ("/v2.0/vpn/endpoint-groups", "dalmatian"),
    ("/v2.1/extensions", "dalmatian"),
    ("/v2.1/os-agents", "dalmatian"),
    ("/v2.1/servers/{server_id}/migrations", "dalmatian"),
    ("/v2.1/servers/{server_id}/consoles", "dalmatian"),
    ("/v2.1/servers/{server_id}/topology", "dalmatian"),
    ("/v2.1/os-console-auth-tokens", "dalmatian"),
    ("/v2/info/import", "dalmatian"),
    ("/v2/info/stores", "dalmatian"),
    ("/v1/capsules", "dalmatian"),
    ("/v2/share-replicas", "dalmatian"),
    ("/v1/audit_templates", "dalmatian"),
    ("/v1/audits", "dalmatian"),
    ("/v1/action_plans", "dalmatian"),
    ("/v1/scoring_engines", "dalmatian"),
    ("/v2/queues", "dalmatian"),
    ("/v2/health", "dalmatian"),
    ("/v2/ping", "dalmatian"),
]


def series_index(series: str) -> int:
    try:
        return SERIES_ORDER.index(series)
    except ValueError as exc:
        raise ValueError(f"unknown series: {series}") from exc


def _path_introduced(path: str) -> str:
    best = "yoga"
    best_idx = 0
    for prefix, series in PATH_INTRODUCED:
        if path == prefix or path.startswith(prefix):
            idx = series_index(series)
            if idx >= best_idx:
                best = series
                best_idx = idx
    return best


def apply_introduced_tags(ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for op in ops:
        item = dict(op)
        if "introduced_in" not in item:
            item["introduced_in"] = _path_introduced(str(item.get("path") or ""))
        out.append(item)
    return out


def filter_ops_for_series(ops: list[dict[str, Any]], series: str) -> list[dict[str, Any]]:
    target = series_index(series)
    kept: list[dict[str, Any]] = []
    for op in apply_introduced_tags(ops):
        since = str(op.get("introduced_in") or "yoga")
        if series_index(since) <= target:
            # Drop series-private metadata from emitted contracts (keep path surface clean).
            emitted = {k: v for k, v in op.items() if k != "introduced_in"}
            # Still keep introduced_in for UI / debugging — useful for operators.
            emitted["introduced_in"] = since
            kept.append(emitted)
    return kept


def microversions_for(
    series: str,
    service: str,
    default_min: str | None,
    default_max: str | None,
) -> tuple[str | None, str | None]:
    table = SERIES_MICROVERSIONS.get(series) or {}
    if service in table:
        return table[service]
    return default_min, default_max
