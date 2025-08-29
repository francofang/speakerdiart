import textwrap

from merge import convert_to_seconds, parse_vtt, map_speakers_to_subtitles, format_output


def test_convert_to_seconds_supports_two_and_three_part_times():
    assert abs(convert_to_seconds("02:03") - (2 * 60 + 3)) < 1e-6
    assert abs(convert_to_seconds("01:02:03") - (1 * 3600 + 2 * 60 + 3)) < 1e-6


def test_mapping_picks_max_overlap_speaker():
    # Two subtitle segments
    vtt = textwrap.dedent(
        """
        00:00:00.000 --> 00:00:03.000
        hello there

        00:00:03.000 --> 00:00:06.000
        how are you
        """
    ).strip()

    subs = parse_vtt(vtt)

    # Two speakers with overlapping turns
    speakers = [
        {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
        {"start": 1.5, "end": 3.2, "speaker": "SPEAKER_01"},
        {"start": 3.0, "end": 5.0, "speaker": "SPEAKER_00"},
        {"start": 4.5, "end": 6.0, "speaker": "SPEAKER_01"},
    ]

    map_speakers_to_subtitles(subs, speakers)
    out = format_output(subs)

    # First line should belong to SPEAKER_01 (overlap 1.7s vs 2.0s? compute)
    # Overlaps: [0-3] with 0-2 => 2.0s (SPK00), with 1.5-3.2 => 1.5s (SPK01)
    # So SPEAKER_00 wins for first.
    assert "[SPEAKER_00]\nhello there" in out

    # Second line overlaps [3-6] with [3-5] => 2.0s (SPK00), with [4.5-6] => 1.5s (SPK01)
    assert "how are you" in out
    # Ensure speaker header appears at least once
    assert out.startswith("[SPEAKER_00]")

