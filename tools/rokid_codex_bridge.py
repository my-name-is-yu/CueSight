#!/usr/bin/env python3
"""Send short Codex/status text to Rokid Glasses over ADB.

The companion Android app polls its internal app file:
  /data/user/0/dev.rokid.codexbridge/files/latest.txt
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path


PACKAGE = "dev.rokid.codexbridge"
REMOTE_FILE = "files/latest.txt"
ROOT = Path(__file__).resolve().parents[1]
PREVIEW_FILE = ROOT / "data" / "rokid_hud_preview.txt"


def run_adb(args: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    adb = shutil.which("adb")
    if not adb:
        raise SystemExit("adb not found. Install with: brew install android-platform-tools")

    return subprocess.run(
        [adb, *args],
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def require_device(serial: str | None = None) -> str:
    proc = run_adb(["devices", "-l"])
    devices = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1], line))

    ready = [device for device in devices if device[1] == "device"]
    if not ready:
        detail = proc.stdout.strip() or proc.stderr.strip() or "no ADB output"
        raise SystemExit(f"No authorized Rokid ADB device found.\n{detail}")
    if serial:
        for device in ready:
            if device[0] == serial:
                return device[0]
        detail = "\n".join(device[2] for device in ready)
        raise SystemExit(f"ADB device {serial!r} not found.\n{detail}")
    wifi_ready = [device for device in ready if ":" in device[0]]
    return (wifi_ready or ready)[0][0]


def push_message(body: str, serial: str | None = None) -> None:
    serial = require_device(serial)
    write = run_adb(
        [
            "-s",
            serial,
            "shell",
            f"run-as {PACKAGE} sh -c 'cd /data/user/0/{PACKAGE} && mkdir -p files && cat > {REMOTE_FILE}'",
        ],
        input_text=body.strip() + "\n",
    )
    if write.returncode != 0:
        raise SystemExit((write.stderr or write.stdout).strip())


def write_local_preview(body: str) -> None:
    PREVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_FILE.write_text(body.strip() + "\n", encoding="utf-8")


def read_input(args: argparse.Namespace) -> str:
    if args.message:
        return args.message
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --message, --file, or pipe text on stdin.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send text to the Rokid Codex Bridge app via ADB.")
    parser.add_argument("--title", default="Codex", help="Accepted for compatibility; not displayed")
    parser.add_argument("--message", help="Message body to send")
    parser.add_argument("--file", help="Read message body from a file")
    parser.add_argument("--serial", default=os.environ.get("ROKID_ADB_SERIAL"), help="ADB serial to use")
    parser.add_argument("--preview-only", action="store_true", help="Update the Mac preview without sending over ADB")
    args = parser.parse_args()

    message = textwrap.dedent(read_input(args)).strip()
    if not message:
        raise SystemExit("Message is empty.")
    write_local_preview(message)
    if not args.preview_only:
        push_message(message, serial=args.serial)


if __name__ == "__main__":
    main()
