"""Lightweight orchestration for the simulated algebra research laboratory."""

from __future__ import annotations

import json
import os
import re
import signal
import shutil
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ACTION_RE = re.compile(
    r"^ACTION:\s*([A-Z_]+)(?:\s+([^|]*?))?\s*\|\s*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class AgentSpec:
    role: str
    title: str
    prompt_path: Path


@dataclass
class TurnResult:
    role: str
    response: str
    artifact: Path
    elapsed_seconds: float
    dry_run: bool
    actions: list[dict[str, str]]
    thread_id: str | None


class TurnTimeout(TimeoutError):
    pass


def _raise_turn_timeout(*_: Any) -> None:
    raise TurnTimeout("turn timeout")


class ResearchLab:
    """A deliberately thin coordinator around independent Codex threads.

    The lab stores durable state in files, while the agents decide what research action should
    happen next. It does not encode a large state machine.
    """

    def __init__(self, root: Path, config_path: Path | None = None) -> None:
        self.root = root.resolve()
        self.config_path = config_path or self.root / "config" / "team.json"
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        policy_path = self.root / "config" / "policy.toml"
        self.policy = tomllib.loads(policy_path.read_text(encoding="utf-8")) if policy_path.exists() else {}
        self.artifacts_dir = self.root / "artifacts"
        self.meetings_dir = self.root / "meetings"
        self.homes_dir = self.root / "agent_homes"
        self.state_path = self.root / "state.json"
        self.stop_path = self.root / "STOP"
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.meetings_dir.mkdir(parents=True, exist_ok=True)
        self.homes_dir.mkdir(parents=True, exist_ok=True)
        self.specs = {
            role: AgentSpec(role, data["title"], self.root / data["prompt"])
            for role, data in self.config["roles"].items()
        }
        self._state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self.state_path.exists():
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            state.setdefault("artifacts", [])
            state.setdefault("meetings", [])
            state.setdefault("threads", {})
            state.setdefault("events", [])
            return state
        return {"turns": 0, "artifacts": [], "meetings": [], "threads": {}, "events": [], "status": "ready"}

    def refresh(self) -> None:
        self._state = self._load_state()

    def _save_state(self) -> None:
        payload = json.dumps(self._state, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.root, delete=False) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        temporary.replace(self.state_path)

    @property
    def turns(self) -> int:
        return int(self._state["turns"])

    def should_stop(self) -> bool:
        return self.stop_path.exists()

    def request_stop(self) -> None:
        self.stop_path.touch()

    def clear_stop(self) -> None:
        self.stop_path.unlink(missing_ok=True)

    def pending_dialogue(self) -> tuple[str, str] | None:
        path = self.root / "inbox" / "dialogue_requests.md"
        if not path.exists():
            return None
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        cursor = int(self._state.get("dialogue_cursor", 0))
        for index, line in enumerate(lines[cursor:], start=cursor):
            match = re.match(r"-\s*[^-]+->\s*([^:]+):\s*(.+)", line)
            if match:
                self._state["dialogue_cursor"] = index + 1
                self._save_state()
                target = match.group(1).strip().lower().replace("-", "_").replace(" ", "_")
                return target, match.group(2).strip()
        self._state["dialogue_cursor"] = len(lines)
        self._save_state()
        return None

    def prepare_home(self, role: str) -> Path:
        """Create a role-specific Codex home and copy only local auth when available."""
        home = self.homes_dir / role
        home.mkdir(parents=True, exist_ok=True)
        auth_source = os.environ.get("CODEX_AUTH_SOURCE")
        candidates = [
            Path(auth_source) if auth_source else None,
            self.root.parent / "01" / ".codex" / "auth.json",
            Path.home() / ".codex" / "auth.json",
        ]
        target = home / "auth.json"
        if not target.exists():
            for candidate in candidates:
                if candidate and candidate.exists():
                    shutil.copy2(candidate, target)
                    target.chmod(0o600)
                    break
        (home / "config.toml").write_text(
            "[mcp_servers.research_lab]\n"
            "command = \"python3\"\n"
            f"args = [\"{self.root / 'mcp_server.py'}\"]\n",
            encoding="utf-8",
        )
        return home

    def shared_context(self, limit: int = 6) -> str:
        self.refresh()
        paths = [self.root / item for item in self._state.get("artifacts", [])[-limit:]]
        sections: list[str] = []
        for path in paths:
            if path.exists():
                sections.append(path.read_text(encoding="utf-8")[-6000:])
        inbox = self.root / "inbox"
        if inbox.exists():
            for path in sorted(inbox.glob("*.md"))[-3:]:
                sections.append(path.read_text(encoding="utf-8")[-4000:])
        return "\n\n--- RECENT ARTIFACT ---\n\n".join(sections) or "(No previous artifacts.)"

    def _prompt(self, role: str, task: str) -> str:
        return (
            "LAB PROTOCOL\n"
            "Read the shared workspace before acting. Do not invent access to private thoughts or "
            "unpublished work. Cite or flag uncertain claims.\n\n"
            f"CURRENT TASK\n{task}\n\n"
            f"RECENT SHARED WORK\n{self.shared_context()}"
        )

    def _role_instructions(self, role: str) -> str:
        spec = self.specs[role]
        role_prompt = spec.prompt_path.read_text(encoding="utf-8")
        role_workspace = self.root / "workspaces" / role
        skill_files = [self.root / "skills" / "research_protocol" / "SKILL.md"]
        skill_by_role = {
            "markman": "hodge_classes",
            "voisin": "hodge_classes",
            "lie_fu": "hodge_classes",
            "phd_writer": "latex_writing",
            "reviewer": "review",
        }
        if role in skill_by_role:
            skill_files.append(self.root / "skills" / skill_by_role[role] / "SKILL.md")
        skills = "\n\n".join(path.read_text(encoding="utf-8") for path in skill_files if path.exists())
        return (
            f"{role_prompt}\n\n"
            f"YOUR PRIVATE WORKSPACE\n{role_workspace}\n\n"
            f"ACTIVE SKILLS\n{skills}"
        )

    def dispatch(self, role: str, task: str, *, dry_run: bool = False) -> TurnResult:
        if role not in self.specs:
            raise ValueError(f"Unknown role: {role}")
        if self.should_stop():
            raise RuntimeError("STOP file requested")

        prompt = self._prompt(role, task)
        started = time.monotonic()
        thread_id: str | None = None
        if dry_run:
            action = (
                "ACTION: MEETING markman,voisin,lie_fu | Compare the current research state."
                if role == "professor"
                else "ACTION: MESSAGE professor | Continue from this artifact."
            )
            response = f"Dry-run response for {role}. I reviewed the shared workspace and would address: {task}\n\n{action}"
        else:
            response, thread_id = self._run_codex(role, prompt)
        elapsed = time.monotonic() - started
        actions = self._parse_actions(response)
        self._state["turns"] += 1
        artifact = self.artifacts_dir / f"turn-{self.turns:03d}-{role}.md"
        artifact.write_text(
            f"# Turn {self.turns}: {role}\n\n"
            f"## Task\n\n{task}\n\n"
            f"## Response\n\n{response}\n\n"
            f"## Metadata\n\n- elapsed_seconds: {elapsed:.2f}\n"
            f"- model: {self.policy.get('model', self.config.get('model', 'gpt-5.6'))}\n"
            f"- reasoning_effort: {self.policy.get('model_reasoning_effort', self.config.get('reasoning_effort', 'high'))}\n"
            f"- actions: {json.dumps(actions, ensure_ascii=False)}\n"
            f"- thread_id: {thread_id or 'none'}\n",
            encoding="utf-8",
        )
        role_results = self.root / "workspaces" / role / "results"
        role_results.mkdir(parents=True, exist_ok=True)
        shutil.copy2(artifact, role_results / artifact.name)
        self._state["artifacts"].append(str(artifact.relative_to(self.root)))
        self._state["events"].append({"role": role, "artifact": str(artifact.relative_to(self.root)), "actions": actions})
        if thread_id:
            self._state.setdefault("threads", {})[role] = thread_id
        self._state["status"] = "running"
        self._save_state()
        return TurnResult(role, response, artifact, elapsed, dry_run, actions, thread_id)

    def _run_codex(self, role: str, prompt: str) -> tuple[str, str | None]:
        from openai_codex import ApprovalMode, Codex, Sandbox

        home = self.prepare_home(role)
        previous_home = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(home)
        try:
            with Codex() as codex:
                model = self.policy.get("model", self.config.get("model", "gpt-5.6"))
                effort = self.policy.get("model_reasoning_effort", self.config.get("reasoning_effort", "high"))
                common = {
                    "model": model,
                    "cwd": str(self.root),
                    "sandbox": getattr(Sandbox, self.policy.get("sandbox", "workspace_write")),
                    "approval_mode": getattr(ApprovalMode, self.policy.get("approval_mode", "deny_all")),
                }
                existing_id = self._state.get("threads", {}).get(role)
                if existing_id:
                    thread = codex.thread_resume(existing_id, **common)
                else:
                    thread = codex.thread_start(
                        config={"model_reasoning_effort": effort},
                        base_instructions=self._role_instructions(role),
                        **common,
                    )
                timeout_seconds = float(self.config.get("max_turn_seconds", 900))
                previous_handler = signal.getsignal(signal.SIGALRM)
                signal.signal(signal.SIGALRM, _raise_turn_timeout)
                signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
                try:
                    result = thread.run(
                        prompt,
                        model=model,
                        effort=effort,
                    )
                    return result.final_response, getattr(thread, "id", None)
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, previous_handler)
        finally:
            if previous_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = previous_home

    def _parse_actions(self, response: str) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []
        for match in ACTION_RE.finditer(response):
            kind = match.group(1).upper()
            target = (match.group(2) or "").strip().lower().replace("-", "_").replace(" ", "_")
            content = match.group(3).strip()
            if kind in {"MESSAGE", "TASK"} and target not in self.specs:
                # Models sometimes qualify a registered role with a task suffix
                # (e.g. ``markman_check``).  Normalize only the explicit suffixes
                # used by the lab protocol; unknown targets remain rejected.
                for suffix in ("_calc", "_check", "_review", "_writer"):
                    if target.endswith(suffix) and target[: -len(suffix)] in self.specs:
                        target = target[: -len(suffix)]
                        break
            if kind in {"MESSAGE", "TASK"} and target not in self.specs:
                continue
            if kind in {"MESSAGE", "TASK", "MEETING", "WAIT", "STOP"}:
                actions.append({"kind": kind, "target": target, "content": content})
        return actions

    def run(self, task: str, *, max_turns: int | None = None, dry_run: bool = False) -> list[TurnResult]:
        budget = max_turns if max_turns is not None else int(self.config.get("max_turns", 12))
        if budget < 1:
            raise ValueError("max_turns must be at least 1")
        queue: list[dict[str, str]] = [{"role": "professor", "task": task, "source": "human"}]
        results: list[TurnResult] = []
        while queue and len(results) < budget:
            if self.should_stop():
                self._state["status"] = "stopped"
                self._save_state()
                break
            event = queue.pop(0)
            result = self.dispatch(event["role"], event["task"], dry_run=dry_run)
            results.append(result)
            for action in result.actions:
                if action["kind"] in {"MESSAGE", "TASK"}:
                    queue.append({"role": action["target"], "task": action["content"], "source": result.role})
                elif action["kind"] == "MEETING":
                    targets = [item.strip() for item in action["target"].split(",") if item.strip()]
                    targets = targets or ["markman", "voisin", "lie_fu", "professor"]
                    for target in targets:
                        if target in self.specs:
                            queue.append({"role": target, "task": action["content"], "source": result.role})
                elif action["kind"] == "STOP":
                    self.request_stop()
            requested = self.pending_dialogue()
            if requested and requested[0] in self.specs:
                queue.append({"role": requested[0], "task": requested[1], "source": "mcp"})
        if len(results) >= budget:
            self._state["status"] = "budget_exhausted"
            self._save_state()
        return results

    def group_meeting(self, *, dry_run: bool = False) -> list[TurnResult]:
        meeting_task = (
            "Join a concise research meeting. Review recent artifacts, state your strongest result "
            "and unresolved objection, and suggest one concrete next task for the team."
        )
        results = [
            self.dispatch(role, meeting_task, dry_run=dry_run)
            for role in ("markman", "voisin", "lie_fu")
        ]
        results.append(self.dispatch(
            "professor",
            "Chair the meeting. Read the three specialist reports just produced, resolve conflicts "
            "where possible, and assign the next concrete task.",
            dry_run=dry_run,
        ))
        meeting_path = self.meetings_dir / f"meeting-{len(self._state['meetings']) + 1:03d}.md"
        meeting_path.write_text(
            "\n\n".join(f"## {result.role}\n\n{result.response}" for result in results) + "\n",
            encoding="utf-8",
        )
        self._state["meetings"].append(str(meeting_path.relative_to(self.root)))
        self._save_state()
        return results
