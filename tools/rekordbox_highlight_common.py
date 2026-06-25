#!/usr/bin/env python3
"""Screen capture and highlight detection helpers for rekordbox browser rows."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "data" / "rekordbox_screen_region.json"
SCREENSHOT = Path("/tmp/rokid_rekordbox.png")


@dataclass(frozen=True)
class ScreenRegion:
    x: int
    y: int
    width: int
    height: int
    row_height: int
    top_index: int
    highlight_mode: str = "auto"


@dataclass(frozen=True)
class HighlightResult:
    visible_row: int
    score: float
    row_count: int
    absolute_index: int


def capture_screen(path: Path = SCREENSHOT) -> Image.Image:
    proc = subprocess.run(
        ["/usr/sbin/screencapture", "-x", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip() or "screencapture failed"
        raise SystemExit(
            f"{detail}\n"
            "Run this from a normal Terminal in the active desktop session and grant Screen Recording "
            "permission to Terminal/Codex/Python."
        )
    image = Image.open(path).convert("RGB")
    arr = np.asarray(image)
    if arr.size == 0 or float(arr.mean()) < 1.0:
        raise SystemExit(
            "Screenshot is empty or black. Grant Screen Recording permission to Terminal/Codex/Python."
        )
    return image


def load_region(path: Path = DEFAULT_CONFIG) -> ScreenRegion:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return ScreenRegion(
        x=int(raw["x"]),
        y=int(raw["y"]),
        width=int(raw["width"]),
        height=int(raw["height"]),
        row_height=int(raw["row_height"]),
        top_index=int(raw["top_index"]),
        highlight_mode=str(raw.get("highlight_mode", "auto")),
    )


def save_region(region: ScreenRegion, path: Path = DEFAULT_CONFIG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(region), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def crop_region(image: Image.Image, region: ScreenRegion) -> Image.Image:
    return image.crop((region.x, region.y, region.x + region.width, region.y + region.height))


def detect_highlight(image: Image.Image, region: ScreenRegion) -> HighlightResult | None:
    crop = crop_region(image, region)
    arr = np.asarray(crop).astype(np.float32)
    if arr.ndim != 3 or arr.shape[0] < region.row_height:
        return None

    row_count = max(1, int(region.height / region.row_height))
    scores = []
    global_mean = arr.mean(axis=(0, 1))
    for row in range(row_count):
        y0 = row * region.row_height
        y1 = min(arr.shape[0], y0 + region.row_height)
        band = arr[y0:y1]
        if band.size == 0:
            continue
        mean_rgb = band.mean(axis=(0, 1))
        max_rgb = band.max(axis=(0, 1))
        min_rgb = band.min(axis=(0, 1))
        brightness = float(mean_rgb.mean())
        contrast = float(np.linalg.norm(mean_rgb - global_mean))
        saturation = float(max_rgb.max() - min_rgb.min())
        blue_bias = float(mean_rgb[2] - ((mean_rgb[0] + mean_rgb[1]) / 2.0))
        if region.highlight_mode == "bright":
            score = brightness + contrast * 0.5
        elif region.highlight_mode == "blue":
            score = blue_bias * 2.0 + contrast + saturation * 0.15
        elif region.highlight_mode == "dark":
            score = (255.0 - brightness) + contrast * 0.5
        else:
            score = contrast + abs(blue_bias) * 1.2 + saturation * 0.1
        scores.append((row, score))

    if not scores:
        return None
    visible_row, score = max(scores, key=lambda item: item[1])
    if score < 3.0:
        return None
    absolute_index = region.top_index + visible_row
    return HighlightResult(
        visible_row=visible_row,
        score=float(score),
        row_count=row_count,
        absolute_index=absolute_index,
    )


def save_debug_image(image: Image.Image, region: ScreenRegion, result: HighlightResult, output: Path) -> None:
    debug = image.copy()
    draw = ImageDraw.Draw(debug)
    x0 = region.x
    y0 = region.y + result.visible_row * region.row_height
    x1 = region.x + region.width
    y1 = y0 + region.row_height
    draw.rectangle((region.x, region.y, region.x + region.width, region.y + region.height), outline="yellow", width=2)
    draw.rectangle((x0, y0, x1, y1), outline="red", width=4)
    output.parent.mkdir(parents=True, exist_ok=True)
    debug.save(output)
