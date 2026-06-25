#!/usr/bin/env python3
"""Convert rekordbox XML or CSV exports into the demo crate JSON format."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "rekordbox_crate.json"


def clean(value: object | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def number(value: object | None, default: float = 0.0) -> float:
    text = clean(value)
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        match = re.search(r"\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else default


def integer(value: object | None, default: int = 5) -> int:
    try:
        return int(round(number(value, default)))
    except ValueError:
        return default


def slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return text or "track"


def split_tags(*values: object | None) -> list[str]:
    tags: list[str] = []
    for value in values:
        for part in re.split(r"[,;/#\s]+", clean(value).lower()):
            if part and part not in tags:
                tags.append(part)
    return tags


def location_name(location: str) -> str:
    if not location:
        return ""
    parsed = urlparse(location)
    path = unquote(parsed.path if parsed.scheme else location)
    return Path(path).stem


def track_from_mapping(item: dict[str, object], fallback_id: str) -> dict[str, object]:
    title = first(item, "title", "name", "track", "track title") or location_name(clean(first(item, "location", "file", "path")))
    artist = first(item, "artist", "album artist", "creator")
    bpm = number(first(item, "bpm", "averagebpm", "average bpm", "tempo"), 0.0)
    key = first(item, "key", "tonality", "camelot")
    rating = integer(first(item, "rating"), 0)
    color = first(item, "color", "colour")
    comment = first(item, "comment", "comments")
    playlist = first(item, "playlist", "playlist name")
    order = integer(first(item, "order", "track number", "#"), 0)
    energy = integer(first(item, "energy"), 5)
    if energy == 5 and rating:
        energy = min(10, max(1, rating * 2))

    ident = clean(first(item, "id", "trackid", "track id")) or f"{slug(artist)}-{slug(title)}" or fallback_id
    return {
        "id": ident,
        "title": title or fallback_id,
        "artist": artist or "Unknown Artist",
        "bpm": bpm,
        "key": key,
        "energy": energy,
        "rating": rating,
        "color": color,
        "comment": comment,
        "playlist": playlist,
        "order": order,
        "tags": split_tags(color, comment, playlist),
    }


def first(item: dict[str, object], *names: str) -> str:
    normalized = {normalize_key(key): value for key, value in item.items()}
    for name in names:
        value = normalized.get(normalize_key(name))
        if clean(value):
            return clean(value)
    return ""


def normalize_key(key: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(key).lower())


def parse_csv(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return [track_from_mapping(dict(row), f"track-{idx}") for idx, row in enumerate(rows, start=1)]


def parse_xml(path: Path, playlist_name: str | None) -> list[dict[str, object]]:
    root = ET.parse(path).getroot()
    collection = root.find("COLLECTION")
    if collection is None:
        raise SystemExit("Invalid rekordbox XML: COLLECTION node not found.")

    by_id: dict[str, dict[str, object]] = {}
    for idx, node in enumerate(collection.findall("TRACK"), start=1):
        attrs = dict(node.attrib)
        attrs["id"] = attrs.get("TrackID", "")
        attrs["title"] = attrs.get("Name", "")
        attrs["artist"] = attrs.get("Artist", "")
        attrs["bpm"] = attrs.get("AverageBpm") or attrs.get("BPM", "")
        attrs["key"] = attrs.get("Tonality", "")
        attrs["color"] = attrs.get("Colour", "")
        attrs["comment"] = attrs.get("Comments", "")
        attrs["location"] = attrs.get("Location", "")
        by_id[clean(attrs.get("TrackID"))] = track_from_mapping(attrs, f"track-{idx}")

    ordered_ids, playlist_for_track = playlist_order(root, playlist_name)
    if ordered_ids:
        tracks = []
        for order, track_id in enumerate(ordered_ids, start=1):
            track = by_id.get(track_id)
            if not track:
                continue
            copy = dict(track)
            copy["playlist"] = playlist_for_track.get(track_id, playlist_name or "")
            copy["order"] = order
            tracks.append(copy)
        return tracks

    return list(by_id.values())


def playlist_order(root: ET.Element, wanted: str | None) -> tuple[list[str], dict[str, str]]:
    playlists = root.find("PLAYLISTS")
    if playlists is None:
        return [], {}

    ordered: list[str] = []
    playlist_for_track: dict[str, str] = {}

    def visit(node: ET.Element, path: list[str]) -> None:
        name = clean(node.attrib.get("Name"))
        next_path = [*path, name] if name and name != "ROOT" else path
        children = list(node)
        track_nodes = [child for child in children if child.tag == "TRACK"]
        full_name = " / ".join(next_path)
        if track_nodes and (not wanted or wanted.lower() in full_name.lower() or wanted.lower() == name.lower()):
            for track_node in track_nodes:
                track_id = clean(track_node.attrib.get("Key"))
                if track_id:
                    ordered.append(track_id)
                    playlist_for_track[track_id] = full_name
        for child in children:
            if child.tag == "NODE":
                visit(child, next_path)

    for child in playlists:
        if child.tag == "NODE":
            visit(child, [])
    return ordered, playlist_for_track


def write_crate(tracks: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"tracks": tracks}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import rekordbox XML/CSV exports into data/rekordbox_crate.json.")
    parser.add_argument("input", type=Path, help="rekordbox XML or CSV export")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--playlist", help="For XML exports, import only a matching playlist path/name")
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input not found: {args.input}")

    suffix = args.input.suffix.lower()
    if suffix == ".xml":
        tracks = parse_xml(args.input, args.playlist)
    elif suffix == ".csv":
        tracks = parse_csv(args.input)
    else:
        raise SystemExit("Input must be .xml or .csv")

    if not tracks:
        raise SystemExit("No tracks were imported.")

    write_crate(tracks, args.output)
    print(f"Imported {len(tracks)} tracks -> {args.output}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
