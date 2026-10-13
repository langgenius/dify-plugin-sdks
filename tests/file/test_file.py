from pathlib import Path

import httpx
import pytest

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.file import file as file_module
from dify_plugin.file.entities import FileType
from dify_plugin.file.file import File
from tests.http_server import HTTPServerFactory, Response

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("content", [b"", b"\x00\xff\x80binary", "你好".encode()])
def test_download_preserves_bytes_and_caches_empty_files(
    http_server: HTTPServerFactory, content: bytes
) -> None:
    server = http_server([Response(body=content)])
    path = "/files/document?timestamp=1&nonce=n&sign=a%2Fb%2Bc"
    file = File(url=server.url + path, type=FileType.DOCUMENT)

    assert file.blob == content
    assert file.blob == content
    assert len(server.requests) == 1
    assert server.requests[0].method == "GET"
    assert server.requests[0].path == path


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500])
def test_failed_download_can_be_retried_without_caching_the_error(
    http_server: HTTPServerFactory, status: int
) -> None:
    server = http_server([
        Response(status=status, body=b"failed"),
        Response(body=b"recovered"),
    ])
    file = File(url=server.url + "/file", type=FileType.IMAGE)

    with pytest.raises(httpx.HTTPStatusError) as exc:
        _ = file.blob
    assert exc.value.response.status_code == status
    assert file.blob == b"recovered"
    assert len(server.requests) == 2


@pytest.mark.parametrize("url", ["/files/relative", "ftp://example.com/file"])
def test_download_explains_unsupported_url_configuration(url: str) -> None:
    file = File(url=url, type=FileType.DOCUMENT)

    with pytest.raises(ValueError, match="FILES_URL") as exc:
        _ = file.blob
    assert isinstance(exc.value.__cause__, httpx.UnsupportedProtocol)


def test_download_rejects_a_truncated_body(http_server: HTTPServerFactory) -> None:
    server = http_server([Response(headers={"Content-Length": "20"}, body=b"short")])
    file = File(url=server.url + "/file", type=FileType.AUDIO)

    with pytest.raises(httpx.RemoteProtocolError):
        _ = file.blob


def test_download_follows_relative_redirect_and_caches_bytes(
    http_server: HTTPServerFactory,
) -> None:
    content = b"\x00\xffredirected"
    server = http_server([
        Response(status=302, headers={"Location": "../file?sign=a%2Fb"}),
        Response(body=content),
    ])
    file = File(url=server.url + "/redirect/start", type=FileType.DOCUMENT)

    assert file.blob == content
    assert file.blob == content
    assert [request.path for request in server.requests] == [
        "/redirect/start",
        "/file?sign=a%2Fb",
    ]


def test_download_honors_configured_read_timeout(
    http_server: HTTPServerFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = http_server([Response(body=b"late", delay=2)])
    monkeypatch.setattr(file_module, "_plugin_config", DifyPluginEnv(HTTPX_TIMEOUT=1))
    file = File(url=server.url + "/file", type=FileType.VIDEO)

    with pytest.raises(httpx.ReadTimeout):
        _ = file.blob


def test_download_uses_configured_http_proxy(
    http_server: HTTPServerFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    proxy = http_server([Response(body=b"proxied")])
    monkeypatch.setenv("HTTP_PROXY", proxy.url)
    url = "http://files.invalid/file?timestamp=1&sign=a%2Fb"

    assert File(url=url, type=FileType.DOCUMENT).blob == b"proxied"
    assert len(proxy.requests) == 1
    assert proxy.requests[0].path == url


def test_download_rejects_untrusted_tls(http_server: HTTPServerFactory) -> None:
    server = http_server([Response(body=b"secure")], tls=True)
    file = File(
        url=server.url.replace("127.0.0.1", "localhost"), type=FileType.DOCUMENT
    )

    with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
        _ = file.blob
    assert server.requests == []


@pytest.mark.parametrize("matching_hostname", [True, False])
def test_download_honors_custom_ca_and_verifies_hostname(
    http_server: HTTPServerFactory,
    monkeypatch: pytest.MonkeyPatch,
    matching_hostname: bool,
) -> None:
    cert = Path(__file__).parents[1] / "fixtures" / "certs" / "localhost.pem"
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    server = http_server([Response(body=b"secure")], tls=True)
    url = (
        server.url.replace("127.0.0.1", "localhost")
        if matching_hostname
        else server.url
    )
    file = File(url=url, type=FileType.DOCUMENT)

    if matching_hostname:
        assert file.blob == b"secure"
        assert len(server.requests) == 1
    else:
        with pytest.raises(httpx.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
            _ = file.blob
        assert server.requests == []
