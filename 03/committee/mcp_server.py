#!/usr/bin/env python3
"""Local stdio MCP transport for the Academic Center Committee."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    from .service import CommitteeService
except ImportError:  # direct execution: python3 03/committee/mcp_server.py
    from service import CommitteeService


ROOT = Path(__file__).resolve().parents[1]
COMMITTEE = CommitteeService(ROOT)


def _result(request_id: Any, payload: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _tool(name: str, description: str, required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {"type": "object", "required": required, "properties": properties},
    }


def tools() -> list[dict[str, Any]]:
    string = {"type": "string"}
    return [
        _tool("committee_health", "Read committee service health and launch state.", [], {}),
        _tool("committee_list_agents", "List registered research agents and thread metadata.", [], {}),
        _tool(
            "committee_report_status",
            "Report an agent status to the committee.",
            ["agent_id", "status"],
            {"agent_id": string, "status": string, "detail": string, "password": string},
        ),
        _tool(
            "committee_submit_manuscript",
            "Submit a math agent manuscript by a path relative to 03/.",
            ["agent_id", "version", "relative_path", "summary"],
            {
                "agent_id": string, "task_id": string, "version": string,
                "relative_path": string, "summary": string, "password": string,
            },
        ),
        _tool(
            "committee_get_submission",
            "Read one manuscript submission and its review state.",
            ["submission_id"],
            {"submission_id": string, "requester": string},
        ),
        _tool(
            "committee_get_review_task",
            "Read submissions assigned to a reviewer.",
            ["reviewer_id"],
            {"reviewer_id": string, "password": string},
        ),
        _tool(
            "committee_submit_review",
            "Submit an APPROVE or REJECT decision for a manuscript.",
            ["reviewer_id", "submission_id", "decision", "comments"],
            {"reviewer_id": string, "submission_id": string, "decision": string, "comments": string, "password": string},
        ),
        _tool(
            "committee_get_review_result",
            "Read review results belonging to a math agent.",
            ["agent_id"],
            {"agent_id": string, "password": string},
        ),
        _tool(
            "committee_send_message",
            "Write a durable committee message to another registered agent.",
            ["from_agent", "to_agent", "subject", "content"],
            {"from_agent": string, "to_agent": string, "subject": string, "content": string, "password": string},
        ),
        _tool(
            "committee_get_messages",
            "Read durable messages addressed to an agent.",
            ["agent_id"],
            {"agent_id": string, "unread_only": {"type": "boolean"}, "password": string},
        ),
        _tool(
            "committee_create_meeting",
            "Create a committee-organized group meeting for statements and peer discussion.",
            ["title", "topic"],
            {"title": string, "topic": string, "participants": {"type": "array", "items": string}, "created_by": string},
        ),
        _tool(
            "committee_submit_meeting_statement",
            "Submit an agent statement to an open group meeting.",
            ["agent_id", "meeting_id"],
            {
                "agent_id": string, "meeting_id": string, "content": string,
                "version": string, "relative_path": string, "password": string,
            },
        ),
        _tool(
            "committee_submit_meeting_comment",
            "Submit a comment on another participant's group-meeting statement.",
            ["agent_id", "meeting_id", "statement_id", "content"],
            {"agent_id": string, "meeting_id": string, "statement_id": string, "content": string, "password": string},
        ),
        _tool(
            "committee_get_meeting_discussion",
            "Read all statements, comments, and returned syntheses for a meeting.",
            ["meeting_id"],
            {"meeting_id": string, "requester": string},
        ),
        _tool(
            "committee_finalize_meeting",
            "Close discussion and return the complete committee feedback packet to every participant.",
            ["meeting_id"],
            {"meeting_id": string, "digest": string, "finalized_by": string},
        ),
        _tool(
            "committee_submit_meeting_synthesis",
            "Submit an agent's compressed, internalized synthesis after committee feedback is returned.",
            ["agent_id", "meeting_id", "content"],
            {"agent_id": string, "meeting_id": string, "content": string, "version": string, "password": string},
        ),
        _tool(
            "committee_get_meeting_syntheses",
            "Read the internalized syntheses submitted for a completed meeting.",
            ["meeting_id"],
            {"meeting_id": string, "requester": string},
        ),
    ]


def call_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "committee_health":
        return COMMITTEE.health()
    if name == "committee_list_agents":
        return COMMITTEE.list_agents(args.get("requester"))
    if name == "committee_report_status":
        return COMMITTEE.report_status(
            args["agent_id"], args["status"], detail=args.get("detail", ""), password=args.get("password")
        )
    if name == "committee_submit_manuscript":
        return COMMITTEE.submit_manuscript(
            args["agent_id"], args["version"], args["relative_path"], args["summary"],
            task_id=args.get("task_id"), password=args.get("password")
        )
    if name == "committee_get_submission":
        return COMMITTEE.get_submission(args["submission_id"], requester=args.get("requester"))
    if name == "committee_get_review_task":
        return COMMITTEE.get_review_task(args["reviewer_id"], password=args.get("password"))
    if name == "committee_submit_review":
        return COMMITTEE.submit_review(
            args["reviewer_id"], args["submission_id"], args["decision"], args["comments"], password=args.get("password")
        )
    if name == "committee_get_review_result":
        return COMMITTEE.get_review_result(args["agent_id"], password=args.get("password"))
    if name == "committee_send_message":
        return COMMITTEE.send_message(
            args["from_agent"], args["to_agent"], args["subject"], args["content"], password=args.get("password")
        )
    if name == "committee_get_messages":
        return COMMITTEE.get_messages(
            args["agent_id"], unread_only=bool(args.get("unread_only", False)), password=args.get("password")
        )
    if name == "committee_create_meeting":
        return COMMITTEE.create_meeting(
            args["title"], args["topic"], participants=args.get("participants"), created_by=args.get("created_by")
        )
    if name == "committee_submit_meeting_statement":
        return COMMITTEE.submit_meeting_statement(
            args["agent_id"], args["meeting_id"], args.get("content"),
            version=args.get("version", "v1"), relative_path=args.get("relative_path"), password=args.get("password")
        )
    if name == "committee_submit_meeting_comment":
        return COMMITTEE.submit_meeting_comment(
            args["agent_id"], args["meeting_id"], args["statement_id"], args["content"], password=args.get("password")
        )
    if name == "committee_get_meeting_discussion":
        return COMMITTEE.get_meeting_discussion(args["meeting_id"], requester=args.get("requester"))
    if name == "committee_finalize_meeting":
        return COMMITTEE.finalize_meeting(
            args["meeting_id"], args.get("digest"), finalized_by=args.get("finalized_by")
        )
    if name == "committee_submit_meeting_synthesis":
        return COMMITTEE.submit_meeting_synthesis(
            args["agent_id"], args["meeting_id"], args["content"],
            version=args.get("version", "v1"), password=args.get("password")
        )
    if name == "committee_get_meeting_syntheses":
        return COMMITTEE.get_meeting_syntheses(args["meeting_id"], requester=args.get("requester"))
    raise ValueError(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method in {"notifications/initialized", "notifications/cancelled"}:
        return None
    if method == "initialize":
        return _result(
            request_id,
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "academic-center-committee", "version": "0.1.0"},
            },
        )
    if method == "tools/list":
        return _result(request_id, {"tools": tools()})
    if method == "tools/call":
        try:
            params = message.get("params", {})
            payload = call_tool(params["name"], params.get("arguments", {}))
            return _result(request_id, {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]})
        except (KeyError, TypeError, ValueError, PermissionError) as exc:
            return _error(request_id, -32602, str(exc))
        except Exception as exc:  # keep the stdio server alive for one bad request
            return _error(request_id, -32000, str(exc))
    if request_id is None:
        return None
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except json.JSONDecodeError as exc:
            response = _error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
