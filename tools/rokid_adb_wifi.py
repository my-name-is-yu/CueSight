#!/usr/bin/env python3
"""Switch the Rokid ADB connection from USB to Wi-Fi."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys


DEFAULT_PORT = 5555


def run_adb(args: list[str]) -> subprocess.CompletedProcess[str]:
    adb = shutil.which("adb")
    if not adb:
        raise SystemExit("adb not found. Install with: brew install android-platform-tools")
    return subprocess.run(
        [adb, *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def adb(args: list[str]) -> str:
    proc = run_adb(args)
    if proc.returncode != 0:
        raise SystemExit((proc.stderr or proc.stdout).strip())
    return proc.stdout.strip()


def ready_devices() -> list[str]:
    output = adb(["devices", "-l"])
    devices: list[str] = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            devices.append(parts[0])
    return devices


def choose_usb_device() -> str:
    devices = ready_devices()
    usb_devices = [device for device in devices if ":" not in device]
    if not usb_devices:
        raise SystemExit(
            "No USB ADB device found. Connect Rokid by USB first, then run this again.\n"
            + adb(["devices", "-l"])
        )
    return usb_devices[0]


def get_wlan_ip(serial: str) -> str:
    output = adb(["-s", serial, "shell", "ip", "-f", "inet", "addr", "show", "wlan0"])
    match = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", output)
    if not match:
        raise SystemExit(
            "Rokid wlan0 has no IPv4 address. Connect Rokid to the same Wi-Fi as this Mac first.\n"
            f"wlan0 output:\n{output or '(empty)'}"
        )
    return match.group(1)


def connect_wifi(port: int) -> str:
    serial = choose_usb_device()
    ip = get_wlan_ip(serial)
    print(f"USB device: {serial}")
    print(f"Rokid Wi-Fi IP: {ip}")
    print(adb(["-s", serial, "tcpip", str(port)]))
    target = f"{ip}:{port}"
    print(adb(["connect", target]))
    return target


def disconnect_wifi(target: str) -> None:
    print(adb(["disconnect", target]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Enable or manage Rokid ADB over Wi-Fi.")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--disconnect", metavar="HOST:PORT", help="Disconnect an existing wireless ADB target")
    parser.add_argument("--devices", action="store_true", help="Print current adb devices and exit")
    args = parser.parse_args()

    if args.devices:
        print(adb(["devices", "-l"]))
        return
    if args.disconnect:
        disconnect_wifi(args.disconnect)
        return

    target = connect_wifi(args.port)
    print()
    print("Wireless ADB is ready.")
    print(f"You can now unplug USB and keep using: {target}")
    print("Test with:")
    print("  python3 tools/rokid_codex_bridge.py --message \"wireless test\"")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
