#!/usr/bin/env python3
"""Run a short terminal demo for recording CueSight without Rokid hardware."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dj_hud_common import REKORDBOX_CRATE, build_browser_hud, load_tracks, resolve_crate


def clear() -> None:
    sys.stdout.write("\033[2J\033[H")


def print_frame(title: str, body: str) -> None:
    clear()
    print("CueSight - Rokid DJ HUD Demo")
    print("=" * 52)
    print(title)
    print("-" * 52)
    print(body)
    print("-" * 52)
    print("Desktop recording: Rokid hardware is not currently connected.")
    sys.stdout.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a short CueSight terminal demo for video recording.")
    parser.add_argument("--crate", type=Path, default=REKORDBOX_CRATE)
    parser.add_argument("--delay", type=float, default=2.0)
    args = parser.parse_args()

    tracks = load_tracks(resolve_crate(args.crate))
    sequence = [0, 1, 2, 3, 4, 5, 6]
    sequence = [index for index in sequence if index < len(tracks)]

    print_frame(
        "Problem",
        "DJs often look down at a laptop while browsing the next track.\n"
        "CueSight keeps the next cue in the performer's line of sight.",
    )
    time.sleep(args.delay)

    for index in sequence:
        print_frame(
            f"Live crate selection: track {index + 1} of {len(tracks)}",
            build_browser_hud(index, tracks),
        )
        time.sleep(args.delay)

    print_frame(
        "Why Rokid Glasses",
        "The HUD is hands-free, glanceable, and always near the DJ's line of sight.\n"
        "That makes it useful during live performance, not just on a laptop screen.",
    )
    time.sleep(args.delay)


if __name__ == "__main__":
    main()
