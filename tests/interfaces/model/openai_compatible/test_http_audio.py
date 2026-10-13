from __future__ import annotations

import json
import wave
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import gevent
import pytest
from gevent.event import Event

from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError
from dify_plugin.interfaces.model.openai_compatible.speech2text import (
    OAICompatSpeech2TextModel,
)
from dify_plugin.interfaces.model.openai_compatible.tts import OAICompatText2SpeechModel
from tests.http_server import HTTPServerFactory, Response

if TYPE_CHECKING:
    from requests import Response as HTTPResponse

pytestmark = pytest.mark.integration


def wav_audio(frames: bytes, rate: int = 24_000) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(frames)
    return output.getvalue()


@pytest.mark.parametrize("count", [1, 2])
def test_tts_preserves_provider_wav_bytes_for_each_sentence(
    http_server: HTTPServerFactory,
    count: int,
) -> None:
    frames = [b"\x01\x00" * 8, b"\x02\x00" * 8][:count]
    audio = [wav_audio(frame) for frame in frames]
    sentences = ["One.", "Two."][:count]
    server = http_server([Response(chunks=(body[:13], body[13:])) for body in audio])
    model = OAICompatText2SpeechModel([])

    result = b"".join(
        model.invoke(
            "model",
            "tenant",
            {
                "endpoint_url": f"{server.url}/v1/",
                "api_key": "key",
                "endpoint_model_name": "upstream-tts",
                "word_limit": 4,
                "audio_type": "wav",
            },
            "".join(sentences),
            "voice-1",
        )
    )

    assert result == b"".join(audio)
    assert [request.path for request in server.requests] == ["/v1/audio/speech"] * count
    assert all(
        request.headers["Authorization"] == "Bearer key" for request in server.requests
    )
    assert [json.loads(request.body) for request in server.requests] == [
        {
            "model": "upstream-tts",
            "input": sentence,
            "voice": "voice-1",
            "response_format": "wav",
        }
        for sentence in sentences
    ]
    assert model.started_at == 0


@pytest.mark.parametrize("failure", ["format", "truncated", "invalid"])
def test_tts_streams_each_provider_segment_without_reencoding(
    http_server: HTTPServerFactory,
    failure: str,
) -> None:
    valid = wav_audio(b"\x01\x00" * 8)
    second = {
        "format": wav_audio(b"\x02\x00" * 8, rate=16_000),
        "truncated": valid[:-2],
        "invalid": b"not WAV",
    }[failure]
    server = http_server([Response(body=valid), Response(body=second)])
    model = OAICompatText2SpeechModel([])
    stream = model.invoke(
        "model",
        "tenant",
        {"endpoint_url": server.url, "word_limit": 4, "audio_type": "wav"},
        "One.Two.",
        "alloy",
    )
    try:
        assert next(stream) == valid
        assert len(server.requests) == 1
        assert b"".join(stream) == second
    finally:
        stream.close()
    assert model.started_at == 0


def test_tts_empty_text_does_not_make_a_request(http_server: HTTPServerFactory) -> None:
    server = http_server([])
    chunks = list(
        OAICompatText2SpeechModel([]).invoke(
            "model", "tenant", {"endpoint_url": server.url}, "", "alloy"
        )
    )
    assert chunks == []
    assert server.requests == []


def test_tts_early_close_releases_the_http_response(
    http_server: HTTPServerFactory, http_responses: tuple[list[HTTPResponse], Event]
) -> None:
    responses, _ready = http_responses
    server = http_server([Response(chunks=(b"first", b"second"))])
    model = OAICompatText2SpeechModel([])
    stream = model.invoke(
        "model", "tenant", {"endpoint_url": server.url}, "Hello", "alloy"
    )

    assert next(stream) == b"first"
    stream.close()

    assert responses[0].raw.closed
    assert model.started_at == 0


def test_tts_greenlet_cancellation_releases_the_http_response(
    http_server: HTTPServerFactory, http_responses: tuple[list[HTTPResponse], Event]
) -> None:
    responses, ready = http_responses
    server = http_server([Response(chunks=(b"delayed",), delay=10)])
    model = OAICompatText2SpeechModel([])
    stream = model.invoke(
        "model", "tenant", {"endpoint_url": server.url}, "Hello", "alloy"
    )
    worker = gevent.spawn(list, stream)
    try:
        assert ready.wait(timeout=2), "The HTTP response was not received"
    finally:
        worker.kill(timeout=2)

    assert worker.ready()
    assert responses[0].raw.closed
    assert model.started_at == 0


def test_tts_truncated_response_reports_error_and_closes_response(
    http_server: HTTPServerFactory, http_responses: tuple[list[HTTPResponse], Event]
) -> None:
    responses, _ready = http_responses
    server = http_server([
        Response(headers={"Content-Length": "5000"}, body=b"a" * 4096)
    ])
    model = OAICompatText2SpeechModel([])
    stream = model.invoke(
        "model", "tenant", {"endpoint_url": server.url}, "Hello", "alloy"
    )

    chunks = []
    with pytest.raises(InvokeError):
        chunks.extend(stream)

    assert (b"a" * 4096).startswith(b"".join(chunks))
    assert responses[0].raw.closed
    assert model.started_at == 0


