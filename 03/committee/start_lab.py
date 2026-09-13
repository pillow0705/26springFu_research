#!/usr/bin/env python3
"""Launch the 03 research threads and concurrent math goals."""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox


ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "agent"
STATE_PATH = ROOT / "runtime" / "launch.json"
MODEL = "gpt-5.6-luna"
EFFORT = "high"
PHASE_SECONDS = {"first": 5 * 60, "second": 15 * 60}


@dataclass(frozen=True)
class AgentSpec:
    role: str
    path: Path
    is_math: bool


@dataclass
class AgentHandle:
    spec: AgentSpec
    client: Codex
    thread_id: str
    goal_state: object | None = None
    goal_turn_id: str | None = None
    goal_status: str | None = None


def specs() -> list[AgentSpec]:
    entries = [
        AgentSpec(f"math{i}", AGENT_ROOT / f"math{i}", True) for i in range(1, 22)
    ]
    entries.extend(
        AgentSpec(f"review{i}", AGENT_ROOT / f"review{i}", False) for i in range(1, 22)
    )
    entries.append(AgentSpec("Writer", AGENT_ROOT / "Writer", False))
    return entries


def _prepare_group_workspaces(agent_specs: list[AgentSpec]) -> None:
    for spec in agent_specs:
        (spec.path / "workspace" / "group_meeting").mkdir(parents=True, exist_ok=True)


def _instructions(spec: AgentSpec) -> str:
    return (spec.path / "AGNET").read_text(encoding="utf-8")


def _objective(spec: AgentSpec) -> str:
    return (
        f"完成 {spec.role} 的 AGNET 文件中规定的研究任务。"
        "持续推进证明、计算和结果记录；遇到无法证明的步骤，明确记录阻塞点。"
        "只有形成可审稿的结论后才将目标标记为完成。"
    )


def _new_handle(spec: AgentSpec) -> AgentHandle:
    home = spec.path / ".codex"
    config = CodexConfig(env={"CODEX_HOME": str(home)}, cwd=str(spec.path))
    client = Codex(config)
    thread = client.thread_start(
        model=MODEL,
        cwd=str(spec.path),
        ephemeral=False,
        sandbox=Sandbox.workspace_write,
        approval_mode=ApprovalMode.deny_all,
        config={"model_reasoning_effort": EFFORT},
        base_instructions=_instructions(spec),
    )
    return AgentHandle(spec, client, thread.id)


def _resume_handle(spec: AgentSpec, thread_id: str) -> AgentHandle:
    home = spec.path / ".codex"
    config = CodexConfig(env={"CODEX_HOME": str(home)}, cwd=str(spec.path))
    client = Codex(config)
    thread = client.thread_resume(
        thread_id,
        model=MODEL,
        cwd=str(spec.path),
        sandbox=Sandbox.workspace_write,
        approval_mode=ApprovalMode.deny_all,
        config={"model_reasoning_effort": EFFORT},
    )
    return AgentHandle(spec, client, thread.id)


def _start_goal(handle: AgentHandle) -> AgentHandle:
    state, turn_id = handle.client._client.start_goal_operation(
        handle.thread_id,
        _objective(handle.spec),
    )
    handle.goal_state = state
    handle.goal_turn_id = turn_id
    return handle


def _load_state() -> dict[str, object] | None:
    if not STATE_PATH.exists():
        return None
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def _save_state(handles: list[AgentHandle], phase: str) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "model": MODEL,
        "reasoning_effort": EFFORT,
        "agents": {
            handle.spec.role: {
                "thread_id": handle.thread_id,
                "goal": handle.spec.is_math,
                "goal_status": getattr(getattr(handle.goal_state, "status", None), "value", None),
            }
            for handle in handles
        },
    }
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=STATE_PATH.parent, delete=False
    ) as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    temporary.replace(STATE_PATH)


def _close_handles(handles: list[AgentHandle]) -> None:
    for handle in handles:
        if handle.goal_state is not None and not handle.goal_state.is_finished():
            try:
                handle.client._client.pause_goal(handle.thread_id)
            except Exception:
                pass
        handle.client.close()


def launch(phase: str, resume: bool, math_workers: int = 21) -> int:
    previous = _load_state() if resume else None
    if resume and previous is None:
        raise RuntimeError("--resume requires 03/runtime/launch.json")

    all_specs = specs()
    _prepare_group_workspaces(all_specs)
    handles: list[AgentHandle] = []
    try:
        with ThreadPoolExecutor(max_workers=len(all_specs)) as pool:
            futures = {}
            for spec in all_specs:
                old = (previous or {}).get("agents", {}).get(spec.role, {})
                if resume and old.get("thread_id"):
                    futures[pool.submit(_resume_handle, spec, old["thread_id"])] = spec.role
                else:
                    futures[pool.submit(_new_handle, spec)] = spec.role
            for future in as_completed(futures):
                handles.append(future.result())

        handles.sort(key=lambda item: all_specs.index(item.spec))
        math_handles = [handle for handle in handles if handle.spec.is_math]
        math_workers = max(1, min(math_workers, len(math_handles)))
        with ThreadPoolExecutor(max_workers=math_workers) as pool:
            goal_futures = [pool.submit(_start_goal, handle) for handle in math_handles]
            for future in as_completed(goal_futures):
                future.result()

        _save_state(handles, phase)
        print(f"THREADS_CREATED={len(handles)}")
        print(f"GOALS_STARTED={len(math_handles)}")
        print(f"PHASE={phase} DURATION_SECONDS={PHASE_SECONDS[phase]}")

        deadline = time.monotonic() + PHASE_SECONDS[phase]
        while time.monotonic() < deadline:
            if all(
                handle.goal_state is not None and handle.goal_state.is_finished()
                for handle in math_handles
            ):
                break
            time.sleep(2)
        _save_state(handles, phase)
        return 0
    finally:
        _close_handles(handles)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=sorted(PHASE_SECONDS), default="first")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--math-workers",
        type=int,
        default=21,
        help="max concurrent math goals in this phase (default: 21)",
    )
    parser.add_argument("--auto", action="store_true", help="run phase and the remaining later phases")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        if args.auto:
            start = list(PHASE_SECONDS).index(args.phase)
            for phase in list(PHASE_SECONDS)[start:]:
                print("THREADS_CREATED=43")
                print(f"GOALS_STARTED={min(21, args.math_workers)}")
                print(f"PHASE={phase} DURATION_SECONDS={PHASE_SECONDS[phase]}")
                print(f"MATH_WORKERS={args.math_workers}")
            return 0
        print("THREADS_CREATED=43")
        print(f"GOALS_STARTED={min(21, args.math_workers)}")
        print(f"PHASE={args.phase} DURATION_SECONDS={PHASE_SECONDS[args.phase]}")
        print(f"MATH_WORKERS={args.math_workers}")
        return 0
    if not args.auto:
        return launch(args.phase, args.resume, args.math_workers)

    if args.phase == "second":
        return launch("second", args.resume, args.math_workers)

    status = launch("first", args.resume, args.math_workers)
    if status != 0:
        return status
    return launch("second", True, args.math_workers)


if __name__ == "__main__":
    raise SystemExit(main())
