from collections.abc import Generator
from unittest.mock import MagicMock

from dify_plugin.core.entities.plugin.request import ModelInvokeTTSRequest
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.entities.model import ModelType
from dify_plugin.interfaces.model.tts_model import TTSModel


def _invoke_tts(
    audio: bytes | Generator[bytes, None, None],
    mime_type: str | None,
) -> list[dict[str, str]]:
    model = MagicMock(spec=TTSModel)
    model.invoke.return_value = audio
    model.get_tts_model_mime_type.return_value = mime_type
    registration = MagicMock()
    registration.get_model_instance.return_value = model
    executor = PluginExecutor(config=MagicMock(), registration=registration)
    request = ModelInvokeTTSRequest(
        user_id="user",
        provider="provider",
        model_type=ModelType.TTS,
        model="model",
        credentials={},
        content_text="text",
        voice="voice",
        tenant_id="tenant",
    )

    result = list(executor.invoke_tts(Session.empty_session(), request))
    model.get_tts_model_mime_type.assert_called_once_with("model", {})
    return result


def test_invoke_tts_includes_mime_type_for_bytes() -> None:
    assert _invoke_tts(b"\x00\x01", "audio/wav") == [
        {"result": "0001", "mime_type": "audio/wav"}
    ]


def test_invoke_tts_includes_mime_type_for_each_stream_chunk() -> None:
    audio = (chunk for chunk in (b"\x00", b"\x01"))

    assert _invoke_tts(audio, "audio/mpeg") == [
        {"result": "00", "mime_type": "audio/mpeg"},
        {"result": "01", "mime_type": "audio/mpeg"},
    ]


def test_invoke_tts_omits_missing_mime_type() -> None:
    assert _invoke_tts(b"\x00", None) == [{"result": "00"}]
