# Academic Center Committee

This directory contains the committee-owned backend for the 21-problem research laboratory.
The backend handles agent registration, durable status, manuscript intake, reviewer dispatch,
review decisions, durable messages, and committee-organized group meetings.

## Components

- `committee/service.py`: SQLite-backed committee service and safe manuscript copying.
- `committee/mcp_server.py`: local stdio MCP transport.
- `committee/start_lab.py`: launcher for 43 persistent Codex threads and 21 concurrent math goals.
- `agent/*/workspace/group_meeting/`: per-agent meeting briefs, discussion packets, comments, and
  internalized syntheses.
- `runtime/launch.json`: launcher output consumed by the committee to find thread IDs.
- `runtime/committee.sqlite`: durable submissions, agent status, and messages.

## Run

```bash
python3 start_lab.py --dry-run --phase first
python3 committee/mcp_server.py
```

Run the monitoring console in another terminal (read-only):

```bash
python3 monitor_server.py --host 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8765/` to see a live dashboard.
It only reads `runtime/launch.json` and `runtime/committee.sqlite`, so it does not affect running agents or MCP services.

The first phase is five minutes and the second phase is fifteen minutes. Use `--resume` for a
second-phase launch after a previous phase has written `runtime/launch.json`.

Manuscripts are submitted with paths relative to `03/`. The committee rejects absolute paths,
path traversal, symlinks that resolve outside `03/`, and non-regular files. A valid submission is
copied into the matching reviewer workspace and assigned by number (`math5` to `review5`).

## Group meetings

The committee creates a meeting with `committee_create_meeting`. Participants submit statements
with `committee_submit_meeting_statement`, read the shared discussion, and comment on another
participant with `committee_submit_meeting_comment`. `committee_finalize_meeting` closes the
discussion and writes a complete feedback packet into every participant's meeting workspace.
Each participant then compresses and internalizes the discussion with
`committee_submit_meeting_synthesis`; the committee can read those syntheses with
`committee_get_meeting_syntheses`.
