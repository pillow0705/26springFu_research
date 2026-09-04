# Laboratory foundation

The prototype keeps coordination intentionally small. `ResearchLab` owns role definitions,
workspaces, Codex thread lifecycle, artifact persistence, and a stop-file boundary. Agents decide
what happens next by emitting generic `ACTION:` lines (`MESSAGE`, `TASK`, `MEETING`, `WAIT`, or
`STOP`). If an agent emits no action, the event queue simply becomes idle; there is no fixed
research-cycle or role-rotation table.

The shared workspace is the durable research memory. `artifacts/` stores every turn,
`meetings/` stores professor-led meetings, and `inbox/` stores notes or dialogue requests received
through the MCP backend. Each role receives a separate runtime home under `agent_homes/` at run
time; only local authentication is copied there, and runtime state is ignored by Git.

`mcp_server.py` exposes three small tools: read recent work, write a note, and request a dialogue.
It is a transport boundary, not a second orchestration engine. `run_lab.py` provides bounded turns,
dry-run validation, optional meetings, and a process-level stop mechanism.

Each role's Codex thread ID is persisted in `state.json`; later events resume that role's thread.
The event queue is seeded only with the initial professor task. Further work exists only when an
agent emits an action or an external MCP client submits a dialogue request.
