import base64
import gzip
import json
import zlib
from collections.abc import Iterator
from email import policy
from email.parser import BytesParser
from io import BytesIO
from pathlib import Path
from threading import Event

import gevent
import pytest
import requests
import trustme

from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.errors.model import InvokeServerUnavailableError
from dify_plugin.interfaces.model.openai_compatible import llm
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)
from dify_plugin.interfaces.model.openai_compatible.speech2text import (
    OAICompatSpeech2TextModel,
)
from tests.http_server import HTTPServerFactory, Response

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_provider_response_retains_redirect_cookies_and_request_metadata(
    http_server: HTTPServerFactory, status: int
) -> None:
    server = http_server([
        Response(
            status=status,
            headers={
                "Location": "/next?signature=a%2Fb",
                "Set-Cookie": "route=one; Path=/",
            },
        ),
        Response(
            headers={"Content-Encoding": "gzip", "Set-Cookie": "result=two"},
            body=gzip.compress(b'{"object":"chat.completion"}'),
        ),
    ])
    response, stream, _mode = (
        OAICompatLargeLanguageModel([])._request_credentials_validation(
            "model", {"endpoint_url": server.url, "mode": "chat", "api_key": "key"}
        )
    )
    with response:
        assert isinstance(response, requests.Response)
        assert not stream
        assert response.ok
        assert response.json() == {"object": "chat.completion"}
        assert response.url == server.url + "/next?signature=a%2Fb"
        assert response.cookies["result"] == "two"
        assert len(response.history) == 1
        assert response.history[0].status_code == status
        assert response.history[0].cookies["route"] == "one"
        assert response.request.method == ("POST" if status in {307, 308} else "GET")
        assert response.elapsed.total_seconds() >= 0

    first, redirected = server.requests
    assert redirected.headers["Cookie"] == "route=one"
    assert redirected.headers["Authorization"] == "Bearer key"
    assert redirected.method == ("POST" if status in {307, 308} else "GET")
    assert redirected.body == (first.body if status in {307, 308} else b"")


def test_provider_redirect_does_not_forward_credentials_to_another_origin(
    http_server: HTTPServerFactory,
) -> None:
    destination = http_server([Response(body=b"{}")])
    origin = http_server([
        Response(status=307, headers={"Location": destination.url + "/completion"})
    ])
    response, _stream, _mode = (
        OAICompatLargeLanguageModel([])._request_credentials_validation(
            "model", {"endpoint_url": origin.url, "mode": "chat", "api_key": "secret"}
        )
    )
    response.close()
    assert origin.requests[0].headers["Authorization"] == "Bearer secret"
    assert "Authorization" not in destination.requests[0].headers


