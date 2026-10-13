import os
import re
import ssl
from collections.abc import Generator
from contextlib import ExitStack
from pathlib import Path
from threading import Event

import pytest
from werkzeug.wrappers import Request as HTTPRequest
from werkzeug.wrappers import Response as HTTPResponse

from tests.http_server import (
    HTTPServer,
    HTTPServerFactory,
    Request,
    Response,
    TestHTTPServer,
)


@pytest.fixture(autouse=True)
def isolated_http_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    for name in (
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NETRC", os.devnull)


@pytest.fixture
def http_server() -> Generator[HTTPServerFactory]:
    stopped = Event()
    servers: list[HTTPServer] = []
    with ExitStack() as stack:

        def start(responses: list[Response], *, tls: bool = False) -> TestHTTPServer:
            context = None
            if tls:
                certs = Path(__file__).parent / "fixtures" / "certs"
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(
                    certs / "localhost.pem", certs / "localhost-key.pem"
                )
            server = stack.enter_context(
                HTTPServer(host="127.0.0.1", threaded=True, ssl_context=context)
            )
            servers.append(server)
            captured = TestHTTPServer(server.url_for("/").rstrip("/"))
            for response in responses:

                def respond(
                    request: HTTPRequest, response: Response = response
                ) -> HTTPResponse:
                    captured.requests.append(
                        Request(
                            request.method,
                            request.environ["RAW_URI"],
                            request.headers,
                            request.get_data(),
                        )
                    )
                    headers = dict(response.headers)
                    if response.chunks is None:
                        headers.setdefault("Content-Length", str(len(response.body)))
                    return HTTPResponse(
                        response.stream(stopped),
                        status=response.status,
                        headers=headers,
                    )

                server.expect_ordered_request(re.compile(r".*")).respond_with_handler(
                    respond
                )
            return captured

        try:
            yield start
            for server in servers:
                server.check()
        finally:
            stopped.set()
