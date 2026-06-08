"""End-to-end tests for ``PluginExecutor.invoke_speech_to_text``.

These drive the real dispatch with a recording fake model to assert that the
temp file handed to the speech2text model is labeled with a suffix that matches
the audio container, and that the full payload (not just the sniffed header) is
written.
"""

import binascii
import pathlib
from collections.abc import Mapping
from typing import IO

import pytest

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.request import ModelInvokeSpeech2TextRequest
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import AIModelEntity, FetchFrom, ModelType
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel


def _model_entity() -> AIModelEntity:
    return AIModelEntity(
        model="whisper",
        label=I18nObject(en_us="whisper"),
        model_type=ModelType.SPEECH2TEXT,
        fetch_from=FetchFrom.PREDEFINED_MODEL,
        model_properties={},
        parameter_rules=[],
    )


class RecordingSpeech2TextModel(Speech2TextModel):
    """Captures the temp-file suffix and bytes the executor hands to the model."""

    model_type = ModelType.SPEECH2TEXT

    def __init__(self) -> None:
        super().__init__(model_schemas=[_model_entity()])
        self.captured_suffix: str | None = None
        self.captured_bytes: bytes | None = None

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model, credentials

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}

    def _invoke(
        self,
        model: str,
        credentials: dict,
        file: IO[bytes],
        user: str | None = None,
    ) -> str:
        del model, credentials, user
        self.captured_suffix = pathlib.Path(file.name).suffix
        self.captured_bytes = file.read()
        return "transcribed"


class _Registration:
    def __init__(self, model_instance: object) -> None:
        self.model_instance = model_instance

    def get_model_instance(self, provider: str, model_type: ModelType) -> object:
        del provider, model_type
        return self.model_instance


def _request(audio: bytes) -> ModelInvokeSpeech2TextRequest:
    return ModelInvokeSpeech2TextRequest(
        user_id="user-1",
        provider="provider",
        model_type=ModelType.SPEECH2TEXT,
        model="whisper",
        credentials={},
        file=binascii.hexlify(audio).decode("ascii"),
    )


# Real container headers padded with trailing bytes so the test also proves the
# entire payload is written, not just the sniffed 16-byte header.
WAV = b"RIFF\x24\x08\x00\x00WAVEfmt " + b"\x00" * 64
M4A = b"\x00\x00\x00\x20ftypM4A " + b"\x11" * 64
OGG = b"OggS\x00\x02\x00\x00\x00\x00\x00\x00" + b"\x22" * 64
UNKNOWN = b"\x00\x01\x02\x03 not a known audio container " + b"\x33" * 32


@pytest.mark.parametrize(
    ("audio", "expected_suffix"),
    [
        (WAV, ".wav"),
        (M4A, ".m4a"),
        (OGG, ".ogg"),
        (UNKNOWN, ".mp3"),
    ],
)
def test_invoke_speech_to_text_labels_temp_file_by_format(
    audio: bytes,
    expected_suffix: str,
) -> None:
    model = RecordingSpeech2TextModel()
    executor = PluginExecutor(DifyPluginEnv(), _Registration(model))

    result = executor.invoke_speech_to_text(Session.empty_session(), _request(audio))

    assert result == {"result": "transcribed"}
    assert model.captured_suffix == expected_suffix
    # The full payload reaches the model, not just the sniffed header.
    assert model.captured_bytes == audio


def test_invoke_speech_to_text_rejects_non_speech2text_model() -> None:
    executor = PluginExecutor(DifyPluginEnv(), _Registration(object()))

    with pytest.raises(ValueError, match="not found for provider"):
        executor.invoke_speech_to_text(Session.empty_session(), _request(WAV))
