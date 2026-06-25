#!/usr/bin/env python3
"""Watch rekordbox screen highlight row and mirror the selected crate row to Rokid."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from dj_hud_common import (
    REKORDBOX_CRATE,
    build_browser_hud,
    build_raw_rows_hud,
    load_tracks,
    resolve_crate,
    send_to_rokid,
)
from rekordbox_highlight_common import (
    DEFAULT_CONFIG,
    ScreenRegion,
    capture_screen,
    detect_highlight,
    load_region,
    save_debug_image,
)


def override_region(region: ScreenRegion, args: argparse.Namespace) -> ScreenRegion:
    return ScreenRegion(
        x=region.x,
        y=region.y,
        width=region.width,
        height=region.height,
        row_height=args.row_height if args.row_height else region.row_height,
        top_index=(args.top_index - 1) if args.top_index else region.top_index,
        highlight_mode=args.highlight_mode or region.highlight_mode,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror rekordbox screen highlight selection to Rokid.")
    parser.add_argument("--crate", type=Path, default=REKORDBOX_CRATE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--interval", type=float, default=0.3)
    parser.add_argument("--top-index", type=int, help="Override top visible crate index, 1-based")
    parser.add_argument("--row-height", type=int, help="Override row height in pixels")
    parser.add_argument("--highlight-mode", choices=("auto", "blue", "bright", "dark"))
    parser.add_argument("--debug-image", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tracks = load_tracks(resolve_crate(args.crate))
    region = override_region(load_region(args.config), args)
    last_key = None
    print("Watching rekordbox screen highlight. Press Ctrl-C to stop.")

    while True:
        image = capture_screen()
        result = detect_highlight(image, region)
        if result is None:
            time.sleep(args.interval)
            continue

        raw_index = result.absolute_index
        if args.debug_image:
            save_debug_image(image, region, result, args.debug_image)
        if 0 <= raw_index < len(tracks):
            hud = build_browser_hud(raw_index, tracks)
            track = tracks[raw_index]
            status = f"{track.artist} - {track.title}"
        else:
            rows = [f"crate row {row + 1}" for row in range(max(0, raw_index - 2), raw_index + 3)]
            selected = min(2, max(0, raw_index))
            hud = build_raw_rows_hud(rows, selected)
            status = "crate row outside loaded crate"
        key = (raw_index, hud)
        if key != last_key:
            send_to_rokid(hud, args.dry_run)
            print(
                f"row={result.visible_row} crate={raw_index + 1} score={result.score:.1f}: "
                f"{status}"
            )
            last_key = key
        time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
