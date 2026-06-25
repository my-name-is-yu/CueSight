#!/usr/bin/env python3
"""Pseudo-realtime DJ browser HUD driver for Rokid demo.

This consumes a normalized crate generated from rekordbox XML/CSV exports and
keeps the live loop simple: keyboard selection changes immediately update the
Rokid HUD with the selected track plus two rows above and below.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dj_hud_common import (
    REKORDBOX_CRATE,
    Track,
    build_browser_hud,
    load_tracks,
    resolve_crate,
    send_to_rokid,
)


def key_root(key: str) -> str:
    return key.strip().replace("m", "").replace("#", "s")


def key_score(a: Track, b: Track) -> int:
    if not a.key or not b.key:
        return 1
    if a.key == b.key:
        return 0
    if key_root(a.key) == key_root(b.key):
        return 1
    return 2


def bpm_delta(a: Track, b: Track) -> float:
    return abs(a.bpm - b.bpm)


def score_track(current: Track, candidate: Track, mode: str) -> tuple[float, str]:
    bpm = bpm_delta(current, candidate)
    key = key_score(current, candidate)
    energy_delta = candidate.energy - current.energy
    shared_tags = len(set(current.tags) & set(candidate.tags))

    if mode == "safe":
        score = bpm * 1.2 + key * 4 + abs(energy_delta) * 2 - shared_tags * 2
        reason = "keep groove"
    elif mode == "lift":
        target = 2
        score = bpm * 0.8 + key * 3 + abs(energy_delta - target) * 2 - shared_tags
        reason = "raise energy"
    elif mode == "wild":
        target = 3
        score = -abs(energy_delta) + max(0, 6 - bpm) * 0.2 + key - shared_tags
        if energy_delta >= target:
            score -= 4
        reason = "surprise switch"
    else:
        raise ValueError(mode)

    if mode in candidate.tags:
        score -= 5
    return score, reason


def pick_candidate(current: Track, tracks: list[Track], used: set[str], mode: str) -> tuple[Track, str]:
    pool = [track for track in tracks if track.id != current.id and track.id not in used]
    if not pool:
        pool = [track for track in tracks if track.id != current.id]
    ranked = sorted(pool, key=lambda track: score_track(current, track, mode)[0])
    choice = ranked[0]
    return choice, score_track(current, choice, mode)[1]


def build_candidate_hud(current: Track, tracks: list[Track], used: set[str]) -> tuple[str, dict[str, Track]]:
    safe, safe_reason = pick_candidate(current, tracks, used, "safe")
    lift, lift_reason = pick_candidate(current, tracks, used | {safe.id}, "lift")
    wild, wild_reason = pick_candidate(current, tracks, used | {safe.id, lift.id}, "wild")
    picks = {"1": safe, "2": lift, "3": wild, "safe": safe, "lift": lift, "wild": wild}

    text = "\n".join(
        [
            "STAY WITH THE CROWD",
            "",
            "NOW",
            f"{current.artist} - {current.title}",
            f"{current.bpm:g} / {current.key} / E{current.energy}",
            "",
            "1 SAFE",
            f"{safe.artist} - {safe.title}",
            f"{safe.bpm:g} / {safe.key} / {safe_reason}",
            "",
            "2 LIFT",
            f"{lift.artist} - {lift.title}",
            f"{lift.bpm:g} / {lift.key} / {lift_reason}",
            "",
            "3 WILD",
            f"{wild.artist} - {wild.title}",
            f"{wild.bpm:g} / {wild.key} / {wild_reason}",
        ]
    )
    return text, picks


def choose_initial(tracks: list[Track], query: str | None) -> Track:
    if not query:
        return tracks[0]
    needle = query.lower()
    for track in tracks:
        haystack = f"{track.artist} {track.title} {track.id}".lower()
        if needle in haystack:
            return track
    raise SystemExit(f"No track matched: {query}")


def print_help() -> None:
    print(
        "Commands: Enter/j/down = next | k/up = previous | number = jump | find <text> | list | q"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Drive the Rokid DJ HUD in pseudo realtime.")
    parser.add_argument("--crate", type=Path, default=REKORDBOX_CRATE)
    parser.add_argument("--current", help="Initial current track title/artist/id substring")
    parser.add_argument(
        "--display",
        choices=("browser", "candidates"),
        default="browser",
        help="browser shows the selected track plus two above/below; candidates is a secondary fallback.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print HUD text instead of sending to Rokid")
    args = parser.parse_args()

    crate = resolve_crate(args.crate)
    tracks = load_tracks(crate)
    current = choose_initial(tracks, args.current)
    selected_index = tracks.index(current)
    used = {current.id}
    print_help()

    while True:
        if args.display == "browser":
            hud = build_browser_hud(selected_index, tracks)
            picks = {}
        else:
            hud, picks = build_candidate_hud(current, tracks, used)
        send_to_rokid(hud, args.dry_run)
        selected = tracks[selected_index]
        try:
            command = input(f"\nSELECTED {selected.artist} - {selected.title} > ").strip().lower()
        except EOFError:
            break

        if command in {"q", "quit", "exit"}:
            break
        if command in picks:
            current = picks[command]
            selected_index = tracks.index(current)
            used.add(current.id)
            continue
        if command in {"j", "down", "n", ""}:
            selected_index = min(len(tracks) - 1, selected_index + 1)
            current = tracks[selected_index]
            used.add(current.id)
            continue
        if command in {"k", "up", "p"}:
            selected_index = max(0, selected_index - 1)
            current = tracks[selected_index]
            used.add(current.id)
            continue
        if command == "list":
            for idx, track in enumerate(tracks, start=1):
                print(f"{idx:02d}. {track.artist} - {track.title} ({track.bpm:g}/{track.key}/E{track.energy})")
            continue
        if command.startswith("find "):
            needle = command[5:].strip()
            matches = [
                track for track in tracks
                if needle in f"{track.artist} {track.title} {track.id}".lower()
            ]
            for idx, track in enumerate(matches, start=1):
                print(f"{idx:02d}. {track.artist} - {track.title} ({track.bpm:g}/{track.key}/E{track.energy})")
            if matches:
                pick = input("Use number or blank to cancel > ").strip()
                if pick.isdigit() and 1 <= int(pick) <= len(matches):
                    current = matches[int(pick) - 1]
                    selected_index = tracks.index(current)
                    used.add(current.id)
            continue
        if command.isdigit() and 1 <= int(command) <= len(tracks):
            selected_index = int(command) - 1
            current = tracks[selected_index]
            used.add(current.id)
            continue

        print_help()


if __name__ == "__main__":
    main()
