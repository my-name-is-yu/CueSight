#!/usr/bin/env python3
"""Import a public Spotify embed playlist into the Rokid DJ crate format."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "rekordbox_crate.json"


def playlist_id(value: str) -> str:
    if "spotify:playlist:" in value:
        return value.rsplit(":", 1)[-1]
    match = re.search(r"playlist/([A-Za-z0-9]+)", value)
    if match:
        return match.group(1)
    return value.strip()


def fetch_embed(pid: str) -> dict:
    url = f"https://open.spotify.com/embed/playlist/{pid}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', text)
    if not match:
        raise SystemExit("Could not find Spotify embed data.")
    return json.loads(html.unescape(match.group(1)))


def parse_tracks(data: dict) -> list[dict[str, object]]:
    entity = data["props"]["pageProps"]["state"]["data"]["entity"]
    track_list = entity.get("trackList", [])
    tracks = []
    for index, item in enumerate(track_list, start=1):
        title = str(item.get("title") or f"Track {index}")
        artist = str(item.get("subtitle") or "Unknown Artist")
        uri = str(item.get("uri") or f"spotify:{index}")
        tracks.append(
            {
                "id": uri,
                "title": title,
                "artist": artist,
                "bpm": 0.0,
                "key": "",
                "energy": 5,
                "rating": 0,
                "color": "",
                "comment": "spotify",
                "playlist": str(entity.get("title") or "Spotify Playlist"),
                "order": index,
                "tags": ["spotify"],
            }
        )
    if not tracks:
        raise SystemExit("No tracks found in Spotify embed data.")
    return tracks


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a public Spotify playlist into crate JSON.")
    parser.add_argument("playlist", help="Spotify playlist URL, URI, or id")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    data = fetch_embed(playlist_id(args.playlist))
    tracks = parse_tracks(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"tracks": tracks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(tracks)} tracks -> {args.output}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
