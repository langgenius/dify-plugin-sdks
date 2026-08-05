from unittest.mock import MagicMock

import pytest

from dify_plugin.entities.model.tts import TTSResult
from dify_plugin.interfaces.model.tts_model import TTSModel


@pytest.mark.parametrize(
    ("audio_type", "expected"),
    [
        ("mp3", "audio/mpeg"),
        ("wav", "audio/wav"),
        ("ogg", "audio/ogg"),
        ("aac", "audio/aac"),
        ("mp4", "audio/mp4"),
        ("unknown", None),
        (None, None),
    ],
)
def test_get_tts_model_mime_type(
    audio_type: str | None,
    expected: str | None,
) -> None:
    model = MagicMock(spec=TTSModel)
    model._get_model_audio_type.return_value = audio_type

    assert TTSModel.get_tts_model_mime_type(model, "model", {}) == expected


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"result": "00"}, {"result": "00"}),
        (
            {"result": "00", "mime_type": "audio/wav"},
            {"result": "00", "mime_type": "audio/wav"},
        ),
    ],
)
def test_tts_result_mime_type_is_optional(
    payload: dict[str, str],
    expected: dict[str, str],
) -> None:
    result = TTSResult.model_validate(payload)

    assert result.model_dump(exclude_none=True) == expected


@pytest.mark.parametrize(
    ("text", "max_length", "expected"),
    [
        ("", 4, []),
        ("abcd", 4, ["abcd"]),
        ("abcdefghij", 4, ["abcd", "efgh", "ij"]),
        ("abcd.", 3, ["abc", "d."]),
        ("Hi.xxxxxx", 5, ["Hi.", "xxxxx", "x"]),
        ("One.Two?Three!", 8, ["One.Two?", "Three!"]),
    ],
)
def test_split_text_into_sentences(
    text: str,
    max_length: int,
    expected: list[str],
) -> None:
    chunks = TTSModel._split_text_into_sentences(text, max_length)

    assert chunks == expected
    assert "".join(chunks) == text
    assert all(chunks)
    assert all(len(chunk) <= max_length for chunk in chunks)


@pytest.mark.parametrize("max_length", [0, -1])
def test_split_text_into_sentences_rejects_non_positive_length(
    max_length: int,
) -> None:
    with pytest.raises(ValueError, match="max_length must be greater than 0"):
        TTSModel._split_text_into_sentences("text", max_length)
