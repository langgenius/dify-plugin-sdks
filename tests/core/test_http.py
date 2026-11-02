from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from io import BytesIO
from pathlib import Path
from socket import socket

import gevent
import httpx
import httpx2
import pytest
import requests
from gevent.event import Event
from werkzeug.wrappers import Request as ServerRequest
from werkzeug.wrappers import Response as ServerResponse

from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation, Session
from dify_plugin.core.utils import http
from dify_plugin.entities.model.message import UserPromptMessage
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
    def unexpected_transport(*_args: object, **_kwargs: object) -> None:
        pytest.fail("The SDK sent a request through an old HTTP transport")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", unexpected_transport)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", unexpected_transport)
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
    with http.post(
        server.url, stream=True, timeout=(1, 0.05 if outcome == "timeout" else 2)
    ) as result:
        assert not clients[0].is_closed
        if outcome == "cancel":
            started = Event()

            def consume() -> None:
                started.set()
                list(result.iter_content(4))

            worker = gevent.spawn(consume)
            assert started.wait(timeout=1)
            worker.kill(timeout=1)
            assert worker.ready()
        elif outcome in {"truncated", "invalid_gzip", "timeout"}:
            error = {
                "truncated": requests.exceptions.ChunkedEncodingError,
                "invalid_gzip": requests.exceptions.ContentDecodingError,
                "timeout": requests.exceptions.ConnectionError,
            }[outcome]
            with pytest.raises(error):
                list(result.iter_content(4))
        elif outcome == "early_close":
            with closing(result.iter_content(4)) as stream:
                assert next(stream) == b"firs"
        else:
            assert b"".join(result.iter_content(4)) == b"firstsecond"
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
                with http.post(server.url_for("/"), stream=True, timeout=2):
                    pass
            else:
                with http.httpx_client() as client:
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


def test_raw_response_retains_undecoded_reads(
    http_server: HTTPServerFactory, clients: list[httpx2.Client]
) -> None:
    server = http_server([Response(chunks=(b"one", b"two"))])
    with http.post(server.url, stream=True, timeout=2) as response:
        assert response.raw.read(2) == b"on"
        assert response.raw.read(2) == b"et"
        assert response.raw.read() == b"wo"
    assert clients[0].is_closed


@pytest.mark.parametrize("use_proxy", [False, True])
def test_connection_failure_preserves_its_exception_type_and_releases_client(
    clients: list[httpx2.Client], use_proxy: bool
) -> None:
    with socket() as unused:
        unused.bind(("127.0.0.1", 0))
        url = f"http://127.0.0.1:{unused.getsockname()[1]}"
        error_type = (
            requests.exceptions.ProxyError if use_proxy else requests.ConnectionError
        )
        with pytest.raises(error_type) as error:
            http.post(
                "http://provider.invalid" if use_proxy else url,
                proxies={"http": url} if use_proxy else {},
                timeout=1,
            )
        assert error.value.request is not None
    assert len(clients) == 1
    assert clients[0].is_closed


def test_invalid_proxy_configuration_preserves_the_url_error() -> None:
    with pytest.raises(requests.exceptions.InvalidURL):
        http.post(
            "http://provider.invalid",
            proxies={"http": "unknown://proxy.invalid"},
            timeout=1,
        )


def test_invalid_proxy_environment_preserves_the_httpx_url_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_PROXY", "fc00::/7")
    with pytest.raises(httpx.InvalidURL):
        http.httpx_client()


def test_invalid_certificate_bundle_preserves_the_ssl_error(
    http_server: HTTPServerFactory, tmp_path: Path
) -> None:
    server = http_server([], tls=True)
    bundle = tmp_path / "invalid.pem"
    bundle.write_text("not a certificate")
    with pytest.raises(requests.exceptions.SSLError):
        http.post(server.url, verify=str(bundle), timeout=1)
    assert not server.requests
