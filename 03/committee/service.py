"""Stateful Academic Center Committee service.

The committee owns agent registration, manuscript intake, reviewer dispatch, review
results, and the durable group-meeting workflow.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASKS: tuple[tuple[str, str], ...] = (
    ("S1", "Type I(1)"),
    ("S2", "Type I(2)"),
    ("S3", "Type I(3)"),
    ("S4", "Type I(6)"),
    ("S5", "Type II(1)"),
    ("S6", "Type II(3)"),
    ("S7", "Type III(1)"),
    ("S8", "Type IV(1,1)"),
    ("S9", "Type IV(2,1)"),
    ("S10", "Type IV(3,1)"),
    ("S11", "Type IV(6,1)"),
    ("N1", "5+1"),
    ("N2", "4+2"),
    ("N3", "4+1+1"),
    ("N4", "3+3"),
    ("N5", "3+2+1"),
    ("N6", "3+1+1+1"),
    ("N7", "2+2+2"),
    ("N8", "2+2+1+1"),
    ("N9", "2+1+1+1+1"),
    ("N10", "1+1+1+1+1+1"),
)
TASK_BY_INDEX = {index + 1: task_id for index, (task_id, _label) in enumerate(TASKS)}
TASK_LABELS = dict(TASKS)
AGENT_RE = re.compile(r"^(math|review)([1-9]|1[0-9]|2[01])$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DECISIONS = {"APPROVE", "REJECT"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_task(agent_id: str) -> str | None:
    match = AGENT_RE.fullmatch(agent_id)
    if not match:
        return None
    return TASK_BY_INDEX[int(match.group(2))]


def _kind(agent_id: str) -> str:
    if agent_id == "Writer":
        return "writer"
    return "math" if agent_id.startswith("math") else "reviewer"


class CommitteeStore:
    """Small SQLite persistence layer safe for concurrent MCP processes."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS agents (
                    agent_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    task_id TEXT,
                    thread_id TEXT,
                    status TEXT NOT NULL DEFAULT 'registered',
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS submissions (
                    submission_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    review_path TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decision TEXT,
                    comments TEXT,
                    reviewer_response TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    reviewed_at TEXT
                );
                CREATE INDEX IF NOT EXISTS submissions_reviewer_status
                    ON submissions(reviewer_id, status);
                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT
                );
                CREATE TABLE IF NOT EXISTS meetings (
                    meeting_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    returned_at TEXT,
                    digest TEXT
                );
                CREATE TABLE IF NOT EXISTS meeting_participants (
                    meeting_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    PRIMARY KEY (meeting_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS meeting_statements (
                    statement_id TEXT PRIMARY KEY,
                    meeting_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_path TEXT,
                    workspace_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS meeting_statements_lookup
                    ON meeting_statements(meeting_id, created_at);
                CREATE TABLE IF NOT EXISTS meeting_comments (
                    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id TEXT NOT NULL,
                    statement_id TEXT NOT NULL,
                    commenter_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS meeting_comments_lookup
                    ON meeting_comments(meeting_id, statement_id, created_at);
                CREATE TABLE IF NOT EXISTS meeting_syntheses (
                    meeting_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    content TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (meeting_id, agent_id)
                );
                """
            )

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    def register_agents(self) -> None:
        entries = [(f"math{i}", "math", TASK_BY_INDEX[i]) for i in range(1, 22)]
        entries += [(f"review{i}", "reviewer", TASK_BY_INDEX[i]) for i in range(1, 22)]
        entries.append(("Writer", "writer", None))
        with self._connect() as connection:
            for agent_id, kind, task_id in entries:
                connection.execute(
                    """INSERT INTO agents(agent_id, kind, task_id, updated_at)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(agent_id) DO UPDATE SET
                         kind=excluded.kind, task_id=excluded.task_id,
                         updated_at=excluded.updated_at""",
                    (agent_id, kind, task_id, _now()),
                )

    def update_agent(
        self,
        agent_id: str,
        *,
        status: str | None = None,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if thread_id is not None:
            fields.append("thread_id = ?")
            values.append(thread_id)
        fields.append("updated_at = ?")
        values.append(_now())
        values.append(agent_id)
        with self._connect() as connection:
            connection.execute(f"UPDATE agents SET {', '.join(fields)} WHERE agent_id = ?", values)
            row = connection.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
        if row is None:
            raise KeyError(f"Unknown agent: {agent_id}")
        return dict(row)

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(connection.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone())

    def list_agents(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM agents ORDER BY kind, agent_id").fetchall()
        return [dict(row) for row in rows]

    def create_submission(self, data: dict[str, Any]) -> dict[str, Any]:
        columns = (
            "submission_id", "agent_id", "reviewer_id", "task_id", "version",
            "source_path", "review_path", "summary", "status", "created_at",
        )
        values = tuple(data[column] for column in columns)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO submissions({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                values,
            )
        return self.get_submission(data["submission_id"]) or data

    def update_submission(self, submission_id: str, **updates: Any) -> dict[str, Any]:
        allowed = {
            "status", "decision", "comments", "reviewer_response", "error", "reviewed_at"
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported submission fields: {sorted(unknown)}")
        if not updates:
            return self.get_submission(submission_id) or {}
        assignments = ", ".join(f"{key} = ?" for key in updates)
        values = [updates[key] for key in updates] + [submission_id]
        with self._connect() as connection:
            connection.execute(f"UPDATE submissions SET {assignments} WHERE submission_id = ?", values)
        return self.get_submission(submission_id) or {}

    def get_submission(self, submission_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(
                connection.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)).fetchone()
            )

    def list_submissions(
        self,
        *,
        reviewer_id: str | None = None,
        agent_id: str | None = None,
        statuses: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if reviewer_id is not None:
            clauses.append("reviewer_id = ?")
            values.append(reviewer_id)
        if agent_id is not None:
            clauses.append("agent_id = ?")
            values.append(agent_id)
        if statuses:
            placeholders = ", ".join("?" for _ in statuses)
            clauses.append(f"status IN ({placeholders})")
            values.extend(statuses)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM submissions{where} ORDER BY created_at DESC", values
            ).fetchall()
        return [dict(row) for row in rows]

    def add_message(self, from_agent: str, to_agent: str, subject: str, content: str) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO messages(from_agent, to_agent, subject, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (from_agent, to_agent, subject, content, _now()),
            )
            message_id = cursor.lastrowid
            row = connection.execute("SELECT * FROM messages WHERE message_id = ?", (message_id,)).fetchone()
        return dict(row)

    def list_messages(self, to_agent: str, *, unread_only: bool = False) -> list[dict[str, Any]]:
        query = "SELECT * FROM messages WHERE to_agent = ?"
        values: list[Any] = [to_agent]
        if unread_only:
            query += " AND read_at IS NULL"
        query += " ORDER BY message_id"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def create_meeting(self, data: dict[str, Any], participants: list[str]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO meetings(meeting_id, title, topic, status, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    data["meeting_id"], data["title"], data["topic"], data["status"],
                    data["created_by"], data["created_at"],
                ),
            )
            connection.executemany(
                "INSERT INTO meeting_participants(meeting_id, agent_id) VALUES (?, ?)",
                [(data["meeting_id"], agent_id) for agent_id in participants],
            )
        return self.get_meeting(data["meeting_id"]) or data

    def get_meeting(self, meeting_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            meeting = self._row(
                connection.execute("SELECT * FROM meetings WHERE meeting_id = ?", (meeting_id,)).fetchone()
            )
            if meeting is None:
                return None
            participants = connection.execute(
                "SELECT agent_id FROM meeting_participants WHERE meeting_id = ? ORDER BY agent_id",
                (meeting_id,),
            ).fetchall()
        meeting["participants"] = [row["agent_id"] for row in participants]
        return meeting

    def update_meeting(self, meeting_id: str, **updates: Any) -> dict[str, Any]:
        allowed = {"status", "returned_at", "digest"}
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError(f"Unsupported meeting fields: {sorted(unknown)}")
        if updates:
            assignments = ", ".join(f"{key} = ?" for key in updates)
            values = [updates[key] for key in updates] + [meeting_id]
            with self._connect() as connection:
                connection.execute(f"UPDATE meetings SET {assignments} WHERE meeting_id = ?", values)
        return self.get_meeting(meeting_id) or {}

    def meeting_participants(self, meeting_id: str) -> list[str]:
        meeting = self.get_meeting(meeting_id)
        if meeting is None:
            raise KeyError(f"unknown meeting_id: {meeting_id}")
        return list(meeting["participants"])

    def create_statement(self, data: dict[str, Any]) -> dict[str, Any]:
        columns = (
            "statement_id", "meeting_id", "agent_id", "version", "content",
            "source_path", "workspace_path", "created_at",
        )
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO meeting_statements({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                tuple(data[column] for column in columns),
            )
        return self.get_statement(data["statement_id"]) or data

    def get_statement(self, statement_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(
                connection.execute(
                    "SELECT * FROM meeting_statements WHERE statement_id = ?", (statement_id,)
                ).fetchone()
            )

    def list_statements(self, meeting_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM meeting_statements WHERE meeting_id = ? ORDER BY created_at, statement_id",
                (meeting_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_comment(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            cursor = connection.execute(
                """INSERT INTO meeting_comments(
                   meeting_id, statement_id, commenter_id, content, created_at
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    data["meeting_id"], data["statement_id"], data["commenter_id"],
                    data["content"], data["created_at"],
                ),
            )
            comment_id = cursor.lastrowid
            row = connection.execute(
                "SELECT * FROM meeting_comments WHERE comment_id = ?", (comment_id,)
            ).fetchone()
        return dict(row)

    def list_comments(self, meeting_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM meeting_comments WHERE meeting_id = ? ORDER BY created_at, comment_id",
                (meeting_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_synthesis(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """INSERT INTO meeting_syntheses(
                   meeting_id, agent_id, version, content, workspace_path, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(meeting_id, agent_id) DO UPDATE SET
                   version=excluded.version, content=excluded.content,
                   workspace_path=excluded.workspace_path, created_at=excluded.created_at""",
                (
                    data["meeting_id"], data["agent_id"], data["version"], data["content"],
                    data["workspace_path"], data["created_at"],
                ),
            )
        return self.get_synthesis(data["meeting_id"], data["agent_id"]) or data

    def get_synthesis(self, meeting_id: str, agent_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            return self._row(
                connection.execute(
                    "SELECT * FROM meeting_syntheses WHERE meeting_id = ? AND agent_id = ?",
                    (meeting_id, agent_id),
                ).fetchone()
            )

    def list_syntheses(self, meeting_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM meeting_syntheses WHERE meeting_id = ? ORDER BY agent_id",
                (meeting_id,),
            ).fetchall()
        return [dict(row) for row in rows]


class CommitteeService:
    """Application service used by the local MCP transport."""

    def __init__(self, root: Path, *, db_path: Path | None = None, enable_sdk: bool = True) -> None:
        self.root = root.resolve()
        self.launch_path = self.root / "runtime" / "launch.json"
        self.store = CommitteeStore(db_path or self.root / "runtime" / "committee.sqlite")
        self.store.register_agents()
        self.ensure_group_workspaces()
        self.enable_sdk = enable_sdk

    def ensure_group_workspaces(self) -> None:
        """Create a stable workspace root for every registered agent's group-meeting work."""
        for agent in self.store.list_agents():
            (self.root / "agent" / agent["agent_id"] / "workspace" / "group_meeting").mkdir(
                parents=True, exist_ok=True
            )

    def _passwords(self) -> dict[str, str]:
        raw = os.environ.get("COMMITTEE_AGENT_PASSWORDS", "")
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("COMMITTEE_AGENT_PASSWORDS must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("COMMITTEE_AGENT_PASSWORDS must be a JSON object")
        return {str(key): str(value) for key, value in parsed.items()}

    def _require_agent(self, agent_id: str, password: str | None = None) -> dict[str, Any]:
        if not isinstance(agent_id, str) or (agent_id != "Writer" and not AGENT_RE.fullmatch(agent_id)):
            raise ValueError("invalid agent_id")
        agent = self.store.get_agent(agent_id)
        if agent is None:
            raise ValueError(f"unknown agent_id: {agent_id}")
        expected = self._passwords().get(agent_id)
        if expected is not None and password != expected:
            raise PermissionError("invalid agent credentials")
        return agent

    def _launch_manifest(self) -> dict[str, Any]:
        if not self.launch_path.exists():
            return {}
        try:
            payload = json.loads(self.launch_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("runtime/launch.json is not valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("runtime/launch.json must contain an object")
        return payload

    def _thread_id(self, agent_id: str) -> str | None:
        entry = self._launch_manifest().get("agents", {}).get(agent_id, {})
        thread_id = entry.get("thread_id") if isinstance(entry, dict) else None
        return thread_id if isinstance(thread_id, str) and thread_id else None

    def _safe_source(self, relative_path: str) -> tuple[Path, str]:
        if not isinstance(relative_path, str) or not relative_path.strip():
            raise ValueError("relative_path is required")
        candidate = Path(relative_path)
        if candidate.is_absolute():
            raise ValueError("relative_path must be relative to 03/")
        try:
            resolved = (self.root / candidate).resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError("relative_path must point to an existing file") from exc
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("relative_path must remain inside 03/") from exc
        if not resolved.is_file():
            raise ValueError("relative_path must point to a regular file")
        return resolved, relative.as_posix()

    def _review_message(self, submission: dict[str, Any]) -> str:
        return (
            "The Academic Center Committee assigned a manuscript for review.\n"
            f"Submission ID: {submission['submission_id']}\n"
            f"Task: {submission['task_id']}\n"
            f"Manuscript version: {submission['version']}\n"
            f"Read this relative path from your workspace: {submission['review_path']}\n"
            "Review the core mathematical logic only. Ignore minor style or arithmetic issues. "
            "If the requested result is proved, call committee_submit_review with APPROVE. "
            "If a serious mathematical gap breaks the result, call it with REJECT and explain why."
        )

    def _dispatch_review(self, submission: dict[str, Any]) -> dict[str, Any]:
        reviewer_id = submission["reviewer_id"]
        if not self.enable_sdk:
            return self.store.update_submission(submission["submission_id"], status="SENT_TO_REVIEWER")
        thread_id = self._thread_id(reviewer_id)
        if not thread_id:
            return self.store.update_submission(
                submission["submission_id"], status="WAITING_FOR_REVIEWER", error="reviewer thread is absent"
            )
        try:
            from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox

            reviewer_dir = self.root / "agent" / reviewer_id
            config = CodexConfig(
                env={"CODEX_HOME": str(reviewer_dir / ".codex")},
                cwd=str(reviewer_dir),
            )
            with Codex(config) as codex:
                thread = codex.thread_resume(
                    thread_id,
                    model="gpt-5.6-sol",
                    cwd=str(reviewer_dir),
                    sandbox=Sandbox.workspace_write,
                    approval_mode=ApprovalMode.deny_all,
                    config={"model_reasoning_effort": "high"},
                )
                result = thread.run(
                    self._review_message(submission),
                    model="gpt-5.6-sol",
                    effort="high",
                )
            updated = self.store.get_submission(submission["submission_id"]) or submission
            if updated.get("decision") in DECISIONS:
                return self.store.update_submission(
                    submission["submission_id"], reviewer_response=result.final_response or ""
                )
            return self.store.update_submission(
                submission["submission_id"],
                status="REVIEWING",
                reviewer_response=result.final_response or "",
            )
        except Exception as exc:
            return self.store.update_submission(
                submission["submission_id"], status="FAILED", error=f"reviewer dispatch failed: {exc}"
            )

    def _committee_actor(self, actor: str | None) -> str:
        if actor in (None, "committee"):
            return "committee"
        agent = self._require_agent(actor)
        if agent["kind"] != "writer":
            raise PermissionError("only the committee or Writer can organize group meetings")
        return actor

    def _meeting(self, meeting_id: str) -> dict[str, Any]:
        if not isinstance(meeting_id, str) or not meeting_id.strip():
            raise ValueError("meeting_id is required")
        meeting = self.store.get_meeting(meeting_id)
        if meeting is None:
            raise KeyError(f"unknown meeting_id: {meeting_id}")
        return meeting

    def _meeting_participant(self, meeting: dict[str, Any], agent_id: str, password: str | None = None) -> dict[str, Any]:
        agent = self._require_agent(agent_id, password)
        if agent_id not in meeting["participants"]:
            raise PermissionError(f"{agent_id} is not a participant in {meeting['meeting_id']}")
        return agent

    def _group_workspace(self, agent_id: str, meeting_id: str) -> Path:
        workspace = self.root / "agent" / agent_id / "workspace" / "group_meeting" / meeting_id
        workspace.mkdir(parents=True, exist_ok=True)
        return workspace

    def create_meeting(
        self,
        title: str,
        topic: str,
        *,
        participants: list[str] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        actor = self._committee_actor(created_by)
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("topic is required")
        selected = participants if participants is not None else [f"math{i}" for i in range(1, 22)]
        if not isinstance(selected, list) or not selected:
            raise ValueError("participants must be a non-empty list")
        normalized: list[str] = []
        for agent_id in selected:
            agent = self._require_agent(agent_id)
            if agent_id not in normalized:
                normalized.append(agent_id)
        meeting_id = f"meeting-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"
        record = {
            "meeting_id": meeting_id,
            "title": title.strip(),
            "topic": topic.strip(),
            "status": "OPEN",
            "created_by": actor,
            "created_at": _now(),
        }
        meeting = self.store.create_meeting(record, normalized)
        brief = f"# {meeting['title']}\n\n## Topic\n\n{meeting['topic']}\n\nMeeting ID: `{meeting_id}`\n"
        for agent_id in normalized:
            workspace = self._group_workspace(agent_id, meeting_id)
            (workspace / "brief.md").write_text(brief, encoding="utf-8")
        return meeting

    def submit_meeting_statement(
        self,
        agent_id: str,
        meeting_id: str,
        content: str | None = None,
        *,
        version: str = "v1",
        relative_path: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        meeting = self._meeting(meeting_id)
        if meeting["status"] != "OPEN":
            raise ValueError("meeting is no longer accepting statements")
        self._meeting_participant(meeting, agent_id, password)
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            raise ValueError("version must contain only letters, numbers, '.', '_' or '-'")
        if content is not None and (not isinstance(content, str) or not content.strip()):
            raise ValueError("content must not be empty")
        source_path: str | None = None
        if content is None:
            if not relative_path:
                raise ValueError("provide content or relative_path")
            source, source_path = self._safe_source(relative_path)
            try:
                content = source.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("relative_path must point to a UTF-8 text file") from exc
        assert content is not None
        statement_id = f"{meeting_id}-statement-{agent_id}-{uuid.uuid4().hex[:8]}"
        workspace = self._group_workspace(agent_id, meeting_id)
        statement_file = workspace / f"statement-{version}.md"
        statement_file.write_text(
            f"# Statement by {agent_id}\n\nVersion: {version}\n\n{content.strip()}\n",
            encoding="utf-8",
        )
        record = self.store.create_statement(
            {
                "statement_id": statement_id,
                "meeting_id": meeting_id,
                "agent_id": agent_id,
                "version": version,
                "content": content.strip(),
                "source_path": source_path,
                "workspace_path": statement_file.relative_to(self.root).as_posix(),
                "created_at": _now(),
            }
        )
        return record

    def submit_meeting_comment(
        self,
        agent_id: str,
        meeting_id: str,
        statement_id: str,
        content: str,
        *,
        password: str | None = None,
    ) -> dict[str, Any]:
        meeting = self._meeting(meeting_id)
        if meeting["status"] != "OPEN":
            raise ValueError("meeting is no longer accepting comments")
        self._meeting_participant(meeting, agent_id, password)
        statement = self.store.get_statement(statement_id)
        if statement is None or statement["meeting_id"] != meeting_id:
            raise KeyError(f"unknown statement_id: {statement_id}")
        if statement["agent_id"] == agent_id:
            raise ValueError("comments must be directed to another participant's statement")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content is required")
        record = self.store.create_comment(
            {
                "meeting_id": meeting_id,
                "statement_id": statement_id,
                "commenter_id": agent_id,
                "content": content.strip(),
                "created_at": _now(),
            }
        )
        workspace = self._group_workspace(agent_id, meeting_id)
        (workspace / "comments").mkdir(parents=True, exist_ok=True)
        (workspace / "comments" / f"{record['comment_id']}-{statement_id}.md").write_text(
            f"# Comment on {statement_id}\n\n{content.strip()}\n", encoding="utf-8"
        )
        return record

    def get_meeting_discussion(self, meeting_id: str, requester: str | None = None) -> dict[str, Any]:
        meeting = self._meeting(meeting_id)
        if requester is not None:
            if requester == "Writer":
                self._require_agent(requester)
            else:
                self._meeting_participant(meeting, requester)
        return {
            "meeting": meeting,
            "statements": self.store.list_statements(meeting_id),
            "comments": self.store.list_comments(meeting_id),
            "syntheses": self.store.list_syntheses(meeting_id),
        }

    def _render_meeting_packet(self, meeting: dict[str, Any], digest: str) -> str:
        statements = self.store.list_statements(meeting["meeting_id"])
        comments = self.store.list_comments(meeting["meeting_id"])
        by_statement: dict[str, list[dict[str, Any]]] = {}
        for comment in comments:
            by_statement.setdefault(comment["statement_id"], []).append(comment)
        lines = [
            f"# Group Meeting Feedback: {meeting['title']}",
            "",
            f"Meeting ID: `{meeting['meeting_id']}`",
            f"Topic: {meeting['topic']}",
            "",
            "## Committee Return",
            "",
            digest.strip(),
            "",
            "## Statements and Discussion",
        ]
        for statement in statements:
            lines.extend(["", f"### {statement['statement_id']} — {statement['agent_id']} ({statement['version']})", "", statement["content"]])
            for comment in by_statement.get(statement["statement_id"], []):
                lines.extend(["", f"> **{comment['commenter_id']} commented:** {comment['content']}"])
        lines.extend(["", "## Required Internalization", "", "Write your own compressed synthesis and submit it through `committee_submit_meeting_synthesis`.", ""])
        return "\n".join(lines)

    def finalize_meeting(
        self,
        meeting_id: str,
        digest: str | None = None,
        *,
        finalized_by: str | None = None,
    ) -> dict[str, Any]:
        actor = self._committee_actor(finalized_by)
        meeting = self._meeting(meeting_id)
        if meeting["status"] != "OPEN":
            raise ValueError("meeting has already been returned")
        if digest is None:
            digest = "The committee returned the complete statement and discussion packet. Each participant must compress and internalize the material in a personal synthesis."
        if not isinstance(digest, str) or not digest.strip():
            raise ValueError("digest must not be empty")
        packet = self._render_meeting_packet(meeting, digest)
        updated = self.store.update_meeting(meeting_id, status="RETURNED", returned_at=_now(), digest=digest.strip())
        feedback_paths: dict[str, str] = {}
        for agent_id in meeting["participants"]:
            workspace = self._group_workspace(agent_id, meeting_id)
            path = workspace / "committee-feedback.md"
            path.write_text(packet, encoding="utf-8")
            relative = path.relative_to(self.root).as_posix()
            feedback_paths[agent_id] = relative
            self.store.add_message(
                actor,
                agent_id,
                f"Group meeting feedback: {meeting['title']}",
                f"The committee returned the discussion packet at {relative}. Read it and submit your internalized synthesis.",
            )
        updated["feedback_paths"] = feedback_paths
        return updated

    def submit_meeting_synthesis(
        self,
        agent_id: str,
        meeting_id: str,
        content: str,
        *,
        version: str = "v1",
        password: str | None = None,
    ) -> dict[str, Any]:
        meeting = self._meeting(meeting_id)
        if meeting["status"] != "RETURNED":
            raise ValueError("meeting feedback has not been returned yet")
        self._meeting_participant(meeting, agent_id, password)
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            raise ValueError("version must contain only letters, numbers, '.', '_' or '-'")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content is required")
        workspace = self._group_workspace(agent_id, meeting_id)
        path = workspace / f"synthesis-{version}.md"
        path.write_text(
            f"# Internalized synthesis by {agent_id}\n\nVersion: {version}\n\n{content.strip()}\n",
            encoding="utf-8",
        )
        record = self.store.create_synthesis(
            {
                "meeting_id": meeting_id,
                "agent_id": agent_id,
                "version": version,
                "content": content.strip(),
                "workspace_path": path.relative_to(self.root).as_posix(),
                "created_at": _now(),
            }
        )
        self.store.add_message(
            agent_id,
            "committee",
            f"Internalized group meeting synthesis: {meeting_id}",
            f"Synthesis submitted at {record['workspace_path']}",
        )
        return record

    def get_meeting_syntheses(self, meeting_id: str, requester: str | None = None) -> list[dict[str, Any]]:
        self._meeting(meeting_id)
        self._committee_actor(requester)
        return self.store.list_syntheses(meeting_id)

    def health(self) -> dict[str, Any]:
        agents = self.store.list_agents()
        submissions = self.store.list_submissions()
        return {
            "service": "academic_center_committee",
            "status": "ok",
            "launch_loaded": self.launch_path.exists(),
            "agent_count": len(agents),
            "submission_count": len(submissions),
            "reviewed_count": sum(1 for item in submissions if item.get("decision") in DECISIONS),
        }

    def list_agents(self, requester: str | None = None) -> list[dict[str, Any]]:
        if requester is not None:
            self._require_agent(requester)
        manifest = self._launch_manifest().get("agents", {})
        result = []
        for agent in self.store.list_agents():
            entry = manifest.get(agent["agent_id"], {})
            agent = dict(agent)
            if isinstance(entry, dict):
                agent["thread_id"] = entry.get("thread_id")
                agent["goal_status"] = entry.get("goal_status")
            result.append(agent)
        return result

    def report_status(
        self,
        agent_id: str,
        status: str,
        *,
        detail: str = "",
        password: str | None = None,
    ) -> dict[str, Any]:
        self._require_agent(agent_id, password)
        if not isinstance(status, str) or not status.strip():
            raise ValueError("status is required")
        message = self.store.add_message(agent_id, "committee", "status", f"{status}: {detail}".strip())
        agent = self.store.update_agent(agent_id, status=status.strip().upper())
        return {"agent": agent, "message": message}

    def submit_manuscript(
        self,
        agent_id: str,
        version: str,
        relative_path: str,
        summary: str,
        *,
        task_id: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        agent = self._require_agent(agent_id, password)
        if agent["kind"] != "math":
            raise PermissionError("only math agents can submit manuscripts")
        expected_task = agent["task_id"]
        if task_id is not None and task_id != expected_task:
            raise ValueError(f"{agent_id} is assigned to {expected_task}, not {task_id}")
        if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
            raise ValueError("version must contain only letters, numbers, '.', '_' or '-'")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("summary is required")
        source, source_path = self._safe_source(relative_path)
        reviewer_id = f"review{agent_id.removeprefix('math')}"
        submission_id = f"{expected_task}-{agent_id}-{version}-{uuid.uuid4().hex[:8]}"
        target_dir = self.root / "agent" / reviewer_id / "inbox" / submission_id
        target_dir.mkdir(parents=True, exist_ok=False)
        target = target_dir / source.name
        shutil.copy2(source, target)
        record = self.store.create_submission(
            {
                "submission_id": submission_id,
                "agent_id": agent_id,
                "reviewer_id": reviewer_id,
                "task_id": expected_task,
                "version": version,
                "source_path": source_path,
                "review_path": target.relative_to(self.root).as_posix(),
                "summary": summary.strip(),
                "status": "COPIED",
                "created_at": _now(),
            }
        )
        return self._dispatch_review(record)

    def get_submission(self, submission_id: str, requester: str | None = None) -> dict[str, Any]:
        if requester is not None:
            self._require_agent(requester)
        record = self.store.get_submission(submission_id)
        if record is None:
            raise KeyError(f"unknown submission_id: {submission_id}")
        return record

    def get_review_task(self, reviewer_id: str, *, password: str | None = None) -> list[dict[str, Any]]:
        reviewer = self._require_agent(reviewer_id, password)
        if reviewer["kind"] != "reviewer":
            raise PermissionError("only reviewer agents can request review tasks")
        return self.store.list_submissions(
            reviewer_id=reviewer_id,
            statuses=("COPIED", "SENT_TO_REVIEWER", "WAITING_FOR_REVIEWER", "REVIEWING"),
        )

    def submit_review(
        self,
        reviewer_id: str,
        submission_id: str,
        decision: str,
        comments: str,
        *,
        password: str | None = None,
    ) -> dict[str, Any]:
        reviewer = self._require_agent(reviewer_id, password)
        if reviewer["kind"] != "reviewer":
            raise PermissionError("only reviewer agents can submit reviews")
        record = self.get_submission(submission_id)
        if record["reviewer_id"] != reviewer_id:
            raise PermissionError("submission is assigned to a different reviewer")
        normalized = decision.strip().upper() if isinstance(decision, str) else ""
        if normalized not in DECISIONS:
            raise ValueError("decision must be APPROVE or REJECT")
        if not isinstance(comments, str) or not comments.strip():
            raise ValueError("comments are required")
        updated = self.store.update_submission(
            submission_id,
            status="APPROVED" if normalized == "APPROVE" else "REJECTED",
            decision=normalized,
            comments=comments.strip(),
            reviewed_at=_now(),
            error=None,
        )
        self.store.add_message(
            reviewer_id,
            record["agent_id"],
            f"Review result for {submission_id}",
            f"{normalized}: {comments.strip()}",
        )
        return updated

    def get_review_result(self, agent_id: str, *, password: str | None = None) -> list[dict[str, Any]]:
        agent = self._require_agent(agent_id, password)
        if agent["kind"] != "math":
            raise PermissionError("only math agents can request their review results")
        return self.store.list_submissions(agent_id=agent_id)

    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        subject: str,
        content: str,
        *,
        password: str | None = None,
    ) -> dict[str, Any]:
        self._require_agent(from_agent, password)
        self._require_agent(to_agent)
        if not isinstance(subject, str) or not subject.strip():
            raise ValueError("subject is required")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("content is required")
        return self.store.add_message(from_agent, to_agent, subject.strip(), content.strip())

    def get_messages(self, agent_id: str, *, unread_only: bool = False, password: str | None = None) -> list[dict[str, Any]]:
        self._require_agent(agent_id, password)
        return self.store.list_messages(agent_id, unread_only=unread_only)
