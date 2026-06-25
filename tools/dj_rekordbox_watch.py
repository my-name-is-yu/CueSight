#!/usr/bin/env python3
"""Watch rekordbox browser selection and mirror it to the Rokid HUD."""

from __future__ import annotations

import argparse
import difflib
import sys
import time
from pathlib import Path

from dj_hud_common import (
    REKORDBOX_CRATE,
    Track,
    build_browser_hud,
    build_raw_rows_hud,
    display_name,
    load_tracks,
    resolve_crate,
    send_to_rokid,
)
from rekordbox_ax_probe import app_root, best_snapshot


def searchable(track: Track) -> str:
    return f"{track.artist} {track.title} {track.bpm:g} {track.key}".lower()


def match_track_index(text: str, tracks: list[Track]) -> int | None:
    needle = text.lower()
    best_index = None
    best_score = 0.0
    for index, track in enumerate(tracks):
        haystack = searchable(track)
        score = difflib.SequenceMatcher(None, needle, haystack).ratio()
        title = track.title.lower()
        artist = track.artist.lower()
        if title and title in needle:
            score += 0.35
        if artist and artist in needle:
            score += 0.25
        if score > best_score:
            best_score = score
            best_index = index
    if best_score >= 0.38:
        return best_index
    return None


def raw_window(rows: tuple[str, ...], selected_text: str, selected_index: int | None) -> tuple[list[str], int | None]:
    if selected_index is None:
        for index, row in enumerate(rows):
            if row == selected_text or selected_text in row or row in selected_text:
                selected_index = index
                break
    if selected_index is None:
        window = [selected_text, *rows[:4]]
        return window[:5], 0 if selected_text else None
    start = max(0, selected_index - 2)
    end = min(len(rows), start + 5)
    start = max(0, end - 5)
    return list(rows[start:end]), selected_index - start


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror rekordbox browser selection to Rokid.")
    parser.add_argument("--crate", type=Path, default=REKORDBOX_CRATE)
    parser.add_argument("--interval", type=float, default=0.5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tracks = load_tracks(resolve_crate(args.crate))
    root = app_root()
    last_hud = ""
    print("Watching rekordbox selection. Press Ctrl-C to stop.")

    while True:
        snapshot = best_snapshot(root)
        if snapshot is None or not snapshot.selected_text:
            time.sleep(args.interval)
            continue

        matched_index = match_track_index(snapshot.selected_text, tracks)
        if matched_index is not None:
            hud = build_browser_hud(matched_index, tracks)
            status = display_name(tracks[matched_index])
        else:
            rows, selected = raw_window(snapshot.rows, snapshot.selected_text, snapshot.selected_index)
            hud = build_raw_rows_hud(rows, selected)
            status = snapshot.selected_text[:80]

        if hud != last_hud:
            send_to_rokid(hud, args.dry_run)
            print(f"HUD updated: {status}")
            last_hud = hud
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
