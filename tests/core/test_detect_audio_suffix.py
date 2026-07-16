"""Tests for audio format detection used by speech-to-text dispatch.

These exercise ``_detect_audio_suffix`` with only the leading magic bytes of
each container, so no real audio files are required.
"""

import pytest

from dify_plugin.core.plugin_executor import _detect_audio_suffix  # noqa: PLC2701


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        # WAV: "RIFF" .... "WAVE"
        (b"RIFF\x24\x08\x00\x00WAVEfmt ", ".wav"),
        # FLAC
        (b"fLaC\x00\x00\x00\x22", ".flac"),
        # Ogg (covers oga / ogg-opus)
        (b"OggS\x00\x02\x00\x00\x00\x00\x00\x00", ".ogg"),
        # MP4/M4A (AAC): ftyp box at offset 4
        (b"\x00\x00\x00\x20ftypM4A ", ".m4a"),
        (b"\x00\x00\x00\x18ftypmp42", ".m4a"),
        # WebM / Matroska EBML magic
        (b"\x1a\x45\xdf\xa3\x01\x00\x00\x00", ".webm"),
    ],
)
def test_detect_audio_suffix_known_formats(header: bytes, expected: str) -> None:
    assert _detect_audio_suffix(header) == expected


@pytest.mark.parametrize(
    "header",
    [
        b"",
        b"\x00\x00\x00\x00",
        b"not an audio header",
        # "RIFF" but not "WAVE" (e.g. AVI) must not be misdetected as wav
        b"RIFF\x24\x08\x00\x00AVI LIST",
        # MP3 (ID3 tag and raw frame sync) intentionally falls through to .mp3,
        # matching the previous hardcoded behavior.
        b"ID3\x04\x00\x00\x00\x00\x00\x00",
        b"\xff\xf3\x90\x64\x00\x00\x00\x00",
    ],
)
def test_detect_audio_suffix_falls_back_to_mp3(header: bytes) -> None:
    assert _detect_audio_suffix(header) == ".mp3"
