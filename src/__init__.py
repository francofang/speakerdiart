"""
广东话采访处理系统

端到端的音频转录和说话人分离处理系统。
"""

__version__ = "2.0.0"
__author__ = "Speaker Diarization Team"

from .pipeline import ProcessingPipeline, run_pipeline
from .transcription import WhisperTranscriber, transcribe_to_vtt
from .diarization import SpeakerDiarizer, diarize_audio_to_segments
from .merge import parse_vtt, parse_rttm, map_speakers_to_subtitles, format_output
from .postprocess import ChatGPTProcessor, polish_with_chatgpt
from .config import get_config, load_config
from .exceptions import SpeakerDiartError

__all__ = [
    "ProcessingPipeline",
    "run_pipeline",
    "WhisperTranscriber",
    "transcribe_to_vtt",
    "SpeakerDiarizer", 
    "diarize_audio_to_segments",
    "parse_vtt",
    "parse_rttm",
    "map_speakers_to_subtitles",
    "format_output",
    "ChatGPTProcessor",
    "polish_with_chatgpt",
    "get_config",
    "load_config",
    "SpeakerDiartError"
]