"""Three-route, reviewer-gated research system for the 21 sixfold cases.

The system is time-bounded: a group meeting starts at ten minutes and the whole
run stops at twenty minutes. Every approved result is written to LaTeX immediately.
LangGraph and DeepSeek are imported lazily so ``--dry-run`` needs no API key.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parent
TASK_SOURCE = ROOT / "System design.md"
if not TASK_SOURCE.exists():
    TASK_SOURCE = ROOT.parent / "04" / "System design.md"
RUNTIME = ROOT / "runtime"

FALLBACK_TASKS = (
    ("S1", "Type I(1)"), ("S2", "Type I(2)"), ("S3", "Type I(3)"),
    ("S4", "Type I(6)"), ("S5", "Type II(1)"), ("S6", "Type II(3)"),
    ("S7", "Type III(1)"), ("S8", "Type IV(1,1)"), ("S9", "Type IV(2,1)"),
    ("S10", "Type IV(3,1)"), ("S11", "Type IV(6,1)"), ("N1", "5+1"),
    ("N2", "4+2"), ("N3", "4+1+1"), ("N4", "3+3"), ("N5", "3+2+1"),
    ("N6", "3+1+1+1"), ("N7", "2+2+2"), ("N8", "2+2+1+1"),
    ("N9", "2+1+1+1+1"), ("N10", "1+1+1+1+1+1"),
)

PROFILES = {
    "A1": "Shimura-family route: parameter families, Hodge loci, monodromy, specialization and degeneration.",
    "A2": "Simple-Albert route: simple sixfolds, End^0, Rosati involution, Albert types, Hodge groups and Weil classes.",
    "A3": "Splitting-exception route: product decompositions, Kunneth tensors, mixed classes and exceptional Hodge classes.",
}


def load_tasks(path: Path = TASK_SOURCE) -> tuple[tuple[str, str], ...]:
    """Read the 21 rows pasted into System design.md; use fallback until then."""
    if path.exists():
        rows = re.findall(r"\|\s*([SN])\s*(\d+)\s*[:：]\s*([^|\n]+)", path.read_text(encoding="utf-8"))
        unique = list(dict.fromkeys((f"{kind}{number}", label.strip()) for kind, number, label in rows))
        if len(unique) == 21:
            return tuple(unique)
    return FALLBACK_TASKS


@dataclass
class Submission:
    agent: str
    task_id: str
    label: str
    proof: str
    attempt: int


@dataclass
class AgentContext:
    agent: str
    profile: str
    meeting_digest: str = ""
    feedback: dict[str, str] = field(default_factory=dict)
    history: list[str] = field(default_factory=list)
    completed: set[str] = field(default_factory=set)
    lock: threading.Lock = field(default_factory=threading.Lock)


class ResearchState(TypedDict, total=False):
    task_id: str
    label: str
    agent: str
    profile: str
    meeting_digest: str
    feedback: str
    history: list[str]
    plan: str
    proof: str
    self_check: str


def _model() -> Any:
    from langchain_openai import ChatOpenAI

    for env_path in (ROOT / ".env", ROOT.parent / "04" / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for a live run")
    return ChatOpenAI(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=key,
        temperature=0.2,
    )


def _text(response: Any) -> str:
    return str(getattr(response, "content", response))


def _json(response: Any) -> dict[str, Any]:
    text = _text(response)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {"status": "BLOCKED", "proof": text, "reason": "Non-JSON model output"}


def build_task_graph(checkpointer: Any = None) -> Any:
    """A three-step LangGraph reasoning pipeline used for one route/task."""
    from langgraph.graph import END, START, StateGraph

    model = _model()

    def plan(state: ResearchState) -> dict[str, str]:
        prompt = f"""You are {state['agent']}. {state['profile']}
Plan a rigorous attack on {state['task_id']}: {state['label']} for six-dimensional
abelian varieties. You are continuing one persistent research context. Previous
research log:
{chr(10).join(state.get('history', [])[-12:])}
Separate known facts from conjectural steps. Return a concise plan."""
        return {"plan": _text(model.invoke(prompt))}

    def prove(state: ResearchState) -> dict[str, str]:
        prompt = f"""You are {state['agent']}. Produce a candidate mathematical proof for
{state['task_id']}: {state['label']} using this plan:
{state['plan']}
Meeting knowledge (possibly empty): {state.get('meeting_digest', '')}
Reviewer feedback from an earlier attempt (possibly empty): {state.get('feedback', '')}
Persistent context excerpt:
{chr(10).join(state.get('history', [])[-12:])}
Return JSON with keys status (PROVED, CONJECTURE, BLOCKED), claim, proof,
assumptions, and gap. Never call a conjecture a theorem."""
        result = _json(model.invoke(prompt))
        return {"proof": json.dumps(result, ensure_ascii=False)}

    def self_check(state: ResearchState) -> dict[str, str]:
        prompt = f"""Check only the mathematical core of this proposed answer. Do not
