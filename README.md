# Rokid DJ 5-Line HUD Demo

This demo shows a rekordbox-derived crate on Rokid as a 5-line browser HUD:
the selected track plus two tracks above and below it.

## 1. Export From rekordbox

Export your rekordbox library or playlist as XML or CSV. Put the file anywhere
on this machine.

## 2. Import The Crate

```bash
python3 tools/import_rekordbox_crate.py path/to/rekordbox.xml
```

For a specific XML playlist:

```bash
python3 tools/import_rekordbox_crate.py path/to/rekordbox.xml --playlist "Main Set"
```

For CSV:

```bash
python3 tools/import_rekordbox_crate.py path/to/playlist.csv
```

The importer writes `data/rekordbox_crate.json`.

## 3. Start The Rokid App

Install and open the Android app on the Rokid device. Confirm ADB sees it:

```bash
adb devices -l
```

Optional bridge test:

```bash
python3 tools/rokid_codex_bridge.py --message "REKORDBOX CRATE"
```

Optional wireless ADB setup:

1. Connect Rokid by USB.
2. Connect Rokid to the same Wi-Fi as this Mac.
3. Run:

```bash
python3 tools/rokid_adb_wifi.py
python3 tools/rokid_codex_bridge.py --message "wireless test"
```

If the test works, unplug USB. The same bridge and DJ watcher commands keep
working over Wi-Fi. If setup says `wlan0 has no IPv4 address`, Rokid is not on
Wi-Fi yet.

## 4. Run The Live Controller

```bash
python3 tools/dj_realtime_demo.py --crate data/rekordbox_crate.json
```

Controls:

- Enter or `j`: move down
- `k`: move up
- number: jump to that track number
- `find <text>`: search by artist/title/id
- `list`: print the full crate
- `q`: quit

Dry-run without Rokid:

```bash
python3 tools/dj_realtime_demo.py --crate data/rekordbox_crate.json --dry-run
```

## DDJ-400 / rekordbox Selection Follow Mode

To mirror the actual rekordbox browser selection moved by DDJ-400, use the
Accessibility watcher.

First allow Accessibility access for the terminal/Python process:

System Settings > Privacy & Security > Accessibility

Then probe rekordbox:

```bash
python3 tools/rekordbox_ax_probe.py --watch
```

If the selected row changes when you browse with DDJ-400, start the Rokid
watcher:

```bash
python3 tools/dj_rekordbox_watch.py --crate data/rekordbox_crate.json
```

Dry-run without Rokid:

```bash
python3 tools/dj_rekordbox_watch.py --crate data/rekordbox_crate.json --dry-run
```

If Accessibility cannot read the rekordbox table, fall back to the manual
controller above.

## DDJ-400 MIDI Follow Mode

If rekordbox does not expose the browser table through Accessibility, mirror the
DDJ-400 browse knob MIDI instead:

```bash
python3 tools/dj_ddj400_midi_watch.py --crate data/rekordbox_crate.json --start 1
```

On first knob movement the tool learns the active CC and prints it, for example:

```text
Learned browse CC: 1:64. Use --control 1:64 next time.
```

Then restart with the fixed mapping:

```bash
python3 tools/dj_ddj400_midi_watch.py --crate data/rekordbox_crate.json --control 1:64 --start 1
```

Use `--reverse` if the direction is inverted.

## rekordbox Highlight Follow Mode

Recommended when Accessibility/MIDI cannot expose the rekordbox browser
selection. This tracks the highlighted row on screen without OCR.

Keep the rekordbox window, playlist sort, and zoom fixed during the demo.

Calibrate the track-list region:

```bash
python3 tools/rekordbox_highlight_calibrate.py --crate data/rekordbox_crate.json
```

The calibrator saves `data/rekordbox_screen_region.json` and writes a debug
image to `/tmp/rekordbox_highlight_debug.png`.

Run the watcher:

```bash
python3 tools/dj_rekordbox_highlight_watch.py --crate data/rekordbox_crate.json
```

Dry-run:

```bash
python3 tools/dj_rekordbox_highlight_watch.py --crate data/rekordbox_crate.json --dry-run
```

Useful last-minute overrides:

```bash
python3 tools/dj_rekordbox_highlight_watch.py --top-index 12 --row-height 24 --highlight-mode blue
```