def test_tts_credential_validation_closes_the_sample_stream(
    http_server: HTTPServerFactory,
    http_responses: tuple[list[HTTPResponse], Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses, _ready = http_responses
    server = http_server([Response(chunks=(b"sample", b"unused audio"))])
    model = OAICompatText2SpeechModel([])
    credentials = {"endpoint_url": server.url, "voices": "voice-1,voice-2"}
    stream = model._invoke("model", "validate", credentials, "Test.", "voice-1")
    monkeypatch.setattr(model, "_invoke", lambda **_kwargs: stream)

    model.validate_credentials("model", credentials)

    assert responses[0].raw.closed
    assert list(stream) == []
    assert json.loads(server.requests[0].body)["voice"] == "voice-1"


@pytest.mark.parametrize("validate", [False, True])
def test_tts_http_failure_closes_the_response(
    http_server: HTTPServerFactory,
    http_responses: tuple[list[HTTPResponse], Event],
    validate: bool,
) -> None:
    responses, _ready = http_responses
    server = http_server([Response(status=401, body=b"invalid API key")])
    model = OAICompatText2SpeechModel([])
    credentials = {"endpoint_url": server.url}
    if validate:
        with pytest.raises(CredentialsValidateFailedError, match="invalid API key"):
            model.validate_credentials("model", credentials)
    else:
        with pytest.raises(InvokeError, match="invalid API key"):
            list(model.invoke("model", "tenant", credentials, "Hello", "alloy"))

    assert responses[0].raw.closed
    assert model.started_at == 0


@pytest.mark.parametrize(
    ("voices", "expected"),
    [
        (" alloy, , echo ", ["alloy", "echo"]),
        (" , ", ["alloy"]),
    ],
)
def test_tts_voice_choices_match_credential_configuration(
    voices: str, expected: list[str]
) -> None:
    model = OAICompatText2SpeechModel([])
    choices = model.get_tts_model_voices("model", {"voices": voices})
    assert [choice["value"] for choice in choices] == expected


def test_speech_to_text_sends_multipart_without_closing_the_callers_file(
    http_server: HTTPServerFactory, tmp_path: Path
) -> None:
    audio = b"RIFF\x00\xffWAVEaudio"
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(audio)
    server = http_server([Response(body='{"text":"你好"}'.encode())])
    model = OAICompatSpeech2TextModel([])

    with audio_path.open("rb") as audio_file:
        result = model.invoke(
            "model",
            {
                "endpoint_url": f"{server.url}/v1/",
                "api_key": "key",
                "endpoint_model_name": "upstream-stt",
            },
            audio_file,
        )
        assert not audio_file.closed

    assert result == "你好"
    assert model.started_at == 0
    request = server.requests[0]
    assert request.path == "/v1/audio/transcriptions"
    assert request.headers["Authorization"] == "Bearer key"
    multipart = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: "
        + request.headers["Content-Type"].encode()
        + b"\r\n\r\n"
        + request.body
    )
    fields = {
        part.get_param("name", header="content-disposition"): part
        for part in multipart.iter_parts()
    }
    assert fields["model"].get_payload(decode=True) == b"upstream-stt"
    assert fields["file"].get_filename() == "audio.wav"
    assert fields["file"].get_payload(decode=True) == audio


@pytest.mark.parametrize(
    "response",
    [
        Response(status=503, body=b"upstream unavailable"),
        Response(body=b"not json"),
        Response(body=b"{}"),
    ],
)
def test_speech_to_text_errors_preserve_file_ownership_and_timing(
    http_server: HTTPServerFactory, tmp_path: Path, response: Response
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"audio")
    server = http_server([response])
    model = OAICompatSpeech2TextModel([])
    with audio_path.open("rb") as audio_file:
        with pytest.raises(InvokeError):
            model.invoke("model", {"endpoint_url": server.url}, audio_file)
        assert not audio_file.closed
    assert model.started_at == 0


@pytest.mark.parametrize("status", [200, 401])
def test_speech_to_text_validates_credentials_with_sample_audio(
    http_server: HTTPServerFactory,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"sample audio")
    server = http_server([Response(status=status, body=b'{"text":"sample"}')])
    model = OAICompatSpeech2TextModel([])
    monkeypatch.setattr(model, "_get_demo_file_path", lambda: str(audio_path))
    if status == 200:
        model.validate_credentials("model", {"endpoint_url": server.url})
    else:
        with pytest.raises(CredentialsValidateFailedError):
            model.validate_credentials("model", {"endpoint_url": server.url})
    assert b"sample audio" in server.requests[0].body
