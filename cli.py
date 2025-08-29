"""
Batch CLI for Cantonese interview pipeline.

Processes a file or all audio/video files in a directory:
  - Whisper (faster-whisper, CPU) -> VTT
  - Diart (CPU) -> speaker segments
  - Merge -> labeled text
  - Optional ChatGPT polishing

Outputs per input file (basename):
  - <name>.merged.txt (always)
  - <name>.polished.txt (if ChatGPT enabled and successful)
  - <name>.vtt / <name>.rttm (if --export-intermediate)
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Iterable, Dict, List

from pipeline import run_pipeline


AUDIO_EXTS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
    ".flac",
    ".aac",
    ".wma",
    ".mkv",
    ".mov",
}


def is_media_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in AUDIO_EXTS


def find_media_files(root: Path, recursive: bool = True) -> List[Path]:
    if root.is_file():
        return [root] if is_media_file(root) else []
    if not recursive:
        return [p for p in root.iterdir() if is_media_file(p)]
    return [p for p in root.rglob("*") if is_media_file(p)]


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def segments_to_rttm(segments: Iterable[Dict], uri: str) -> str:
    lines = []
    for seg in segments:
        start = float(seg["start"])  # seconds
        end = float(seg["end"])  # seconds
        dur = max(0.0, end - start)
        spk = str(seg["speaker"])  # e.g., SPEAKER_00
        # RTTM: SPEAKER <uri> 1 <start> <dur> <ortho> <stype> <name> <conf>
        lines.append(
            f"SPEAKER {uri} 1 {start:.3f} {dur:.3f} <NA> <NA> {spk} <NA>"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Batch pipeline for Cantonese interviews (CPU)")
    ap.add_argument("input", help="Input media file or folder")
    ap.add_argument("--out", dest="out_dir", default="outputs", help="Output directory (default: outputs)")
    ap.add_argument("--model", dest="model", default="small", help="Whisper model size (tiny/base/small/medium/large)")
    ap.add_argument("--device", dest="device", default="cpu", help="Device: cpu (default) or cuda")
    ap.add_argument("--language", dest="language", default="zh", help="Transcription language (default: zh)")
    ap.add_argument("--speakers", dest="speakers", type=int, default=2, help="Number of speakers (default: 2)")
    ap.add_argument("--export-intermediate", action="store_true", help="Export <name>.vtt and <name>.rttm")
    ap.add_argument("--gpt", action="store_true", help="Use ChatGPT polishing if OPENAI_API_KEY is set")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subfolders when input is a folder")
    args = ap.parse_args()

    inp = Path(args.input).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    files = find_media_files(inp, recursive=args.recursive)
    if not files:
        print(f"No media files found at: {inp}")
        return

    print(f"Found {len(files)} file(s). Processing with model={args.model}, device={args.device}...")
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, f in enumerate(files, 1):
        name = f.stem
        print(f"[{idx}/{len(files)}] {f}")
        try:
            res = run_pipeline(
                str(f),
                whisper_model=args.model,
                device=args.device,
                language=args.language,
                use_chatgpt=args.gpt,
            )

            # Export intermediates
            if args.export_intermediate:
                if res.get("vtt_text"):
                    write_text(out_dir / f"{name}.vtt", res["vtt_text"]) 
                if res.get("speakers"):
                    rttm = segments_to_rttm(res["speakers"], uri=name)
                    write_text(out_dir / f"{name}.rttm", rttm)

            # Always write merged
            merged = res.get("polished_text") or res.get("merged_text") or ""
            write_text(out_dir / f"{name}.merged.txt", merged)
            # If polished available and distinct, save as well
            if res.get("polished_text") and res["polished_text"].strip() != (res.get("merged_text") or "").strip():
                write_text(out_dir / f"{name}.polished.txt", res["polished_text"]) 

        except Exception as e:
            print(f"  Error processing {f}: {e}")

    print(f"Done. Outputs at: {out_dir}")


if __name__ == "__main__":
    main()

