# Engineering review

The independent review pass checked the laboratory implementation after the initial scaffold.

## Verified

- `pytest -q`: 3 tests passed.
- `python3 -m py_compile lab.py run_lab.py mcp_server.py`: passed.
- MCP initialize/tools-list smoke test: passed.
- `python3 run_lab.py --dry-run --max-turns 2 --meeting`: completed bounded turns and produced a
  multi-role meeting transcript.
- Codex model and reasoning effort are explicit (`gpt-5.6-sol`, `high`) and recorded in artifacts.
- Real SDK smoke test completed one professor turn with the local Codex credential using
  `gpt-5.6-sol` and `high` reasoning.
- Each role receives its own runtime home, private workspace path, role prompt, and relevant skills.
- STOP-file handling, turn limits, and Unix signal timeout are implemented.
- The coordinator is event-driven: it has no fixed role rotation; agents emit generic actions and
  the queue routes them, while per-role thread IDs are persisted for later resumption.

## Deliberate limits

The first version assumes one scheduler process at a time and uses a small file-backed protocol.
The MCP server is intentionally dependency-free; it exposes the lab backend but does not replace
the scheduler. Mathematical correctness still requires independent human or formal verification.
