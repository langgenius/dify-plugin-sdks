import gzip
import json
import ssl
import traceback
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from io import BytesIO
from pathlib import Path
from socket import socket

import gevent
import httpx2
import pytest
from gevent.event import Event
from werkzeug.wrappers import Request as ServerRequest
from werkzeug.wrappers import Response as ServerResponse

from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation, Session
from dify_plugin.core.server.io_server import IOServer
from dify_plugin.core.utils import http
from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError
from dify_plugin.file.entities import FileType
from dify_plugin.file.file import File
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)
from dify_plugin.interfaces.model.openai_compatible.rerank import OAICompatRerankModel
from dify_plugin.interfaces.model.openai_compatible.speech2text import (
    OAICompatSpeech2TextModel,
)
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)
from dify_plugin.interfaces.model.openai_compatible.tts import OAICompatText2SpeechModel
from dify_plugin.invocations.file import File as FileInvocation
from tests.http_server import HTTPServer, HTTPServerFactory, Response
from tests.servers.helpers import MemoryRequestReader, RecordingResponseWriter

pytestmark = pytest.mark.integration


@pytest.fixture
def clients(monkeypatch: pytest.MonkeyPatch) -> list[httpx2.Client]:
    clients = []
    client_type = httpx2.Client

    def create(*args: object, **kwargs: object) -> httpx2.Client:
        client = client_type(*args, **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(httpx2, "Client", create)
    return clients


def test_every_sdk_http_operation_uses_httpx2(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    clients: list[httpx2.Client],
) -> None:
    server = http_server([
        Response(
            body=b'{"choices":[{"message":{"content":"answer"}}],"usage":{"prompt_tokens":0,"completion_tokens":0}}'
        ),
        Response(body=b'{"object":"chat.completion"}'),
        Response(body=b'{"data":[{"embedding":[1,2]}],"usage":{"total_tokens":1}}'),
        Response(body=b'{"model":"model"}'),
        Response(body=b'{"results":[{"index":0,"relevance_score":1}]}'),
        Response(body=b"audio"),
        Response(body=b'{"text":"transcribed"}'),
        Response(
            status=201,
            body=b'{"id":"file","name":"test.txt","size":4,"extension":"txt","mime_type":"text/plain"}',
        ),
        Response(body=b"downloaded"),
        Response(
            body=b'{"session_id":"session","event":"backwards_response","data":{"backwards_request_id":"request","event":"end","message":"","data":null}}\n'
        ),
    ])
    credentials = {"endpoint_url": server.url, "mode": "chat"}
    model = OAICompatLargeLanguageModel([])
    chunks = list(
        model.invoke(
            "model", credentials, [UserPromptMessage(content="Question")], stream=False
        )
    )
    assert chunks[0].delta.message.content == "answer"
    model.validate_credentials("model", credentials)
    embeddings = OAICompatEmbeddingModel([])
    monkeypatch.setattr(embeddings, "_get_num_tokens_by_gpt2", len)
    assert embeddings.invoke("model", credentials, ["text"]).embeddings == [[1, 2]]
    embeddings.validate_credentials("model", credentials)
    assert (
        OAICompatRerankModel([])
        .invoke("model", credentials, "query", ["doc"])
        .docs[0]
        .text
        == "doc"
    )
    assert (
        b"".join(
            OAICompatText2SpeechModel([]).invoke(
                "model", "tenant", credentials, "text", "alloy"
            )
        )
        == b"audio"
    )
    with BytesIO(b"audio") as audio:
        assert (
            OAICompatSpeech2TextModel([]).invoke("model", credentials, audio)
            == "transcribed"
        )
    upload = FileInvocation()
    monkeypatch.setattr(
        upload,
        "_backwards_invoke",
        lambda *_args: iter([{"url": server.url + "/upload"}]),
    )
    assert upload.upload("test.txt", b"test", "text/plain").id == "file"
    assert File(url=server.url + "/file", type=FileType.DOCUMENT).blob == b"downloaded"
    reader = MemoryRequestReader()
    with ThreadPoolExecutor(max_workers=1) as executor:
        session = Session(
            session_id="session",
            executor=executor,
            reader=reader,
            writer=RecordingResponseWriter(),
            install_method=InstallMethod.Serverless,
            dify_plugin_daemon_url=server.url,
            max_invocation_timeout=2,
        )
        try:
            invocation = BackwardsInvocation[dict](session)
            assert (
                list(
                    invocation._http_backwards_invoke(
                        "request", InvokeType.Storage, dict, {}
                    )
                )
                == []
            )
        finally:
            reader.close()
    assert len(server.requests) == 10
    assert len(clients) == 10
    assert all(client.is_closed for client in clients)


@pytest.mark.parametrize(
    "outcome",
    ["complete", "early_close", "truncated", "invalid_gzip", "timeout", "cancel"],
)
def test_provider_stream_owns_its_client_until_consumed_or_closed(
    http_server: HTTPServerFactory, clients: list[httpx2.Client], outcome: str
) -> None:
    response = Response(chunks=(b"first", b"second"))
    if outcome == "truncated":
        response = Response(headers={"Content-Length": "30"}, body=b"short")
    elif outcome == "invalid_gzip":
        response = Response(headers={"Content-Encoding": "gzip"}, body=b"not gzip")
    elif outcome in {"timeout", "cancel"}:
        response = Response(chunks=(b"delayed",), delay=5)
    server = http_server([response])
    with (
        http.client() as client,
        client.stream(
            "POST",
            server.url,
            timeout=httpx2.Timeout(0.05 if outcome == "timeout" else 2, connect=1),
        ) as result,
    ):
        assert not clients[0].is_closed
        if outcome == "cancel":
            started = Event()

            def consume() -> None:
                started.set()
                list(result.iter_bytes(4))

            worker = gevent.spawn(consume)
            assert started.wait(timeout=1)
            worker.kill(timeout=1)
            assert worker.ready()
        elif outcome in {"truncated", "invalid_gzip", "timeout"}:
            error = {
                "truncated": httpx2.RemoteProtocolError,
                "invalid_gzip": httpx2.DecodingError,
                "timeout": httpx2.ReadTimeout,
            }[outcome]
            with pytest.raises(error):
                list(result.iter_bytes(4))
        elif outcome == "early_close":
            with closing(result.iter_bytes(4)) as stream:
                assert next(stream) == b"firs"
        else:
            assert b"".join(result.iter_bytes(4)) == b"firstsecond"
    assert clients[0].is_closed


@pytest.mark.parametrize("kind", ["provider", "runtime"])
def test_cancelling_before_response_headers_closes_the_client(
    clients: list[httpx2.Client], kind: str
) -> None:
    received = Event()
    finish = Event()

    def respond(_request: ServerRequest) -> ServerResponse:
        received.set()
        finish.wait(timeout=5)
        return ServerResponse("finished")

    with HTTPServer(host="127.0.0.1", threaded=True) as server:
        server.expect_request("/").respond_with_handler(respond)

        def invoke() -> None:
            if kind == "provider":
                with (
                    http.client() as client,
                    client.stream("POST", server.url_for("/"), timeout=2),
                ):
                    pass
            else:
                with http.client() as client:
                    client.get(server.url_for("/"))

        worker = gevent.spawn(invoke)
        try:
            assert received.wait(timeout=2)
            worker.kill(timeout=1)
            assert worker.ready()
            assert clients[0].is_closed
        finally:
            finish.set()
            worker.kill(timeout=1)


def test_raw_response_retains_compressed_bytes(
    http_server: HTTPServerFactory, clients: list[httpx2.Client]
) -> None:
    body = gzip.compress(b"one two")
    server = http_server([Response(headers={"Content-Encoding": "gzip"}, body=body)])
    with http.client() as client, client.stream("GET", server.url) as response:
        assert b"".join(response.iter_raw()) == body
    assert clients[0].is_closed


@pytest.mark.parametrize("use_proxy", [False, True])
def test_connection_failure_carries_the_request_and_releases_client(
    clients: list[httpx2.Client], use_proxy: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    with socket() as unused:
        unused.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{unused.getsockname()[1]}"
        if use_proxy:
            monkeypatch.setenv("HTTP_PROXY", url)
        with pytest.raises(httpx2.ConnectError) as error, http.client() as client:
            client.get("http://provider.invalid" if use_proxy else url, timeout=1)
        assert error.value.request is not None
    assert len(clients) == 1
    assert clients[0].is_closed


def test_invalid_proxy_configuration_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTTP_PROXY", "unknown://proxy.invalid")
    with pytest.raises(ValueError, match="Unknown scheme"):
        http.client()


def test_ipv6_network_in_no_proxy_does_not_break_client_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_PROXY", "fc00::/7")
    with http.client() as client:
        assert isinstance(client, httpx2.Client)


def test_invalid_certificate_bundle_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = tmp_path / "invalid.pem"
    bundle.write_text("not a certificate")
    monkeypatch.setenv("SSL_CERT_FILE", str(bundle))
    with pytest.raises(ssl.SSLError):
        http.client()


@pytest.mark.parametrize("operation", ["invoke", "validate"])
@pytest.mark.parametrize("suffix", [" ", "\t", " \t"])
def test_header_whitespace_does_not_break_provider_calls(
    http_server: HTTPServerFactory, operation: str, suffix: str
) -> None:
    server = http_server([
        Response(
            body=b'{"object":"chat.completion","choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":0,"completion_tokens":0}}'
        )
    ])
    credentials = {
        "endpoint_url": server.url,
        "mode": "chat",
        "api_key": "synthetic-key" + suffix,
    }
    model = OAICompatLargeLanguageModel([])
    if operation == "validate":
        model.validate_credentials("model", credentials)
    else:
        chunks = list(model.invoke("model", credentials, [], stream=False))
        assert chunks[0].delta.message.content == "ok"
    assert server.requests[0].headers["Authorization"] == "Bearer synthetic-key"


@pytest.mark.parametrize("operation", ["invoke", "validate"])
@pytest.mark.parametrize("field", ["api_key", "extra_header", "header_name"])
@pytest.mark.parametrize("invalid", ["\r\nInjected: yes", "\x00", "\u4e2d"])
def test_invalid_headers_never_expose_credentials_in_errors_or_wire_output(
    http_server: HTTPServerFactory,
    operation: str,
    field: str,
    invalid: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "synthetic-key-do-not-log"  # ruff: ignore[hardcoded-password-string]
    server = http_server([])
    credentials = {"endpoint_url": server.url, "mode": "chat"}
    if field == "api_key":
        credentials["api_key"] = secret + invalid
    elif field == "extra_header":
        credentials["extra_headers"] = {"X-Secret": secret + invalid}
    else:
        credentials["extra_headers"] = {secret + invalid: "value"}
    model = OAICompatLargeLanguageModel([])

    def invoke() -> None:
        if operation == "validate":
            model.validate_credentials("model", credentials)
        else:
            list(model.invoke("model", credentials, [], stream=False))

    with pytest.raises((InvokeError, CredentialsValidateFailedError)) as caught:
        invoke()
    assert secret not in str(caught.value)
    assert secret not in "".join(traceback.format_exception(caught.value))
    writer = RecordingResponseWriter()

    class Dispatch(IOServer):
        def _execute_request(self, *_args: object) -> None:
            invoke()

    # Exercise the real serialization boundary without starting a server.
    dispatch = object.__new__(Dispatch)
    dispatch._execute_request_in_thread("headers", {}, None, writer)
    assert secret not in json.dumps(writer.messages)
    assert secret not in caplog.text
    assert not server.requests


def test_empty_file_get_has_no_transfer_encoding(
    http_server: HTTPServerFactory,
) -> None:
    server = http_server([Response(body=b"download")])
    assert File(url=server.url, type=FileType.DOCUMENT).blob == b"download"
    assert "Transfer-Encoding" not in server.requests[0].headers
    assert server.requests[0].body == b""