police notation or minor exposition errors. Identify any missing implication,
false assertion, or unjustified use of a Hodge group:
{state['proof']}
Return JSON {{\"ready\": true/false, \"reason\": \"...\"}}."""
        return {"self_check": _text(model.invoke(prompt))}

    graph = StateGraph(ResearchState)
    graph.add_node("plan", plan)
    graph.add_node("prove", prove)
    graph.add_node("self_check", self_check)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "prove")
    graph.add_edge("prove", "self_check")
    graph.add_edge("self_check", END)
    return graph.compile(checkpointer=checkpointer)


def sqlite_checkpointer(path: Path) -> tuple[Any, sqlite3.Connection]:
    from langgraph.checkpoint.sqlite import SqliteSaver

    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, check_same_thread=False)
    return SqliteSaver(connection), connection


def review(submission: Submission) -> tuple[str, str]:
    """Review proof correctness only; tolerate small notation/style errors."""
    prompt = f"""You are reviewer for {submission.task_id}: {submission.label}.
Review only whether the mathematical proof has a serious logical error or an
unsupported key step. Ignore minor notation, wording, and formatting mistakes.
Return JSON: {{\"decision\": \"APPROVE\"|\"REVISE\"|\"BLOCKED\", \"feedback\": \"...\"}}.
Candidate from {submission.agent}:
{submission.proof}"""
    result = _json(_model().invoke(prompt))
    decision = str(result.get("decision", "BLOCKED")).upper()
    if decision not in {"APPROVE", "REVISE", "BLOCKED"}:
        decision = "BLOCKED"
    return decision, str(result.get("feedback", result.get("reason", "")))


class Writer:
    """Incrementally fills a fixed 21-section LaTeX manuscript."""

    def __init__(self, path: Path, tasks: tuple[tuple[str, str], ...], event_path: Path | None = None) -> None:
        self.path = path
        self.tasks = tasks
        self.event_path = event_path
        self.sections = {key: "% TODO: awaiting an approved proof.\n" for key, _ in tasks}
        self.lock = threading.Lock()

    def accept(self, submission: Submission, feedback: str) -> None:
        prompt = f"""You are the Writer agent. Convert this reviewer-approved
mathematical answer into a concise LaTeX section for {submission.task_id}: {submission.label}.
Preserve the mathematical claim and proof status. Do not strengthen a conjecture
into a theorem. Return only compilable LaTeX body text, with no document wrapper.
Approved answer:\n{submission.proof}\nReviewer note:\n{feedback}"""
        try:
            section = _text(_model().invoke(prompt))
        except Exception:
            section = submission.proof
        with self.lock:
            self.sections[submission.task_id] = (
                f"% Submitted by {submission.agent}; reviewer note: {feedback}\n"
                + section + "\n"
            )
            self.flush()
            if self.event_path:
                _emit(self.event_path, "WRITER_ACCEPT", task=submission.task_id, agent=submission.agent)

    def flush(self) -> None:
        body = "\n".join(
            f"\\section{{{key}: {label}}}\n{self.sections[key]}"
            for key, label in self.tasks
        )
        document = "\\documentclass{article}\n\\begin{document}\n" + body + "\\end{document}\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(document, encoding="utf-8")
        temporary.replace(self.path)


class Committee:
    def __init__(self, writer: Writer, max_revisions: int = 2, event_path: Path | None = None) -> None:
        self.writer = writer
        self.max_revisions = max_revisions
        self.event_path = event_path
        self.history: list[dict[str, Any]] = []
        self.approved: set[str] = set()
        self.lock = threading.Lock()

    def is_approved(self, task_id: str) -> bool:
        with self.lock:
            return task_id in self.approved

    def all_approved(self, tasks: tuple[tuple[str, str], ...]) -> bool:
        with self.lock:
            return len(self.approved) == len(tasks)

    def receive(self, submission: Submission) -> tuple[str, str]:
        decision, feedback = review(submission)
        with self.lock:
            self.history.append({"task": submission.task_id, "agent": submission.agent, "decision": decision, "feedback": feedback})
            if decision == "APPROVE":
                self.approved.add(submission.task_id)
        if self.event_path:
            _emit(self.event_path, "REVIEW", task=submission.task_id, agent=submission.agent, decision=decision)
        if decision == "APPROVE":
            self.writer.accept(submission, feedback)
        return decision, feedback


