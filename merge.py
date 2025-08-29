"""
Utilities to parse VTT/RTTM and map speaker turns onto subtitle segments.

These functions are extracted from the existing speakerdiart.py to be reusable
by both the classic merge UI and the new end-to-end pipeline.
"""
from typing import List, Dict, Optional


def convert_to_seconds(time_str: str) -> float:
    parts = time_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h = 0
        m, s = parts
    else:
        raise ValueError(f"时间格式错误: {time_str}")
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_vtt(vtt_content: str) -> List[Dict]:
    subtitles: List[Dict] = []
    entries = vtt_content.split("\n\n")
    for entry in entries:
        if "-->" in entry:
            parts = entry.split("\n")
            times = parts[0]
            text = "\n".join(parts[1:]) if len(parts) > 1 else ""
            start_time, end_time = times.split(" --> ")
            subtitles.append(
                {
                    "start": convert_to_seconds(start_time.strip()),
                    "end": convert_to_seconds(end_time.strip()),
                    "text": text.strip(),
                    "speakers": None,
                }
            )
    return subtitles


def parse_rttm(rttm_content: str) -> List[Dict]:
    speakers: List[Dict] = []
    for line in rttm_content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        start_time = float(parts[3])
        duration = float(parts[4])
        speaker_id = parts[7]
        speakers.append({"start": start_time, "end": start_time + duration, "speaker": speaker_id})
    return speakers


def map_speakers_to_subtitles(subtitles: List[Dict], speakers: List[Dict]) -> None:
    for subtitle in subtitles:
        max_overlap_speaker: Optional[str] = None
        max_overlap_duration = 0.0
        for speaker in speakers:
            overlap_start = max(subtitle["start"], speaker["start"])
            overlap_end = min(subtitle["end"], speaker["end"])
            overlap_duration = max(0.0, overlap_end - overlap_start)
            if overlap_duration > max_overlap_duration:
                max_overlap_speaker = speaker["speaker"]
                max_overlap_duration = overlap_duration
        if max_overlap_speaker:
            subtitle["speakers"] = {max_overlap_speaker}


def format_output(subtitles: List[Dict]) -> str:
    output: List[str] = []
    current_speaker: Optional[str] = None
    for sub in subtitles:
        if sub.get("speakers"):
            speaker = list(sub["speakers"])[0]
            if speaker != current_speaker:
                current_speaker = speaker
                output.append(f"[{current_speaker}]")
        if sub.get("text"):
            output.append(sub["text"])
    return "\n".join(output)

