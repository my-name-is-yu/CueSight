#!/usr/bin/env python3
"""Mirror DDJ-400 browse MIDI movements to the Rokid DJ HUD."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dj_hud_common import REKORDBOX_CRATE, build_browser_hud, load_tracks, resolve_crate, send_to_rokid


ROOT = Path(__file__).resolve().parents[1]
MIDI_PROBE = ROOT / "tools" / "midi_probe.swift"


def relative_delta(value: int) -> int:
    if value in {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 63}:
        return 1
    if value in {65, 126, 127, 125, 124, 123, 122, 121, 120}:
        return -1
    if value > 64:
        return -1
    if value > 0:
        return 1
    return 0


def event_key(event: dict[str, object]) -> str | None:
    if event.get("event") != "cc":
        return None
    return f"{event.get('channel')}:{event.get('control')}"


def parse_control(value: str | None) -> str | None:
    if not value:
        return None
    if ":" not in value:
        raise SystemExit("--control must be formatted as channel:control, for example 1:64")
    channel, control = value.split(":", 1)
    return f"{int(channel)}:{int(control)}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch DDJ-400 MIDI browse movements and update Rokid HUD.")
    parser.add_argument("--crate", type=Path, default=REKORDBOX_CRATE)
    parser.add_argument("--start", type=int, default=1, help="1-based starting track index matching rekordbox selection")
    parser.add_argument("--control", help="Fixed CC mapping as channel:control. If omitted, first relative CC is learned.")
    parser.add_argument("--reverse", action="store_true", help="Reverse browse direction")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tracks = load_tracks(resolve_crate(args.crate))
    selected = min(max(args.start - 1, 0), len(tracks) - 1)
    locked_control = parse_control(args.control)
    last_hud = ""

    env = dict(os.environ)
    env.setdefault("CLANG_MODULE_CACHE_PATH", "/tmp/rokid-clang-cache")
    proc = subprocess.Popen(
        ["swift", str(MIDI_PROBE)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=1,
        env=env,
    )
    assert proc.stdout is not None

    print("Watching DDJ MIDI. Turn the rekordbox browse knob once if no control is locked.")
    try:
        while True:
            line = proc.stdout.readline()
            if not line:
                err = proc.stderr.read() if proc.stderr else ""
                raise SystemExit(err or "MIDI probe stopped.")
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(line.rstrip())
                continue

            if event.get("event") == "source":
                print(f"MIDI source {event.get('index')}: {event.get('name')}")
                continue

            key = event_key(event)
            if not key:
                continue
            value = int(event.get("value", 0))
            delta = relative_delta(value)
            if delta == 0:
                continue
            if locked_control is None:
                locked_control = key
                print(f"Learned browse CC: {locked_control}. Use --control {locked_control} next time.")
            if key != locked_control:
                continue
            if args.reverse:
                delta *= -1

            selected = min(max(selected + delta, 0), len(tracks) - 1)
            hud = build_browser_hud(selected, tracks)
            if hud != last_hud:
                send_to_rokid(hud, args.dry_run)
                track = tracks[selected]
                print(f"{selected + 1:03d}: {track.artist} - {track.title}")
                last_hud = hud
    except KeyboardInterrupt:
        proc.terminate()
        sys.exit(0)


if __name__ == "__main__":
    main()
