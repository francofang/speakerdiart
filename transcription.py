"""
Whisper transcription wrapper for CPU inference using faster-whisper (CTranslate2).

Produces WebVTT text compatible with merge.parse_vtt.
"""
from typing import Iterable, Tuple
import io


def _format_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _segments_to_vtt(segments: Iterable[Tuple[float, float, str]]) -> str:
    buf = io.StringIO()
    buf.write("WEBVTT\n\n")
    for start, end, text in segments:
        buf.write(f"{_format_ts(start)} --> {_format_ts(end)}\n")
        buf.write(text.strip() + "\n\n")
    return buf.getvalue()


def transcribe_to_vtt(audio_path: str, model_size: str = "small", device: str = "cpu", language: str = "zh") -> str:
    """
    Run faster-whisper transcription and return VTT text.

    Requires: pip install faster-whisper
    """
    try:
        from faster_whisper import WhisperModel
    except Exception as e:
        raise ImportError(
            "faster-whisper is required. Install with: pip install faster-whisper"
        ) from e

    model = WhisperModel(model_size, device=device)
    segments, _info = model.transcribe(
        audio_path,
        language=language,
        task="transcribe",
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )

    collected = []
    for seg in segments:
        collected.append((seg.start, seg.end, seg.text))
    return _segments_to_vtt(collected)

