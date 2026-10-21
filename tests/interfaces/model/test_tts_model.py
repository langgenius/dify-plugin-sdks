from collections.abc import Generator, Mapping
from unittest.mock import Mock

import pytest

from dify_plugin.entities.model import AIModelEntity, ModelPropertyKey, ModelType
from dify_plugin.entities.model.tts import TTSResult
from dify_plugin.errors.model import (
    InvokeBadRequestError,
    InvokeConnectionError,
    InvokeError,
)
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
    model = StubTTS([
        AIModelEntity(
            model="model",
            model_type=ModelType.TTS,
            model_properties={ModelPropertyKey.AUDIO_TYPE: audio_type},
        )
    ])

    assert model.get_tts_model_mime_type("model", {}) == expected


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


class StubTTS(TTSModel):
    def _invoke(self, **kwargs: object) -> bytes | Generator[bytes]:
        del kwargs
        raise NotImplementedError

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {InvokeConnectionError: [TimeoutError]}


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (
            None,
            [{"name": "Alloy", "value": "alloy"}, {"name": "Nova", "value": "nova"}],
        ),
        ("en-US", [{"name": "Alloy", "value": "alloy"}]),
        ("fr-FR", []),
    ],
)
def test_tts_voices_filter_by_model_language(
    language: str | None, expected: list[dict[str, str]]
) -> None:
    model = StubTTS([
        AIModelEntity(
            model="model",
            model_type=ModelType.TTS,
            model_properties={
                ModelPropertyKey.VOICES: [
                    {"name": "Alloy", "mode": "alloy", "language": ["en-US", "zh-CN"]},
                    {"name": "Nova", "mode": "nova", "language": ["zh-CN"]},
                ],
                ModelPropertyKey.DEFAULT_VOICE: "alloy",
                ModelPropertyKey.AUDIO_TYPE: "mp3",
                ModelPropertyKey.WORD_LIMIT: 4096,
                ModelPropertyKey.MAX_WORKERS: 2,
            },
        )
    ])

    assert model.get_tts_model_voices("model", {}, language) == expected
    assert model._get_model_default_voice("model", {}) == "alloy"
    assert model._get_model_word_limit("model", {}) == 4096
    assert model._get_model_workers_limit("model", {}) == 2
    assert model.get_tts_model_mime_type("model", {}) == "audio/mpeg"


def test_missing_tts_schema_properties_have_no_defaults() -> None:
    model = StubTTS([])

    assert model.get_tts_model_voices("unknown", {}) is None
    assert model._get_model_default_voice("unknown", {}) is None
    assert model._get_model_word_limit("unknown", {}) is None
    assert model._get_model_workers_limit("unknown", {}) is None
    assert model.get_tts_model_mime_type("unknown", {}) is None


@pytest.mark.parametrize("audio", [b"", b"\x00\xffaudio"])
def test_tts_returns_complete_audio_without_iterating_bytes(
    audio: bytes,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = StubTTS([])
    provider = Mock(return_value=audio)
    monkeypatch.setattr(model, "_invoke", provider)

    result = model.invoke(
        "model", "tenant", {"key": "secret"}, "hello", "alloy", "user"
    )

    assert isinstance(result, bytes)
    assert result == audio
    assert model.started_at == 0
    provider.assert_called_once_with(
        model="model",
        tenant_id="tenant",
        credentials={"key": "secret"},
        content_text="hello",
        voice="alloy",
        user="user",
    )


@pytest.mark.parametrize("audio", [[], [b"\x00\xff", b"audio"]])
def test_tts_consumes_provider_stream_and_resets_timing(
    audio: list[bytes],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = StubTTS([])
    closed = []

    def response() -> Generator[bytes]:
        try:
            assert model.started_at > 0
            yield from audio
        finally:
            closed.append(True)

    monkeypatch.setattr(model, "_invoke", Mock(return_value=response()))
    stream = model.invoke("model", "tenant", {}, "hello", "alloy")

    assert isinstance(stream, Generator)
    assert list(stream) == audio
    assert closed == [True]
    assert model.started_at == 0


def test_closing_tts_stream_closes_provider_without_consuming_more_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = StubTTS([])
    closed = []

    def response() -> Generator[bytes]:
        try:
            yield b"first"
            pytest.fail("Closing the stream must not read more audio")
        finally:
            closed.append(True)

    provider_stream = response()
    monkeypatch.setattr(model, "_invoke", Mock(return_value=provider_stream))
    stream = model.invoke("model", "tenant", {}, "hello", "alloy")
    assert isinstance(stream, Generator)
    assert next(stream) == b"first"
    stream.close()
    stream.close()

    assert closed == [True]
    assert model.started_at == 0


@pytest.mark.parametrize(
    ("error", "expected_type"),
    [
        (TimeoutError("provider stalled"), InvokeConnectionError),
        (RuntimeError("audio failed"), InvokeError),
        (InvokeBadRequestError("invalid voice"), InvokeError),
    ],
)
def test_tts_maps_errors_after_audio_starts(
    error: Exception,
    expected_type: type[InvokeError],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = StubTTS([])
    closed = []

    def response() -> Generator[bytes]:
        try:
            yield b"first"
            raise error
        finally:
            closed.append(True)

    monkeypatch.setattr(model, "_invoke", Mock(return_value=response()))
    stream = model.invoke("model", "tenant", {}, "hello", "alloy")
    assert isinstance(stream, Generator)
    assert next(stream) == b"first"

    with pytest.raises(expected_type) as exc_info:
        next(stream)

    assert type(exc_info.value) is expected_type
    assert exc_info.value.__cause__ is error
    assert closed == [True]
    assert model.started_at == 0
