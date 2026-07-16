from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from dify_plugin.errors.model import CredentialsValidateFailedError
from examples.openai.models.tts import tts


def test_streaming_preserves_request_chunk_and_voice_order() -> None:
    events = Mock()

    def iter_bytes(sentence: str) -> Generator[bytes, None, None]:
        events("iter", sentence)
        yield f"{sentence}:1".encode()
        yield f"{sentence}:2".encode()

    @contextmanager
    def response(sentence: str) -> Generator[SimpleNamespace, None, None]:
        events("enter", sentence)
        try:
            yield SimpleNamespace(iter_bytes=lambda _: iter_bytes(sentence))
        finally:
            events("close", sentence)

    def create_response(**kwargs: str) -> AbstractContextManager[SimpleNamespace]:
        sentence = kwargs["input"]
        events("create", sentence)
        return response(sentence)

    create = Mock(side_effect=create_response)
    client = SimpleNamespace(
        audio=SimpleNamespace(
            speech=SimpleNamespace(
                with_streaming_response=SimpleNamespace(create=create),
            ),
        ),
    )
    model = tts.OpenAIText2SpeechModel([])

    with (
        patch.object(tts, "OpenAI", return_value=client),
        patch.object(
            model,
            "get_tts_model_voices",
            return_value=[{"value": "alloy"}, {"value": "echo"}],
        ),
        patch.object(model, "_get_model_default_voice") as default_voice,
        patch.object(model, "_get_model_word_limit", return_value=5),
        patch.object(
            model,
            "_split_text_into_sentences",
            return_value=["first", "second"],
        ),
    ):
        audio = model.invoke(
            model="tts-1",
            tenant_id="tenant",
            credentials={"openai_api_key": "test"},
            content_text="long input",
            voice="echo",
        )
        events.assert_not_called()
        assert list(audio) == [  # noqa: S101
            b"first:1",
            b"first:2",
            b"second:1",
            b"second:2",
        ]
    default_voice.assert_not_called()
    create.assert_has_calls(
        [
            call(
                model="tts-1",
                response_format="mp3",
                input="first",
                voice="echo",
            ),
            call(
                model="tts-1",
                response_format="mp3",
                input="second",
                voice="echo",
            ),
        ],
    )
    events.assert_has_calls(
        [
            call("create", "first"),
            call("enter", "first"),
            call("iter", "first"),
            call("close", "first"),
            call("create", "second"),
            call("enter", "second"),
            call("iter", "second"),
            call("close", "second"),
        ],
    )


def test_validate_credentials_consumes_and_closes_stream() -> None:
    model = tts.OpenAIText2SpeechModel([])
    audio = MagicMock()
    audio.__next__.return_value = b"audio"
    credentials = {"openai_api_key": "test"}

    with (
        patch.object(model, "_get_model_default_voice", return_value="alloy"),
        patch.object(
            model,
            "_tts_invoke_streaming",
            return_value=audio,
        ) as invoke_streaming,
    ):
        model.validate_credentials(model="tts-1", credentials=credentials)

    audio.__next__.assert_called_once_with()
    audio.close.assert_called_once_with()
    invoke_streaming.assert_called_once_with(
        model="tts-1",
        credentials=credentials,
        content_text="Hello Dify!",
        voice="alloy",
    )


def test_validate_credentials_rejects_empty_stream() -> None:
    model = tts.OpenAIText2SpeechModel([])
    audio = MagicMock()
    audio.__next__.side_effect = StopIteration

    with (
        patch.object(model, "_get_model_default_voice", return_value="alloy"),
        patch.object(model, "_tts_invoke_streaming", return_value=audio),
        pytest.raises(
            CredentialsValidateFailedError,
            match="No audio bytes found",
        ),
    ):
        model.validate_credentials(
            model="tts-1",
            credentials={"openai_api_key": "test"},
        )

    audio.close.assert_called_once_with()
