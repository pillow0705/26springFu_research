# Multi-agent sixfold research system (persistent-context variant)

This variant keeps exactly one persistent LangGraph thread/context for each route A1, A2 and A3. Each route repeatedly works on the shared pool of unresolved cases. The committee sends proofs to a proof-focused reviewer, returns serious objections to the originating route, and immediately writes approved answers into a fixed 21-section LaTeX manuscript. A turn-ordered A1/A2/A3 meeting reads each route's real history at ten minutes; the run stops when all 21 slots are approved or at twenty minutes.

## Run

```bash
cd 05
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
DEEPSEEK_API_KEY=sk-... .venv/bin/python multi_agent_research_system.py
```

The task list is read from `../04/System design.md` (the fallback list is used until the table is present). The API key can remain in `../04/.env`.

```bash
python3 multi_agent_research_system.py --dry-run
```

Per-task LangGraph state is checkpointed to `runtime/research.sqlite` when the SQLite checkpoint package is installed; override it with `--checkpoint`.

The model is configured through `DEEPSEEK_MODEL` (default `deepseek-chat`) and `DEEPSEEK_BASE_URL` (default `https://api.deepseek.com`).