def test_provider_preserves_netrc_authentication(
    http_server: HTTPServerFactory, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = http_server([Response(body=b"{}")])
    netrc = tmp_path / "netrc"
    netrc.write_text("machine 127.0.0.1 login account password password\n")
    monkeypatch.setenv("NETRC", str(netrc))
    response, _stream, _mode = (
        OAICompatLargeLanguageModel([])._request_credentials_validation(
            "model", {"endpoint_url": server.url, "mode": "chat", "api_key": "key"}
        )
    )
    response.close()
    expected = base64.b64encode(b"account:password").decode()
    assert server.requests[0].headers["Authorization"] == f"Basic {expected}"


def test_provider_honors_no_proxy_ip_networks(
    http_server: HTTPServerFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = http_server([Response(body=b"{}")])
    proxy = http_server([])
    monkeypatch.setenv("HTTP_PROXY", proxy.url)
    monkeypatch.setenv("NO_PROXY", "127.0.0.0/8")
    response, _stream, _mode = (
        OAICompatLargeLanguageModel([])._request_credentials_validation(
            "model", {"endpoint_url": server.url, "mode": "chat"}
        )
    )
    response.close()
    assert len(server.requests) == 1
    assert not proxy.requests


@pytest.mark.parametrize("bundle", ["REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"])
@pytest.mark.parametrize("matching_hostname", [True, False])
def test_provider_preserves_ca_configuration_and_hostname_verification(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    tls_ca: trustme.CA,
    bundle: str,
    matching_hostname: bool,
) -> None:
    server = http_server([Response(body=b"{}")], tls=True)
    url = (
        server.url.replace("127.0.0.1", "localhost")
        if matching_hostname
        else server.url
    )
    with tls_ca.cert_pem.tempfile() as cert:
        monkeypatch.setenv(bundle, cert)
        if bundle == "REQUESTS_CA_BUNDLE":
            monkeypatch.setenv("CURL_CA_BUNDLE", "/missing/fallback-ca.pem")
        model = OAICompatLargeLanguageModel([])
        if matching_hostname:
            response, _stream, _mode = model._request_credentials_validation(
                "model", {"endpoint_url": url, "mode": "chat"}
            )
            response.close()
            assert len(server.requests) == 1
        else:
            with pytest.raises(requests.exceptions.SSLError):
                model._request_credentials_validation(
                    "model", {"endpoint_url": url, "mode": "chat"}
                )
            assert not server.requests


def test_provider_does_not_expand_trust_from_httpx_certificate_configuration(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    tls_ca: trustme.CA,
) -> None:
    server = http_server([Response(body=b"{}")], tls=True)
    with tls_ca.cert_pem.tempfile() as cert:
        monkeypatch.setenv("SSL_CERT_FILE", cert)
        with pytest.raises(requests.exceptions.SSLError):
            OAICompatLargeLanguageModel([])._request_credentials_validation(
                "model",
                {
                    "endpoint_url": server.url.replace("127.0.0.1", "localhost"),
                    "mode": "chat",
                },
            )
    assert not server.requests


def test_provider_error_response_retains_requests_status_semantics(
    http_server: HTTPServerFactory,
) -> None:
    server = http_server([Response(status=429, body="稍后重试".encode())])
    response, _stream, _mode = (
        OAICompatLargeLanguageModel([])._request_credentials_validation(
            "model", {"endpoint_url": server.url, "mode": "chat"}
        )
    )
    with response:
        assert not response
        response.encoding = "utf-8"
        assert response.text == "稍后重试"
        with pytest.raises(requests.HTTPError) as error:
            response.raise_for_status()
        assert error.value.response is response
        assert error.value.request is response.request


@pytest.mark.parametrize("named", [True, False])
def test_transcription_reads_from_the_current_file_position(
    http_server: HTTPServerFactory, named: bool
) -> None:
    server = http_server([Response(body=b'{"text":"transcribed"}')])
    with BytesIO(b"skip audio payload") as audio:
        if named:
            audio.name = "/audio/recording.wav"
        audio.seek(5)
        result = OAICompatSpeech2TextModel([]).invoke(
            "model", {"endpoint_url": server.url}, audio
        )
        assert not audio.closed

    assert result == "transcribed"
    request = server.requests[0]
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode()
        + request.body
    )
    parts = {
        part.get_param("name", header="content-disposition"): part
        for part in message.iter_parts()
    }
    assert parts["file"].get_payload(decode=True) == b"audio payload"
    assert parts["file"].get_filename() == ("recording.wav" if named else "file")
    assert "Content-Type" not in parts["file"]


class GzipEventResponse(Response):
    def stream(self, stopped: Event) -> Iterator[bytes]:
        compressor = zlib.compressobj(wbits=31)
        event = json.dumps({"choices": [{"delta": {"content": "first"}}]}).encode()
        yield compressor.compress(b"data: " + event + b"\n\n") + compressor.flush(
            zlib.Z_SYNC_FLUSH
        )
        stopped.wait(5)
        yield compressor.compress(b"data: [DONE]\n\n") + compressor.flush()


def test_compressed_stream_yields_before_the_next_event_arrives(
    http_server: HTTPServerFactory,
) -> None:
    server = http_server([
        GzipEventResponse(
            headers={"Content-Encoding": "gzip", "Content-Type": "text/event-stream"},
            chunks=(),
        )
    ])
    stream = OAICompatLargeLanguageModel([]).invoke(
        "model",
        {"endpoint_url": server.url, "mode": "chat"},
        [UserPromptMessage(content="Question")],
    )
    try:
        with gevent.Timeout(2):
            assert next(stream).delta.message.content == "first"
    finally:
        stream.close()


def test_stream_timeout_preserves_the_public_model_error_category(
    http_server: HTTPServerFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = http_server([Response(chunks=(b"data: [DONE]\n\n",), delay=5)])
    monkeypatch.setattr(
        llm,
        "_plugin_config",
        llm._plugin_config.model_copy(update={"MAX_REQUEST_TIMEOUT": 0.05}),
    )
    with pytest.raises(InvokeServerUnavailableError):
        list(
            OAICompatLargeLanguageModel([]).invoke(
                "model",
                {"endpoint_url": server.url, "mode": "chat"},
                [UserPromptMessage(content="Question")],
            )
        )
