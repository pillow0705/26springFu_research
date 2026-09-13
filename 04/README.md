# Multi-agent sixfold research system

This prototype runs three mathematical routes (A1, A2, A3) over all 21 six-dimensional cases. Each route can submit a proof as soon as it has one; the committee sends it to a proof-focused reviewer, returns serious objections to the originating agent, and immediately writes approved answers into a fixed 21-section LaTeX manuscript. A turn-ordered A1/A2/A3 meeting starts at ten minutes, and the complete run stops at twenty minutes with the current manuscript preserved.

## Run

```bash
cd 04
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DEEPSEEK_API_KEY=sk-... .venv/bin/python multi_agent_research_system.py
```

The task list is read from the 21-row table in `System design.md` (the fallback list is used until the table is present). Inspect the orchestration contract without an API call:

```bash
python3 multi_agent_research_system.py --dry-run
```

Per-task LangGraph state is checkpointed to `runtime/research.sqlite` when the SQLite checkpoint package is installed; override it with `--checkpoint`.

The model is configured through `DEEPSEEK_MODEL` (default `deepseek-chat`) and `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`).
