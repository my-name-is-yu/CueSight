#!/usr/bin/env python3
"""Shared crate and HUD helpers for the Rokid DJ demo."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CRATE = ROOT / "data" / "demo_crate.json"
REKORDBOX_CRATE = ROOT / "data" / "rekordbox_crate.json"
BRIDGE = ROOT / "tools" / "rokid_codex_bridge.py"
PREVIEW_FILE = ROOT / "data" / "rokid_hud_preview.txt"
MAX_TITLE_CHARS = 24


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    bpm: float
    key: str
    energy: int
    tags: tuple[str, ...]
    rating: int = 0
    color: str = ""
    comment: str = ""
    playlist: str = ""


def load_tracks(path: Path) -> list[Track]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    tracks = []
    for item in raw.get("tracks", []):
        tracks.append(
            Track(
                id=str(item["id"]),
                title=str(item["title"]),
                artist=str(item["artist"]),
                bpm=float(item.get("bpm", 0.0) or 0.0),
                key=str(item.get("key", "")),
                energy=int(item.get("energy", 5) or 5),
                tags=tuple(str(tag).lower() for tag in item.get("tags", [])),
                rating=int(item.get("rating", 0) or 0),
                color=str(item.get("color", "")),
                comment=str(item.get("comment", "")),
                playlist=str(item.get("playlist", "")),
            )
        )
    if not tracks:
        raise SystemExit(f"No tracks found in {path}")
    return tracks


def resolve_crate(path: Path) -> Path:
    if path == REKORDBOX_CRATE and not path.exists():
        print(f"Using fallback demo crate: {DEFAULT_CRATE}")
        return DEFAULT_CRATE
    return path


def build_browser_hud(selected_index: int, tracks: list[Track]) -> str:
    start = max(0, selected_index - 2)
    end = min(len(tracks), start + 5)
    start = max(0, end - 5)
    visible = tracks[start:end]

    lines = ["REKORDBOX CRATE", ""]
    for offset, track in enumerate(visible, start=start):
        prefix = ">" if offset == selected_index else " "
        lines.append(f"{prefix} {display_track_line(track)}")
    return "\n".join(lines)


def build_raw_rows_hud(rows: list[str], selected_index: int | None = None) -> str:
    lines = ["REKORDBOX CRATE", ""]
    for index, row in enumerate(rows[:5]):
        prefix = ">" if selected_index == index else " "
        lines.append(f"{prefix} {ellipsize(row, MAX_TITLE_CHARS)} / -- / --")
    return "\n".join(lines)


def display_track_line(track: Track) -> str:
    return f"{ellipsize(track.title, MAX_TITLE_CHARS)} / {display_bpm(track)} / {track.key or '--'}"


def display_name(track: Track) -> str:
    name = f"{track.artist} - {track.title}".strip(" -")
    return ellipsize(name, MAX_TITLE_CHARS)


def display_bpm(track: Track) -> str:
    return f"{track.bpm:g}" if track.bpm > 0 else "--"


def ellipsize(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1] + "…"


def send_to_rokid(text: str, dry_run: bool = False) -> None:
    write_local_preview(text)
    if dry_run:
        print("\n" + "=" * 48)
        print(text)
        print("=" * 48)
        return
    proc = subprocess.run(
        [sys.executable, str(BRIDGE), "--message", text],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit((proc.stderr or proc.stdout).strip())


def write_local_preview(text: str) -> None:
    PREVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_FILE.write_text(text.strip() + "\n", encoding="utf-8")
