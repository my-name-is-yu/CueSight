#!/usr/bin/env python3
"""Show the latest Rokid HUD text on this Mac."""

from __future__ import annotations

import argparse
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREVIEW = ROOT / "data" / "rokid_hud_preview.txt"


def clear() -> None:
    print("\033[2J\033[H", end="")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview the latest Rokid HUD text in this terminal.")
    parser.add_argument("--file", type=Path, default=DEFAULT_PREVIEW)
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()

    last = None
    while True:
        if args.file.exists():
            text = args.file.read_text(encoding="utf-8").strip()
        else:
            text = "Waiting for CueSight HUD..."

        if text != last:
            clear()
            print(text)
            last = text
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
