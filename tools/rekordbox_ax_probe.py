#!/usr/bin/env python3
"""Probe rekordbox browser selection through macOS Accessibility."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass

import ApplicationServices
import AppKit


REKORDBOX_NAMES = ("rekordbox", "rekordbox 7", "rekordbox 6")
TEXT_ATTRS = ("AXTitle", "AXValue", "AXDescription", "AXHelp", "AXSelectedText")
CHILD_ATTRS = ("AXChildren", "AXRows", "AXVisibleRows", "AXColumns")
SELECTED_ATTRS = ("AXSelectedRows", "AXSelectedChildren", "AXFocusedUIElement")


@dataclass(frozen=True)
class AXSnapshot:
    selected_text: str
    rows: tuple[str, ...]
    selected_index: int | None


def ensure_trusted() -> None:
    trusted = ApplicationServices.AXIsProcessTrusted()
    if trusted:
        return
    message = (
        "macOS Accessibility permission is required.\n"
        "Open System Settings > Privacy & Security > Accessibility and allow Terminal/Codex/Python, "
        "then restart this command."
    )
    raise SystemExit(message)


def get_rekordbox_app():
    workspace = AppKit.NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        name = str(app.localizedName() or "")
        bundle = str(app.bundleIdentifier() or "")
        if "rekordbox" in name.lower() or "rekordbox" in bundle.lower():
            return app
    names = ", ".join(REKORDBOX_NAMES)
    raise SystemExit(f"rekordbox process not found. Start rekordbox first. Looked for: {names}")


def ax_attr(element, attr: str):
    err, value = ApplicationServices.AXUIElementCopyAttributeValue(element, attr, None)
    if err == 0:
        return value
    return None


def ax_attrs(element) -> list[str]:
    err, attrs = ApplicationServices.AXUIElementCopyAttributeNames(element, None)
    if err == 0 and attrs:
        return list(attrs)
    return []


def children_of(element) -> list:
    children = []
    for attr in CHILD_ATTRS:
        value = ax_attr(element, attr)
        if isinstance(value, (list, tuple)):
            children.extend(value)
    # Preserve order while removing duplicates by object id.
    seen = set()
    unique = []
    for child in children:
        key = id(child)
        if key not in seen:
            seen.add(key)
            unique.append(child)
    return unique


def role_of(element) -> str:
    return str(ax_attr(element, "AXRole") or "")


def text_of(element, depth: int = 0, max_depth: int = 4) -> str:
    parts = []
    for attr in TEXT_ATTRS:
        value = ax_attr(element, attr)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
        elif value is not None and not isinstance(value, (list, tuple)):
            text = str(value).strip()
            if text and not text.startswith("<AXUIElement"):
                parts.append(text)
    if depth < max_depth:
        for child in children_of(element):
            child_text = text_of(child, depth + 1, max_depth)
            if child_text:
                parts.append(child_text)
    return normalize_text(" ".join(parts))


def normalize_text(value: str) -> str:
    return " ".join(value.replace("\n", " ").split())


def selected_elements(element) -> list:
    results = []
    for attr in SELECTED_ATTRS:
        value = ax_attr(element, attr)
        if isinstance(value, (list, tuple)):
            results.extend(value)
        elif value is not None and "AXUIElement" in str(type(value)):
            results.append(value)
    return results


def find_tables(element, depth: int = 0, max_depth: int = 9) -> list:
    if depth > max_depth:
        return []
    role = role_of(element)
    found = []
    if role in {"AXTable", "AXOutline", "AXList", "AXBrowser"}:
        found.append(element)
    for child in children_of(element):
        found.extend(find_tables(child, depth + 1, max_depth))
    return found


def snapshot_for_table(table) -> AXSnapshot | None:
    rows = ax_attr(table, "AXRows") or ax_attr(table, "AXVisibleRows") or children_of(table)
    if not isinstance(rows, (list, tuple)) or not rows:
        return None
    row_texts = [text_of(row, max_depth=3) for row in rows]
    row_texts = [text for text in row_texts if useful_row(text)]
    if not row_texts:
        return None

    selected = selected_elements(table)
    selected_text = ""
    selected_index = None
    if selected:
        selected_text = text_of(selected[0], max_depth=3)
        for index, row in enumerate(rows):
            if row == selected[0]:
                selected_index = index
                break

    if not selected_text:
        focused = ax_attr(table, "AXFocusedUIElement")
        if focused is not None:
            selected_text = text_of(focused, max_depth=3)

    if not selected_text and row_texts:
        selected_text = row_texts[0]
        selected_index = 0

    return AXSnapshot(selected_text=selected_text, rows=tuple(row_texts), selected_index=selected_index)


def useful_row(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    noisy = ("column", "scroll", "button", "search", "playlist", "collection")
    return not (len(text) < 2 or any(lowered == word for word in noisy))


def best_snapshot(root) -> AXSnapshot | None:
    best = None
    best_score = -1
    for table in find_tables(root):
        snapshot = snapshot_for_table(table)
        if snapshot is None:
            continue
        score = len(snapshot.rows)
        if snapshot.selected_text:
            score += 10
        if score > best_score:
            best = snapshot
            best_score = score
    return best


def app_root():
    ensure_trusted()
    app = get_rekordbox_app()
    return ApplicationServices.AXUIElementCreateApplication(app.processIdentifier())


def dump_tree(element, depth: int = 0, max_depth: int = 6) -> None:
    if depth > max_depth:
        return
    role = role_of(element)
    text = text_of(element, max_depth=1)
    attrs = ",".join(ax_attrs(element)[:8])
    indent = "  " * depth
    print(f"{indent}{role} text={text[:100]!r} attrs={attrs}")
    for child in children_of(element)[:80]:
        dump_tree(child, depth + 1, max_depth)


def print_snapshot(snapshot: AXSnapshot | None) -> None:
    if snapshot is None:
        print("No table/list selection found.")
        return
    print(f"selected_index={snapshot.selected_index} selected={snapshot.selected_text!r}")
    for index, row in enumerate(snapshot.rows[:12]):
        marker = ">" if snapshot.selected_index == index else " "
        print(f"{marker} {index:02d} {row}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe rekordbox Accessibility selection.")
    parser.add_argument("--dump", action="store_true", help="Dump the rekordbox Accessibility tree.")
    parser.add_argument("--watch", action="store_true", help="Print selection changes repeatedly.")
    parser.add_argument("--interval", type=float, default=0.5)
    args = parser.parse_args()

    root = app_root()
    if args.dump:
        dump_tree(root)
        return

    last = None
    while True:
        snapshot = best_snapshot(root)
        key = snapshot.selected_text if snapshot else ""
        if key != last:
            print_snapshot(snapshot)
            last = key
        if not args.watch:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
