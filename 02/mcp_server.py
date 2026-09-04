#!/usr/bin/env python3
"""Small stdio MCP-style backend for the research laboratory.

The server intentionally exposes only lab operations. It keeps transport simple and dependency
free so it can be launched from a Codex MCP configuration or tested from a shell.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from lab import ResearchLab


ROOT = Path(__file__).resolve().parent
LAB = ResearchLab(ROOT)


def result(request_id: Any, payload: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": payload}


def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "research_read_workspace",
            "description": "Read recent durable artifacts from the shared research workspace.",
            "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
        },
        {
            "name": "research_write_note",
            "description": "Write a durable note into the shared inbox.",
            "inputSchema": {
                "type": "object",
                "required": ["author", "title", "content"],
                "properties": {
                    "author": {"type": "string"},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
            },
        },
        {
            "name": "research_request_dialogue",
            "description": "Record a request for another role to discuss a research question.",
            "inputSchema": {
                "type": "object",
                "required": ["from_role", "to_role", "topic"],
                "properties": {
                    "from_role": {"type": "string"},
                    "to_role": {"type": "string"},
                    "topic": {"type": "string"},
                },
            },
        },
    ]


def call_tool(name: str, args: dict[str, Any]) -> str:
    if name == "research_read_workspace":
        return LAB.shared_context(int(args.get("limit", 6)))
    if name == "research_write_note":
        inbox = ROOT / "inbox"
        inbox.mkdir(exist_ok=True)
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in args["title"]).strip("_")
        if not safe_title:
            raise ValueError("title must contain at least one alphanumeric character")
        path = inbox / f"{safe_title[:80]}.md"
        path.write_text(f"# {args['title']}\n\nAuthor: {args['author']}\n\n{args['content']}\n", encoding="utf-8")
        return f"Wrote {path.relative_to(ROOT)}"
    if name == "research_request_dialogue":
        inbox = ROOT / "inbox"
        inbox.mkdir(exist_ok=True)
        path = inbox / "dialogue_requests.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {args['from_role']} -> {args['to_role']}: {args['topic']}\n")
        return "Dialogue request recorded"
    raise ValueError(f"Unknown tool: {name}")


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return result(request_id, {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "simulated-algebra-lab", "version": "0.1.0"},
        })
    if method == "tools/list":
        return result(request_id, {"tools": tools()})
    if method == "tools/call":
        try:
            params = message.get("params", {})
            text = call_tool(params["name"], params.get("arguments", {}))
            return result(request_id, {"content": [{"type": "text", "text": text}]})
        except (KeyError, TypeError, ValueError) as exc:
            return error(request_id, -32602, str(exc))
    if request_id is None:
        return None
    return error(request_id, -32601, f"Method not found: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except json.JSONDecodeError as exc:
            response = error(None, -32700, str(exc))
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
