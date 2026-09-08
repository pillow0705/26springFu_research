#!/usr/bin/env python3
"""Read-only monitoring dashboard for the 03 lab runtime."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
LAUNCH_PATH = ROOT / "runtime" / "launch.json"
DB_PATH = ROOT / "runtime" / "committee.sqlite"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {"error": "invalid-json"}
    if isinstance(payload, dict):
        return payload
    return {}


def _safe_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _query_db() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {
            "database": False,
            "error": "committee.sqlite not found",
            "totals": {},
            "submission_status": {},
            "meeting_status": {},
        }
    try:
        conn = sqlite3.connect(DB_PATH, timeout=2)
        conn.row_factory = sqlite3.Row
    except sqlite3.OperationalError as exc:
        return {"database": False, "error": str(exc), "totals": {}, "submission_status": {}, "meeting_status": {}}

    try:
        with conn:
            c = conn.cursor()
            totals: dict[str, Any] = {}
            for table in ("submissions", "messages", "meetings", "meeting_statements", "meeting_comments", "meeting_syntheses"):
                value = c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                totals[table] = int(value)

            rows = c.execute(
                "SELECT status, COUNT(*) AS count FROM submissions GROUP BY status"
            ).fetchall()
            submission_status = {row["status"]: int(row["count"]) for row in rows}
            submission_status.setdefault("PENDING", 0)
            submission_status["PENDING"] += submission_status.get(None, 0) + submission_status.get("", 0)
            submission_status = {k: v for k, v in submission_status.items() if k not in (None, "")}

            meeting_rows = c.execute("SELECT status, COUNT(*) AS count FROM meetings GROUP BY status").fetchall()
            meeting_status = {row["status"]: int(row["count"]) for row in meeting_rows}

            latest = []
            for row in c.execute(
                "SELECT submission_id, agent_id, reviewer_id, task_id, status, decision, created_at "
                "FROM submissions ORDER BY created_at DESC LIMIT 20"
            ).fetchall():
                latest.append(
                    {
                        "submission_id": row["submission_id"],
                        "agent_id": row["agent_id"],
                        "reviewer_id": row["reviewer_id"],
                        "task_id": row["task_id"],
                        "status": row["status"],
                        "decision": row["decision"],
                        "created_at": row["created_at"],
                    }
                )

            return {
                "database": True,
                "totals": totals,
                "submission_status": submission_status,
                "meeting_status": meeting_status,
                "latest_submissions": latest,
            }
    finally:
        conn.close()


def _agent_stats() -> dict[str, Any]:
    manifest = _safe_read_json(LAUNCH_PATH)
    phase = manifest.get("phase")
    updated_at = manifest.get("updated_at")
    model = manifest.get("model")
    reasoning_effort = manifest.get("reasoning_effort")
    agents = manifest.get("agents", {})
    if not isinstance(agents, dict):
        agents = {}

    math_handles = {name: info for name, info in agents.items() if str(name).startswith("math")}
    reviewer_handles = {name: info for name, info in agents.items() if str(name).startswith("review")}
    goal_status_counter = Counter()
    for info in math_handles.values():
        status = info.get("goal_status") if isinstance(info, dict) else None
        goal_status_counter[str(status or "not_started")] += 1

    return {
        "updated_at": updated_at or "unknown",
        "phase": phase or "unknown",
        "model": model or "unknown",
        "reasoning_effort": reasoning_effort or "unknown",
        "math": {
            "total": len(math_handles),
            "goal_status": dict(goal_status_counter),
            "goal_active": goal_status_counter.get("active", 0),
            "goal_finished": goal_status_counter.get("finished", 0),
            "goal_stopped": goal_status_counter.get("stopped", 0),
            "goal_not_started": goal_status_counter.get("not_started", 0),
        },
        "review": {
            "total": len(reviewer_handles),
            "goal_flagged": sum(1 for item in reviewer_handles.values() if isinstance(item, dict) and item.get("goal")),
            "goal_status": Counter(
                (info.get("goal_status") if isinstance(info, dict) else None) or "inactive"
                for info in reviewer_handles.values()
            ),
        },
        "writer": 1 if "Writer" in agents else 0,
        "threads": len(agents),
    }


def build_dashboard_state() -> dict[str, Any]:
    state = {"ts": _now()}
    state["lab"] = _agent_stats()
    state.update(_query_db())
    return state


def render_html() -> str:
    return """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>03 Monitor</title>
  <style>
    body { font-family: Arial, Helvetica, sans-serif; background: #f6f7fb; margin: 0; padding: 1.2rem; color: #202124; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 0.8rem; }
    .card { background: white; border: 1px solid #dce0e8; border-radius: 8px; padding: 1rem; }
    h1, h2 { margin: 0 0 .6rem; }
    h1 { font-size: 1.2rem; }
    h2 { font-size: 1rem; }
    .muted { color: #667085; font-size: .9rem; }
    table { width: 100%; border-collapse: collapse; }
    th, td { border-bottom: 1px solid #eceff4; text-align: left; padding: .4rem .2rem; font-size: .9rem; }
    tr:last-child td { border-bottom: none; }
    .status { color: #1d4ed8; font-weight: 600; }
    .stamp { color: #475467; font-size: .85rem; margin-top: .6rem; }
  </style>
</head>
<body>
  <h1>03 Monitoring Console</h1>
  <div class="stamp" id="stamp">Loading ...</div>
  <div class="grid" id="cards"></div>
  <h2>Recent Submissions</h2>
  <table id="recent">
    <thead><tr><th>Time</th><th>Submission</th><th>Agent</th><th>Reviewer</th><th>Status</th><th>Decision</th></tr></thead>
    <tbody></tbody>
  </table>
  <script>
    const cards = [
      ['Lab', 'lab'],
      ['Totals', 'totals'],
      ['Submission Status', 'submission_status'],
      ['Meeting Status', 'meeting_status'],
      ['DB', 'database']
    ];

    function prettyRows(header, data) {
      if (typeof data !== 'object') return `<div class="muted">-</div>`;
      const rows = Object.entries(data).map(([k,v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('');
      return `<table><tbody>${rows || '<tr><td>empty</td><td>-</td></tr>'}</tbody></table>`;
    }

    async function refresh() {
      try {
        const rsp = await fetch('/api/state', { cache: 'no-store' });
        if (!rsp.ok) throw new Error(`request failed: ${rsp.status}`);
        const state = await rsp.json();
        document.getElementById('stamp').textContent = `Updated: ${state.ts} | Lab phase: ${state.lab?.phase || 'unknown'}`;

        const lab = state.lab || {};
        const grids = [
          { title: 'Lab Info', body: `<div>Phase: <span class="status">${lab.phase || '-'}</span></div><div>Math total: ${lab.math?.total || 0}, Active: ${lab.math?.goal_active || 0}, Finished: ${lab.math?.goal_finished || 0}</div><div>Writer: ${lab.writer || 0}</div><div>Threads: ${lab.threads || 0}</div><div>Model: ${lab.model || '-'} (${lab.reasoning_effort || '-'})</div>` },
          { title: 'Submission Totals', body: prettyRows('totals', state.totals) },
          { title: 'Submission Status', body: prettyRows('submission_status', state.submission_status) },
          { title: 'Meeting Status', body: prettyRows('meeting_status', state.meeting_status) },
          { title: 'Database', body: `<div>Connected: ${state.database ? 'yes' : 'no'}</div><div>${state.error ? `Error: ${state.error}` : ''}</div>` }
        ];
        document.getElementById('cards').innerHTML = grids.map(item => `<div class="card"><h2>${item.title}</h2>${item.body}</div>`).join('');

        const tbody = document.querySelector('#recent tbody');
        const rows = (state.latest_submissions || []).map((row) => `<tr><td>${row.created_at || ''}</td><td>${row.submission_id || ''}</td><td>${row.agent_id || ''}</td><td>${row.reviewer_id || ''}</td><td>${row.status || ''}</td><td>${row.decision || ''}</td></tr>`).join('');
        tbody.innerHTML = rows || '<tr><td colspan="6" class="muted">No records yet</td></tr>';
      } catch (error) {
        document.getElementById('stamp').textContent = `Refresh failed: ${error.message}`;
      }
    }
    setInterval(refresh, 2000);
    refresh();
  </script>
</body>
</html>"""


class MonitorHandler(BaseHTTPRequestHandler):
    server_version = "03Monitor/1.0"

    def _json(self, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _html(self, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._html(render_html())
            return
        if path == "/api/state":
            self._json(build_dashboard_state())
            return
        if path == "/api/health":
            self._json({"ok": True, "ts": _now(), "database": DB_PATH.exists()})
            return
        if path == "/api/recent":
            query = parse_qs(urlparse(self.path).query)
            limit = _safe_int(query.get("limit", [None])[0], 20)
            data = _query_db()
            rows = data.get("latest_submissions", [])
            self._json({
                "ts": _now(),
                "items": rows[: min(limit, len(rows))]
            })
            return
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"not found")

    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MonitorHandler)
    print(f"MONITOR_URL=http://{args.host}:{args.port}/")
    print("MONITOR_REFRESH=2000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
