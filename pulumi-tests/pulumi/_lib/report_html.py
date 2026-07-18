"""Render HTML report from Pulumi + HTTP coverage results."""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SERIES_ORDER = ("yoga", "antelope", "caracal", "dalmatian")


def _methods_line(methods: dict[str, Any]) -> str:
    return " ".join(f"{m}={methods.get(m, 0)}" for m in ("GET", "POST", "PUT", "PATCH", "DELETE"))


def render_html(summary: dict[str, Any], series_reports: list[dict[str, Any]]) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    cards = []
    for rep in series_reports:
        series = html.escape(str(rep.get("series", "?")))
        pu = rep.get("pulumi", {})
        http = rep.get("http", {})
        cards.append(
            f"""
            <div class="card">
              <h3>{series}</h3>
              <p class="muted">pulumi_openstack + HTTP pack probe</p>
              <div class="stats">
                <span class="ok">pulumi exports ok={len(pu.get("outputs", {})) - len(pu.get("empty_exports", []))}</span>
                <span class="fail">empty exports={len(pu.get("empty_exports", []))}</span>
              </div>
              <div class="stats">
                <span class="ok">http ok={http.get("ok_count", 0)}</span>
                <span class="fail">http fail={http.get("fail_count", 0)} nonempty_fail={http.get("nonempty_fail_count", 0)}</span>
                <span>http total={http.get("total", 0)}/{http.get("expected_ops", "?")}</span>
              </div>
              <div class="stats muted">
                methods: {html.escape(_methods_line(http.get("methods") or {}))}
                {" · <span class='fail'>coverage incomplete</span>" if http.get("coverage_incomplete") else ""}
              </div>
            </div>"""
        )

    detail_rows = []
    for rep in series_reports:
        series = rep.get("series", "?")
        for item in rep.get("http", {}).get("failures", [])[:500]:
            detail_rows.append(
                '<tr class="fail">'
                f"<td>{html.escape(str(series))}</td>"
                f"<td>{html.escape(str(item.get('service', '')))}</td>"
                f"<td>{html.escape(str(item.get('operation_id', '')))}</td>"
                f"<td>{html.escape(str(item.get('method', '')))}</td>"
                f"<td><code>{html.escape(str(item.get('path', '')))}</code></td>"
                f"<td>{html.escape(str(item.get('status', '')))}</td>"
                f"<td>{html.escape(str(item.get('detail', ''))[:240])}</td>"
                "</tr>"
            )
        for empty in rep.get("pulumi", {}).get("empty_exports", []):
            detail_rows.append(
                '<tr class="fail">'
                f"<td>{html.escape(str(series))}</td>"
                f"<td>pulumi_openstack</td>"
                f"<td>export_nonempty</td>"
                f"<td>—</td><td><code>export</code></td><td>—</td>"
                f"<td>{html.escape(str(empty))}</td>"
                "</tr>"
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Pulumi OpenStack coverage</title>
  <style>
    :root {{ --bg:#0f1419; --panel:#1a222c; --text:#e7ecf3; --muted:#9aa7b8; --ok:#3dd68c; --fail:#ff6b6b; --border:#2a3544; }}
    body {{ margin:0; font-family:"IBM Plex Sans",sans-serif; background:radial-gradient(1000px 500px at 0% 0%,#1b2a3d,var(--bg)); color:var(--text); }}
    header, main {{ max-width:1200px; margin:0 auto; padding:1.5rem; }}
    .summary, .cards {{ display:grid; gap:.75rem; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); margin:1rem 0; }}
    .summary div, .card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:1rem; }}
    .ok {{ color:var(--ok); font-weight:600; }} .fail {{ color:var(--fail); font-weight:600; }}
    .muted {{ color:var(--muted); }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--border); border-radius:10px; overflow:hidden; font-size:.9rem; }}
    th, td {{ padding:.45rem .6rem; border-bottom:1px solid var(--border); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); background:#121820; }}
    tr.fail {{ background:rgba(255,107,107,.08); }}
    code {{ font-family:ui-monospace,monospace; font-size:.82rem; }}
  </style>
</head>
<body>
  <header>
    <h1>Pulumi OpenStack API coverage</h1>
    <p class="muted">Generated {html.escape(generated)} · pulumi_openstack primary + HTTP pack probe with non-empty checks</p>
  </header>
  <main>
    <div class="summary">
      <div><strong>{summary.get("series_count", 0)}</strong><span class="muted"> series</span></div>
      <div><strong class="ok">{summary.get("pulumi_ok", 0)}</strong><span class="muted"> pulumi stacks ok</span></div>
      <div><strong class="fail">{summary.get("pulumi_fail", 0)}</strong><span class="muted"> pulumi failures</span></div>
      <div><strong class="ok">{summary.get("http_ok", 0)}</strong><span class="muted"> http ops ok</span></div>
      <div><strong class="fail">{summary.get("http_fail", 0)}</strong><span class="muted"> http / nonempty fails</span></div>
    </div>
    <h2>Series</h2>
    <div class="cards">{"".join(cards)}</div>
    <h2>Failures</h2>
    <table>
      <thead><tr><th>Series</th><th>Service</th><th>Operation</th><th>Method</th><th>Path</th><th>HTTP</th><th>Detail</th></tr></thead>
      <tbody>{"".join(detail_rows) if detail_rows else '<tr><td colspan="7">No failures</td></tr>'}</tbody>
    </table>
  </main>
</body>
</html>
"""


def write_html(
    report_dir: Path, summary: dict[str, Any], series_reports: list[dict[str, Any]]
) -> Path:
    path = report_dir / "pulumi-report.html"
    path.write_text(render_html(summary, series_reports), encoding="utf-8")
    return path


def load_series_files(report_dir: Path) -> list[dict[str, Any]]:
    out = []
    for series in SERIES_ORDER:
        path = report_dir / f"series-{series}.json"
        if path.exists():
            out.append(json.loads(path.read_text(encoding="utf-8")))
    return out
