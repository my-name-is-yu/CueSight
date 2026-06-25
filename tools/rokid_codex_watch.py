#!/usr/bin/env python3
"""Watch a local Codex feed file and mirror compact status text to Rokid."""

from __future__ import annotations

import argparse
import json
import sys
import time
import textwrap
import sqlite3
from pathlib import Path

from rokid_codex_bridge import push_message


DEFAULT_FEED = "/tmp/codex-rokid-feed.txt"
DEFAULT_CODEX_STATE_DB = str(Path.home() / ".codex" / "state_5.sqlite")
RETRY_SECONDS = 3.0


def read_source(args: argparse.Namespace) -> str:
    if args.stdin:
        return sys.stdin.read()
    if args.session_id:
        return read_session_summary(args)
    feed = Path(args.feed)
    if not feed.exists():
        return ""
    return feed.read_text(encoding="utf-8", errors="replace")


def resolve_rollout_path(session_id: str, state_db: str) -> Path:
    db = Path(state_db).expanduser()
    if not db.exists():
        raise SystemExit(f"Codex state DB not found: {db}")
    with sqlite3.connect(db) as conn:
        row = conn.execute("select rollout_path from threads where id = ?", (session_id,)).fetchone()
    if not row or not row[0]:
        raise SystemExit(f"Codex session not found: {session_id}")
    rollout = Path(row[0]).expanduser()
    if not rollout.exists():
        raise SystemExit(f"Codex rollout file not found: {rollout}")
    return rollout


def message_text(payload: dict) -> tuple[str, str] | None:
    if payload.get("type") != "message":
        return None
    role = payload.get("role")
    if role not in ("user", "assistant"):
        return None
    texts = []
    for content in payload.get("content") or []:
        if isinstance(content, dict) and content.get("type") in ("input_text", "output_text"):
            text = content.get("text") or ""
            if text:
                texts.append(text)
    text = "\n".join(texts).strip()
    if not text:
        return None
    return role, text


def read_recent_session_messages(rollout: Path, limit: int) -> list[tuple[str, str]]:
    messages: list[tuple[str, str]] = []
    with rollout.open(encoding="utf-8", errors="replace") as file:
        for line in file:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "response_item":
                continue
            parsed = message_text(obj.get("payload") or {})
            if parsed:
                messages.append(parsed)
    return messages[-limit:]


def summarize_session_messages(messages: list[tuple[str, str]], session_id: str) -> str:
    if not messages:
        return f"Session {session_id[:8]}\nWaiting for Codex..."

    lines = [f"Session {session_id[:8]}"]
    for role, text in messages:
        body = compact_message_text(text)
        if not body:
            continue
        prefix = "U" if role == "user" else "A"
        lines.append(f"{prefix}: {body}")
    return "\n".join(lines)


