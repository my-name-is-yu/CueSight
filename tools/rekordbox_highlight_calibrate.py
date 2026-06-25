#!/usr/bin/env python3
"""Calibrate the rekordbox browser region for highlight tracking."""

from __future__ import annotations

import argparse
from pathlib import Path

from dj_hud_common import REKORDBOX_CRATE, load_tracks, resolve_crate
from rekordbox_highlight_common import (
    DEFAULT_CONFIG,
    ScreenRegion,
    capture_screen,
    detect_highlight,
    save_debug_image,
    save_region,
)


def ask_int(label: str, default: int | None = None) -> int:
    prompt = f"{label}"
    if default is not None:
        prompt += f" [{default}]"
    prompt += ": "
    value = input(prompt).strip()
    if not value and default is not None:
        return default
    return int(value)


def ask_mode(default: str = "auto") -> str:
    value = input(f"highlight_mode auto/blue/bright/dark [{default}]: ").strip()
    return value or default


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate rekordbox screen region for highlight tracking.")
    parser.add_argument("--crate", type=Path, default=REKORDBOX_CRATE)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--debug-image", type=Path, default=Path("/tmp/rekordbox_highlight_debug.png"))
    args = parser.parse_args()

    tracks = load_tracks(resolve_crate(args.crate))
    image = capture_screen()
    print(f"Screenshot size: {image.width} x {image.height}")
    print("Enter the rekordbox track-list rectangle in screen pixels.")
    print("Tip: use macOS Screenshot selection coordinates or estimate, then adjust if needed.")
    x = ask_int("x")
    y = ask_int("y")
    width = ask_int("width")
    height = ask_int("height")
    row_height = ask_int("row_height", 24)
    top_index = ask_int("top visible crate index, 1-based", 1) - 1
    mode = ask_mode()

    region = ScreenRegion(
        x=x,
        y=y,
        width=width,
        height=height,
        row_height=row_height,
        top_index=top_index,
        highlight_mode=mode,
    )
    result = detect_highlight(image, region)
    save_region(region, args.output)
    print(f"Saved config: {args.output}")
    if result is None:
        print("No highlight detected. Try another region/mode/row_height.")
        return

    save_debug_image(image, region, result, args.debug_image)
    absolute = min(max(result.absolute_index, 0), len(tracks) - 1)
    track = tracks[absolute]
    print(
        f"Detected visible row {result.visible_row}, crate index {absolute + 1}, "
        f"score {result.score:.1f}: {track.artist} - {track.title}"
    )
    print(f"Debug image: {args.debug_image}")


if __name__ == "__main__":
    main()