def _emit(path: Path, event: str, **data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": time.time(), "event": event, **data}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_meeting(contexts: dict[str, AgentContext], event_path: Path | None = None) -> str:
    """Three-turn meeting: A1 speaks, A2 speaks, A3 speaks, then a shared digest."""
    if event_path:
        _emit(event_path, "MEETING_START")
    reports: list[str] = []
    for agent in ("A1", "A2", "A3"):
        context = contexts[agent]
        with context.lock:
            history = "\n".join(context.history[-20:])
            completed = ", ".join(sorted(context.completed)) or "none"
        prompt = f"""You are {agent}. {PROFILES[agent]}
This is a report from your persistent context, not a fresh brainstorm. You have
completed or attempted: {completed}
Recent research history:
{history}
Summarize your strongest ideas, failed approaches, and one useful suggestion for
the other two routes. Do not claim unproved results."""
        reports.append(f"{agent}: {_text(_model().invoke(prompt))}")
    digest_prompt = """Chair the research meeting. Integrate these three turn-ordered
reports into shared context. Preserve disagreements and label conjectures.
Reports:\n""" + "\n\n".join(reports)
    digest = _text(_model().invoke(digest_prompt))
    for context in contexts.values():
        with context.lock:
            context.meeting_digest = digest
    if event_path:
        _emit(event_path, "MEETING_END")
    return digest


def run(*, total_seconds: int = 20 * 60, meeting_after: int = 10 * 60, output: Path = RUNTIME / "paper.tex", checkpoint: Path = RUNTIME / "research.sqlite") -> dict[str, Any]:
    tasks = load_tasks()
    progress_path = output.with_suffix(".progress.jsonl")
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text("", encoding="utf-8")
    writer = Writer(output, tasks, progress_path)
    committee = Committee(writer, event_path=progress_path)
    contexts = {agent: AgentContext(agent, profile) for agent, profile in PROFILES.items()}
    deadline = time.monotonic() + total_seconds
    stop = threading.Event()
    meeting_started = threading.Event()
    checkpoint_store = None
    checkpoint_connection = None
    try:
        checkpoint_store, checkpoint_connection = sqlite_checkpointer(checkpoint)
    except (ImportError, ModuleNotFoundError):
        pass

    def meeting_timer() -> None:
        time.sleep(meeting_after)
        if not stop.is_set():
            meeting_started.set()
            run_meeting(contexts, progress_path)
            meeting_started.clear()

    timer = threading.Thread(target=meeting_timer, daemon=True)
    timer.start()

    def worker(context: AgentContext) -> None:
        _emit(progress_path, "AGENT_START", agent=context.agent)
        # One graph/thread per route; task changes happen inside this persistent context.
        graph = build_task_graph(checkpoint_store)
        while not stop.is_set() and time.monotonic() < deadline and not committee.all_approved(tasks):
            made_progress = False
            for task_id, label in tasks:
                if stop.is_set() or time.monotonic() >= deadline:
                    return
                if committee.is_approved(task_id):
                    continue
                while meeting_started.is_set() and not stop.is_set():
                    time.sleep(0.25)
                attempts = 0
                while attempts <= committee.max_revisions and not stop.is_set() and time.monotonic() < deadline:
                    attempts += 1
                    with context.lock:
                        history = list(context.history)
                        meeting_digest = context.meeting_digest
                        feedback = context.feedback.get(task_id, "")
                    state: ResearchState = {
                        "task_id": task_id, "label": label, "agent": context.agent,
                        "profile": context.profile, "meeting_digest": meeting_digest,
                        "feedback": feedback, "history": history,
                    }
                    result = graph.invoke(state, config={"configurable": {"thread_id": context.agent}})
                    proof = result.get("proof", "")
                    with context.lock:
                        context.history.append(f"{task_id} attempt {attempts}: {proof[:1800]}")
                    submission = Submission(context.agent, task_id, label, proof, attempts)
                    _emit(progress_path, "SUBMIT", task=task_id, agent=context.agent, attempt=attempts)
                    decision, feedback = committee.receive(submission)
                    made_progress = True
                    if decision == "APPROVE":
                        with context.lock:
                            context.completed.add(task_id)
                        break
                    if decision == "BLOCKED":
                        with context.lock:
                            context.feedback[task_id] = feedback
                        break
                    with context.lock:
                        context.feedback[task_id] = feedback
                if committee.all_approved(tasks):
                    stop.set()
                    return
            if not made_progress:
                time.sleep(1)

    workers = [threading.Thread(target=worker, args=(context,), daemon=True) for context in contexts.values()]
    for thread in workers:
        thread.start()
    while time.monotonic() < deadline and any(thread.is_alive() for thread in workers):
        time.sleep(0.25)
    stop.set()
    for thread in workers:
        thread.join(timeout=2)
    writer.flush()
    if checkpoint_connection is not None:
        checkpoint_connection.close()
    return {"tasks": len(tasks), "reviews": len(committee.history), "meeting_started": meeting_started.is_set(), "paper": str(output), "timed_out": time.monotonic() >= deadline}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--total-seconds", type=int, default=20 * 60)
    parser.add_argument("--meeting-after", type=int, default=10 * 60)
    parser.add_argument("--output", type=Path, default=RUNTIME / "paper.tex")
    parser.add_argument("--checkpoint", type=Path, default=RUNTIME / "research.sqlite")
    args = parser.parse_args()
    if args.dry_run:
        print(json.dumps({"agents": list(PROFILES), "tasks": len(load_tasks()), "meeting_after": args.meeting_after, "hard_stop": args.total_seconds, "writer_output": str(args.output)}, ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(run(total_seconds=args.total_seconds, meeting_after=args.meeting_after, output=args.output, checkpoint=args.checkpoint), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
