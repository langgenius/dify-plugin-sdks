import binascii
import io
import pathlib
from typing import IO
from unittest.mock import MagicMock

import pytest

from dify_plugin.core.entities.plugin.request import ModelInvokeSpeech2TextRequest
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.runtime import Session
from dify_plugin.entities.model import ModelType
from dify_plugin.interfaces.model.speech2text_model import Speech2TextModel


@pytest.mark.parametrize(
    ("audio", "expected_suffix"),
    [
        (b"RIFF\x24\x08\x00\x00WAVEpayload", ".wav"),
        (b"fLaCpayload", ".flac"),
        (b"OggSpayload", ".ogg"),
        (b"\x00\x00\x00\x18ftypM4A payload", ".m4a"),
        (b"\x00\x00\x00\x18ftypmp42payload", ".mp4"),
        (
            bytes.fromhex(
                "1a45dfa39f4286810142f7810142f2810442f38108"
                "4282847765626d4287810242858102"
            ),
            ".webm",
        ),
        (b"\x1a\x45\xdf\xa3\x88\x42\x82\x40\x04webm", ".webm"),
        (b"\x1a\x45\xdf\xa3\x88\x42\x82\x85webm\0", ".webm"),
        pytest.param(
            bytes.fromhex("1a45dfa301000000000000074282847765626d"),
            ".webm",
            id="webm-eight-byte-header-size",
        ),
        pytest.param(
            bytes.fromhex("1a45dfa389ec804282847765626d"),
            ".webm",
            id="webm-after-empty-void",
        ),
        pytest.param(bytes.fromhex("1a45dfa3"), ".mp3", id="ebml-missing-header-size"),
        pytest.param(
            bytes.fromhex("1a45dfa340"), ".mp3", id="ebml-truncated-header-size"
        ),
        pytest.param(
            bytes.fromhex("1a45dfa300"), ".mp3", id="ebml-invalid-size-marker"
        ),
        pytest.param(
            bytes.fromhex("1a45dfa3ff4282847765626d"),
            ".mp3",
            id="ebml-unknown-header-size",
        ),
        pytest.param(
            bytes.fromhex("1a45dfa388"), ".mp3", id="ebml-truncated-header-data"
        ),
        pytest.param(bytes.fromhex("1a45dfa380"), ".mp3", id="ebml-empty-header"),
        pytest.param(
            bytes.fromhex("1a45dfa38100"), ".mp3", id="ebml-invalid-element-marker"
        ),
        pytest.param(
            bytes.fromhex("1a45dfa38142"), ".mp3", id="ebml-truncated-element-id"
        ),
        pytest.param(
            bytes.fromhex("1a45dfa3824282"), ".mp3", id="ebml-missing-element-size"
        ),
        pytest.param(
            bytes.fromhex("1a45dfa3874282ff7765626d"),
            ".mp3",
            id="ebml-unknown-doctype-size",
        ),
        pytest.param(
            bytes.fromhex("1a45dfa3864282847765626d"),
            ".mp3",
            id="ebml-doctype-exceeds-parent",
        ),
        pytest.param(
            bytes.fromhex("1a45dfa38a4282877765626d"),
            ".mp3",
            id="ebml-doctype-exceeds-file",
        ),
        pytest.param(
            bytes.fromhex("1a45dfa382ec80"), ".mp3", id="ebml-without-doctype"
        ),
        (b"RIFF\x24\x08\x00\x00AVI payload", ".mp3"),
        (b"\x00\x00\x00\x18ftypavifpayload", ".mp3"),
        (b"\x1a\x45\xdf\xa3\x9f\x42\x82\x88matroskapayload", ".mp3"),
        (
            b"\x1a\x45\xdf\xa3\x8b\x42\x82\x88matroska\x42\x82\x84webm",
            ".mp3",
        ),
        (
            b"\x1a\x45\xdf\xa3\x94\xec\x87\x42\x82\x84webm\x42\x82\x88matroska",
            ".mp3",
        ),
        (b"ID3payload", ".mp3"),
        (b"", ".mp3"),
    ],
)
def test_invoke_speech_to_text_preserves_audio_format(
    audio: bytes,
    expected_suffix: str,
) -> None:
    files: list[IO[bytes]] = []

    def invoke(
        model_name: str,
        credentials: dict[str, object],
        audio_file: IO[bytes],
        user_id: str | None,
    ) -> str:
        del model_name, credentials, user_id
        assert isinstance(audio_file, io.IOBase)
        assert pathlib.Path(audio_file.name).suffix == expected_suffix
        assert audio_file.tell() == 0
        assert audio_file.read() == audio
        files.append(audio_file)
        return "transcript"

    model = MagicMock(spec=Speech2TextModel)
    model.invoke.side_effect = invoke
    registration = MagicMock()
    registration.get_model_instance.return_value = model
    executor = PluginExecutor(config=MagicMock(), registration=registration)
    request = ModelInvokeSpeech2TextRequest(
        user_id="user",
        provider="provider",
        model_type=ModelType.SPEECH2TEXT,
        model="model",
        credentials={},
        file=binascii.hexlify(audio).decode(),
    )

    assert executor.invoke_speech_to_text(Session.empty_session(), request) == {
        "result": "transcript",
    }
    assert len(files) == 1
    assert files[0].closed
    assert not pathlib.Path(files[0].name).exists()
