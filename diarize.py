"""
Speaker diarization wrapper (CPU-friendly) using diart + onnxruntime if available.

Falls back to a clear ImportError with setup guidance when diart is missing.
Returns a list of dicts: {start: float, end: float, speaker: str}
"""
from typing import List, Dict


def diarize_audio_to_segments(audio_path: str, device: str = "cpu", num_speakers: int = 2) -> List[Dict]:
    """
    Run diarization and return segments with speaker labels.

    Requires: pip install diart onnxruntime (or onnxruntime-gpu)
    """
    try:
        # diart has evolved; prefer the public CLI/pipeline API if present.
        # Importing lazily to avoid hard dependency if users only run merge.
        import diart
    except Exception as e:
        raise ImportError(
            "diart is required for diarization. Install with: pip install diart onnxruntime"
        ) from e

    # Attempt using diart's simple pipeline API if available.
    # We keep this wrapper minimal and defensive.
    try:
        from diart.inference import Diarization
        from diart.sources import FileAudioSource
    except Exception:
        # Fallback older API: use the high-level function if provided
        try:
            # Some versions expose a convenience function
            from diart import diarize as diart_run  # type: ignore
        except Exception as inner:
            raise ImportError(
                "Unsupported diart version. Please update diart or consult its docs."
            ) from inner
        # If we reached here, we cannot guarantee stable API; guide the user instead
        raise ImportError(
            "This project expects diart>=0.9 with inference APIs. Update diart and try again."
        )

    # Use file source and synchronous inference
    source = FileAudioSource(audio_path)
    engine = Diarization(num_speakers=num_speakers, device=device)
    result = engine(source)

    segments: List[Dict] = []
    # Convert result (pyannote style timeline) to flat segments
    # result.itertracks(yield_label=True) -> ((segment, track), label)
    try:
        for (_segment, _track), label in result.itertracks(yield_label=True):
            start = float(_segment.start)
            end = float(_segment.end)
            segments.append({"start": start, "end": end, "speaker": str(label)})
    except Exception:
        # Some versions expose .labels_ and .get_timeline(label)
        for label in getattr(result, "labels_", []):
            timeline = result.get_timeline(label)  # type: ignore
            for seg in timeline:
                segments.append({"start": float(seg.start), "end": float(seg.end), "speaker": str(label)})

    # Normalize labels to SPEAKER_00/01 for consistency
    label_map = {}
    ordered = sorted(set(s["speaker"] for s in segments))
    for i, lab in enumerate(ordered):
        label_map[lab] = f"SPEAKER_{i:02d}"
    for s in segments:
        s["speaker"] = label_map[s["speaker"]]

    return segments
