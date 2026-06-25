#!/usr/bin/env python3
"""Run the local STS_test audio model and mirror its text result to Rokid.

This keeps the heavy model runtime on the Mac:
  /Users/yuyoshimuta/dev/STS_test/try_lfm25_audio.py

The Rokid app remains a lightweight display surface that receives compact text
through the existing ADB file bridge.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from rokid_codex_bridge import push_message
from rokid_codex_watch import format_for_glasses


DEFAULT_STS_DIR = Path("/Users/yuyoshimuta/dev/STS_test")
DEFAULT_MODEL = "LiquidAI/LFM2.5-Audio-1.5B-JP"
DEFAULT_OUTPUT_DIR = DEFAULT_STS_DIR / "outputs" / "rokid"


def require_executable(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"{name} not found in PATH.")
    return path


def run_sts(args: argparse.Namespace, sts_args: list[str]) -> subprocess.CompletedProcess[str]:
    uv = require_executable("uv")
    script = args.sts_dir / "try_lfm25_audio.py"
    if not script.exists():
        raise SystemExit(f"STS runner not found: {script}")

    cmd = [uv, "run", "python", str(script), *sts_args]
    print("$ " + " ".join(str(part) for part in cmd), file=sys.stderr, flush=True)
    return subprocess.run(
        cmd,
        cwd=args.sts_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def send_text_to_rokid(args: argparse.Namespace, text: str) -> None:
    message = format_for_glasses(
        text,
        title=args.title,
        max_chars=args.max_chars,
        max_lines=args.max_lines,
        line_width=args.line_width,
    )
    push_message(message)


def play_audio(path: Path) -> None:
    if not path.exists():
        print(f"Audio output not found, skipping playback: {path}", file=sys.stderr)
        return
    afplay = shutil.which("afplay")
    if not afplay:
        print(f"afplay not found, audio left at: {path}", file=sys.stderr)
        return
    subprocess.run([afplay, str(path)], check=False)


def collect_text_from_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace").strip()


def report_failure(proc: subprocess.CompletedProcess[str]) -> None:
    detail = "\n".join(part.strip() for part in (proc.stderr, proc.stdout) if part.strip())
    raise SystemExit(detail or f"STS command failed with exit code {proc.returncode}")


def run_asr(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_text = args.output_text or (args.output_dir / "asr.txt")
    sts_args = [
        "asr",
        "--model",
        args.model,
        "--device",
        args.device,
        "--dtype",
        args.dtype,
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--input",
        str(args.input),
        "--output-text",
        str(output_text),
    ]
    proc = run_sts(args, sts_args)
    if proc.returncode != 0:
        report_failure(proc)

    text = collect_text_from_file(output_text) or proc.stdout.strip()
    if not text:
        raise SystemExit("STS ASR completed but produced no text.")
    send_text_to_rokid(args, text)
    print(text)


def run_chat(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_audio = args.output or (args.output_dir / "chat.wav")
    output_text = args.output_text or (args.output_dir / "chat.txt")
    sts_args = [
        "chat",
        "--model",
        args.model,
        "--device",
        args.device,
        "--dtype",
        args.dtype,
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--audio-temperature",
        str(args.audio_temperature),
        "--audio-top-k",
        str(args.audio_top_k),
        "--output",
        str(output_audio),
        "--output-text",
        str(output_text),
    ]
    if args.audio:
        sts_args.extend(["--audio", str(args.audio)])
    if args.text:
        sts_args.extend(["--text", args.text])

    proc = run_sts(args, sts_args)
    if proc.returncode != 0:
        report_failure(proc)

    text = collect_text_from_file(output_text) or proc.stdout.strip()
    if not text:
        text = f"STS chat completed.\nAudio: {output_audio}"
    send_text_to_rokid(args, text)
    print(text)
    if args.play:
        play_audio(output_audio)


def run_tts(args: argparse.Namespace) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_audio = args.output or (args.output_dir / "tts.wav")
    sts_args = [
        "tts",
        "--model",
        args.model,
        "--device",
        args.device,
        "--dtype",
        args.dtype,
        "--max-new-tokens",
        str(args.max_new_tokens),
        "--audio-temperature",
        str(args.audio_temperature),
        "--audio-top-k",
        str(args.audio_top_k),
        "--text",
        args.text,
        "--voice",
        args.voice,
        "--output",
        str(output_audio),
    ]
    proc = run_sts(args, sts_args)
    if proc.returncode != 0:
        report_failure(proc)

    send_text_to_rokid(args, f"Speaking:\n{args.text}")
    print(f"Wrote {output_audio}")
    if args.play:
        play_audio(output_audio)


def add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--sts-dir", type=Path, default=DEFAULT_STS_DIR)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", choices=("auto", "cpu", "mps", "cuda"), default="mps")
    parser.add_argument("--dtype", choices=("auto", "float32", "float16", "bfloat16"), default="float32")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--title", default="STS")
    parser.add_argument("--max-chars", type=int, default=220)
    parser.add_argument("--max-lines", type=int, default=5)
    parser.add_argument("--line-width", type=int, default=32)


def add_audio_generation_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--audio-temperature", type=float, default=0.8)
    parser.add_argument("--audio-top-k", type=int, default=64)
    parser.add_argument("--play", action="store_true", help="Play generated audio on the Mac with afplay")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Connect the local STS_test model runner to the Rokid display bridge.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              tools/rokid_sts_bridge.py asr --input /path/to/question.wav
              tools/rokid_sts_bridge.py chat --audio /path/to/question.wav --play
              tools/rokid_sts_bridge.py chat --text "こんにちは" --play
              tools/rokid_sts_bridge.py tts --text "Rokid STS bridge is ready." --play
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    asr = subparsers.add_parser("asr", help="Transcribe audio and show text on Rokid.")
    add_common_options(asr)
    asr.add_argument("--input", type=Path, required=True)
    asr.add_argument("--output-text", type=Path)
    asr.set_defaults(func=run_asr)

    chat = subparsers.add_parser("chat", help="Run one STS/chat turn and show text on Rokid.")
    add_common_options(chat)
    add_audio_generation_options(chat)
    chat.add_argument("--audio", type=Path)
    chat.add_argument("--text")
    chat.add_argument("--output", type=Path)
    chat.add_argument("--output-text", type=Path)
    chat.set_defaults(func=run_chat)

    tts = subparsers.add_parser("tts", help="Generate speech and show the spoken text on Rokid.")
    add_common_options(tts)
    add_audio_generation_options(tts)
    tts.add_argument("--text", required=True)
    tts.add_argument("--voice", choices=("uk-female", "uk-male", "us-female", "us-male"), default="us-female")
    tts.add_argument("--output", type=Path)
    tts.set_defaults(func=run_tts)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    if getattr(args, "input", None) and not args.input.exists():
        raise SystemExit(f"Input audio does not exist: {args.input}")
    if getattr(args, "audio", None) and not args.audio.exists():
        raise SystemExit(f"Input audio does not exist: {args.audio}")
    if args.command == "chat" and not args.audio and not args.text:
        raise SystemExit("Provide --audio, --text, or both for chat.")
    args.func(args)


if __name__ == "__main__":
    main()