def compact_message_text(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("<proposed_plan>"):
        for line in stripped.splitlines():
            clean = line.strip("# `")
            if clean and clean not in ("<proposed_plan>", "</proposed_plan>"):
                return clean
    for line in reversed(stripped.splitlines()):
        clean = line.strip()
        if not clean:
            continue
        if clean.startswith(("```", "<", "{", "}")):
            continue
        if clean.startswith(("#", "-", "*")):
            clean = clean.lstrip("#-* ").strip()
        if clean:
            return clean
    return " ".join(stripped.split())[:120]


def read_session_summary(args: argparse.Namespace) -> str:
    rollout = resolve_rollout_path(args.session_id, args.codex_state_db)
    messages = read_recent_session_messages(rollout, args.session_messages)
    return summarize_session_messages(messages, args.session_id)


def source_marker(args: argparse.Namespace) -> tuple[int, int] | None:
    if args.stdin:
        return None
    if args.session_id:
        rollout = resolve_rollout_path(args.session_id, args.codex_state_db)
        stat = rollout.stat()
        return stat.st_mtime_ns, stat.st_size
    feed = Path(args.feed)
    if not feed.exists():
        return None
    stat = feed.stat()
    return stat.st_mtime_ns, stat.st_size


def trim_line(line: str, width: int) -> str:
    clean = " ".join(line.strip().split())
    if len(clean) <= width:
        return clean
    if width <= 1:
        return clean[:width]
    return clean[: width - 1].rstrip() + "..."


def format_for_glasses(raw: str, *, title: str, max_chars: int, max_lines: int, line_width: int) -> str:
    body = textwrap.dedent(raw).strip()
    if not body:
        body = "Waiting for Codex..."

    available_lines = max(1, max_lines - 1)
    body_lines = [line for line in body.splitlines() if line.strip()]
    if not body_lines:
        body_lines = [body]

    selected = body_lines[-available_lines:]
    formatted = [trim_line(line, line_width) for line in selected]
    message = "\n".join([title, *formatted]).strip()

    if len(message) <= max_chars:
        return message

    budget = max(0, max_chars - len(title) - 1)
    tail = message.split("\n", 1)[1] if "\n" in message else ""
    if len(tail) > budget:
        tail = "..." + tail[-max(0, budget - 3) :]
    return "\n".join(part for part in [title, tail.strip()] if part).strip()


def send_with_retry(message: str, *, retry: bool) -> bool:
    while True:
        try:
            push_message(message)
            return True
        except SystemExit as exc:
            print(f"ROKID send failed: {exc}", file=sys.stderr)
            if not retry:
                return False
            time.sleep(RETRY_SECONDS)


def run_once(args: argparse.Namespace) -> int:
    raw = read_source(args)
    message = format_for_glasses(
        raw,
        title=args.title,
        max_chars=args.max_chars,
        max_lines=args.max_lines,
        line_width=args.line_width,
    )
    return 0 if send_with_retry(message, retry=False) else 1


def watch(args: argparse.Namespace) -> int:
    last_payload = None
    last_mtime = None
    target = f"session {args.session_id}" if args.session_id else args.feed
    print(f"Watching {target}; press Ctrl-C to stop.", file=sys.stderr)
    while True:
        try:
            marker = source_marker(args)
            if marker is not None:
                pass
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            marker = None
        if marker is not None:
            if marker != last_mtime:
                last_mtime = marker
                try:
                    raw = read_source(args)
                except SystemExit as exc:
                    print(exc, file=sys.stderr)
                    raw = ""
                message = format_for_glasses(
                    raw,
                    title=args.title,
                    max_chars=args.max_chars,
                    max_lines=args.max_lines,
                    line_width=args.line_width,
                )
                if message != last_payload:
                    if send_with_retry(message, retry=True):
                        last_payload = message
        time.sleep(args.interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror a compact Codex feed to Rokid Glasses.")
    parser.add_argument("--feed", default=DEFAULT_FEED, help="File to watch for status text")
    parser.add_argument("--interval", type=float, default=0.5, help="Polling interval in seconds")
    parser.add_argument("--title", default="Codex", help="First line shown on the glasses")
    parser.add_argument("--max-chars", type=int, default=220, help="Maximum total display characters")
    parser.add_argument("--max-lines", type=int, default=5, help="Maximum display lines including title")
    parser.add_argument("--line-width", type=int, default=32, help="Approximate maximum characters per line")
    parser.add_argument("--once", action="store_true", help="Send once and exit")
    parser.add_argument("--stdin", action="store_true", help="Read one message from stdin")
    parser.add_argument("--session-id", help="Watch a Codex Desktop session rollout by thread id")
    parser.add_argument("--codex-state-db", default=DEFAULT_CODEX_STATE_DB, help="Codex Desktop state SQLite DB")
    parser.add_argument("--session-messages", type=int, default=4, help="Recent user/assistant messages to summarize")
    args = parser.parse_args()

    if args.stdin or args.once:
        raise SystemExit(run_once(args))
    raise SystemExit(watch(args))


if __name__ == "__main__":
    main()
