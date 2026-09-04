# Simulated Algebra Research Lab

This experiment builds a small, recoverable research laboratory around the Codex Python SDK.
The lab models three mathematicians, a professor, a PhD writer, and an independent reviewer.

## Design

Agents communicate through a shared Markdown workspace. Each event gives one agent a task, stores
its response as an artifact, and lets the agent emit generic `ACTION:` lines for messages, tasks,
meetings, waiting, or stopping. The scheduler is intentionally thin: it starts/resumes Codex
threads, records artifacts, enforces limits, and supports a hard stop file.

The implementation is English-only. The research source notes remain in the parent `02/` folder.

## Run

```bash
cd /root/program/26research/26springFu_research/02
python3 run_lab.py --dry-run
python3 run_lab.py --max-turns 8
```

Use `--dry-run` to validate orchestration without model calls. A real run uses the local Codex
credential found in `CODEX_HOME` (or the standard `~/.codex` location). Create `STOP` in the lab
workspace to request a clean stop between turns.
