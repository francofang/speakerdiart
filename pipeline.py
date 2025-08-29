"""
End-to-end pipeline orchestration for: Whisper -> Diart -> Merge -> (optional) ChatGPT.
CPU-first design; dependencies are loaded lazily so classic merge mode still works.
"""
from typing import Optional, Dict, Any, List

from merge import parse_vtt, map_speakers_to_subtitles, format_output


def run_pipeline(
    audio_path: str,
    whisper_model: str = "small",
    device: str = "cpu",
    language: str = "zh",
    use_chatgpt: bool = False,
    openai_api_key: Optional[str] = None,
    num_speakers: int = 2,
) -> Dict[str, Any]:
    """
    Execute the pipeline and return a dict with keys:
      - vtt_text: str
      - speakers: List[Dict[start,end,speaker]]
      - merged_text: str
      - polished_text: Optional[str]
    """
    from transcription import transcribe_to_vtt
    from diarize import diarize_audio_to_segments

    # 1) Transcribe
    vtt_text = transcribe_to_vtt(audio_path, model_size=whisper_model, device=device, language=language)

    # 2) Diarize
    speaker_segments: List[Dict] = diarize_audio_to_segments(audio_path, device=device, num_speakers=num_speakers)

    # 3) Merge
    subs = parse_vtt(vtt_text)
    map_speakers_to_subtitles(subs, speaker_segments)
    merged_text = format_output(subs)

    result: Dict[str, Any] = {
        "vtt_text": vtt_text,
        "speakers": speaker_segments,
        "merged_text": merged_text,
        "polished_text": None,
    }

    # 4) Optional ChatGPT postprocess
    if use_chatgpt:
        try:
            from postprocess import polish_with_chatgpt

            polished = polish_with_chatgpt(merged_text, api_key=openai_api_key)
            result["polished_text"] = polished
        except Exception:
            # Fail softly
            result["polished_text"] = None

    return result

