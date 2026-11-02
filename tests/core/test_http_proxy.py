import base64
import socket
import ssl
import subprocess  # ruff: ignore[suspicious-subprocess-import]
from collections.abc import Callable, Generator
from contextlib import ExitStack
from pathlib import Path
from typing import BinaryIO

import gevent
import httpx2
import pytest
import trustme
from gevent.event import Event
from gevent.server import StreamServer

from dify_plugin.core.utils import http
from dify_plugin.entities.model.message import UserPromptMessage
from dify_plugin.errors.model import InvokeConnectionError
from dify_plugin.file.entities import FileType
from dify_plugin.file.file import File
from dify_plugin.interfaces.model.openai_compatible import llm

pytestmark = pytest.mark.integration


@pytest.fixture
def tcp_peer() -> Generator[Callable[[Callable[[socket.socket], None]], int]]:
    errors = []
    with ExitStack() as stack:

        def start(handler: Callable[[socket.socket], None]) -> int:
            def handle(sock: socket.socket, _address: object) -> None:
                with sock:
                    sock.settimeout(3)
                    try:
                        handler(sock)
                    except Exception as error:
                        errors.append(error)

            server = StreamServer(("127.0.0.1", 0), handle)
            server.start()
            stack.callback(server.stop)
            return server.server_port

        yield start
    assert not errors


def read_null_terminated(stream: BinaryIO) -> bytes:
    data = bytearray()
    while char := stream.read(1):
        if char == b"\0":
            return bytes(data)
        data.extend(char)
    pytest.fail("SOCKS client disconnected mid-field")


def receive_http(stream: BinaryIO) -> tuple[bytes, dict[bytes, bytes]]:
    request = stream.readline()
    headers = {}
    while (line := stream.readline()) not in {b"\r\n", b""}:
        key, value = line.split(b":", 1)
        headers[key.lower()] = value.strip()
    stream.read(int(headers.get(b"content-length", b"0")))
    return request, headers


def respond(sock: socket.socket, body: bytes = b"ok") -> None:
    sock.sendall(
        b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: "
        + str(len(body)).encode()
        + b"\r\n\r\n"
        + body
    )


@pytest.mark.parametrize("scheme", ["socks4", "socks4a", "socks5", "socks5h"])
@pytest.mark.parametrize("authenticate", [False, True])
@pytest.mark.parametrize("tls", [False, True])
def test_socks_connects_with_authentication_dns_and_tls(
    tcp_peer: Callable,
    monkeypatch: pytest.MonkeyPatch,
    tls_ca: trustme.CA,
    scheme: str,
    authenticate: bool,
    tls: bool,
) -> None:
    remote_dns = scheme in {"socks4a", "socks5h"}
    hostname = "provider.invalid" if remote_dns else "localhost"
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_ca.issue_cert(hostname).configure_cert(context)
    received = []

    def handle(sock: socket.socket) -> None:
        with sock.makefile("rb") as stream:
            if scheme.startswith("socks4"):
                assert stream.read(2) == b"\x04\x01"
                assert int.from_bytes(stream.read(2)) == (443 if tls else 80)
                address = stream.read(4)
                assert read_null_terminated(stream) == (
                    b"us@er" if authenticate else b""
                )
                if remote_dns:
                    assert address[:3] == b"\0\0\0"
                    assert address[3] != 0
                    assert read_null_terminated(stream) == hostname.encode()
                else:
                    assert socket.inet_ntoa(address) == "127.0.0.1"
                reply = b"\0\x5a\0\x50\x7f\0\0\1"
            else:
                assert stream.read(1) == b"\x05"
                methods = stream.read(stream.read(1)[0])
                assert methods == (b"\0\x02" if authenticate else b"\0")
                sock.sendall(b"\x05\x02" if authenticate else b"\x05\0")
                if authenticate:
                    assert stream.read(1) == b"\x01"
                    assert stream.read(stream.read(1)[0]) == b"us@er"
                    assert stream.read(stream.read(1)[0]) == b"p@ss"
                    sock.sendall(b"\x01\0")
                assert stream.read(3) == b"\x05\x01\0"
                address_type = stream.read(1)
                if remote_dns:
                    assert address_type == b"\x03"
                    assert stream.read(stream.read(1)[0]) == hostname.encode()
                elif address_type == b"\x01":
                    assert socket.inet_ntoa(stream.read(4)) == "127.0.0.1"
                else:
                    assert address_type == b"\x04"
                    assert socket.inet_ntop(socket.AF_INET6, stream.read(16)) == "::1"
                assert int.from_bytes(stream.read(2)) == (443 if tls else 80)
                # Cover a bound-address domain; it is unrelated to target DNS.
                reply = (
                    (b"\x05\0\0\x04" + b"\0" * 16 + b"\0\x50")
                    if tls
                    else (
                        b"\x05\0\0\x03\x04peer\0\x50"
                        if authenticate
                        else b"\x05\0\0\x01\x7f\0\0\1\0\x50"
                    )
                )
            for byte in reply:
                sock.sendall(bytes([byte]))
                gevent.sleep(0)
        if tls:
            with context.wrap_socket(sock, server_side=True) as secure:
                with secure.makefile("rb") as stream:
                    received.append(receive_http(stream))
                respond(secure)
        else:
            with sock.makefile("rb") as stream:
                received.append(receive_http(stream))
            respond(sock)

    port = tcp_peer(handle)
    userinfo = "us%40er:p%40ss@" if authenticate else ""
    monkeypatch.setenv("ALL_PROXY", f"{scheme}://{userinfo}127.0.0.1:{port}")
    if remote_dns:
        resolve = socket.getaddrinfo

        def checked_resolve(host: str, *args: object, **kwargs: object) -> list:
            assert host != hostname, "A remote-DNS proxy must resolve the target"
            return resolve(host, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", checked_resolve)
    with tls_ca.cert_pem.tempfile() as cert:
        monkeypatch.setenv("SSL_CERT_FILE", cert)
        assert (
            File(
                url=f"{'https' if tls else 'http'}://{hostname}/file?sign=a%2Fb",
                type=FileType.DOCUMENT,
            ).blob
            == b"ok"
        )
    request, headers = received[0]
    assert request == b"GET /file?sign=a%2Fb HTTP/1.1\r\n"
    assert headers[b"host"] == hostname.encode()
    assert b"proxy-authorization" not in headers
    assert b"transfer-encoding" not in headers


@pytest.mark.parametrize("reply", [b"\x04\0", b"\x05\xff", b"\x05\x01", b"\x05", b""])
def test_socks_rejects_invalid_or_incomplete_negotiation(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch, reply: bytes
) -> None:
    def handle(sock: socket.socket) -> None:
        sock.recv(10)
        sock.sendall(reply)

    port = tcp_peer(handle)
    monkeypatch.setenv("ALL_PROXY", f"socks5h://127.0.0.1:{port}")
    with http.client() as client, pytest.raises(httpx2.ProxyError):
        client.get("http://provider.invalid", timeout=1)


@pytest.mark.parametrize(
    "outcome", ["reject_auth", "reject_connect", "bad_address", "timeout", "cancel"]
)
def test_socks_failures_close_the_connection(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    ready, closed = Event(), Event()

    def handle(sock: socket.socket) -> None:
        with sock.makefile("rb") as stream:
            assert stream.read(4) == b"\x05\x02\0\x02"
            ready.set()
            if outcome not in {"timeout", "cancel"}:
                sock.sendall(b"\x05\x02")
                assert stream.read(1) == b"\x01"
                stream.read(stream.read(1)[0])
                stream.read(stream.read(1)[0])
                sock.sendall(b"\x01\xff" if outcome == "reject_auth" else b"\x01\0")
                if outcome != "reject_auth":
                    assert stream.read(4) == b"\x05\x01\0\x03"
                    stream.read(stream.read(1)[0] + 2)
                    sock.sendall(
                        b"\x05\x05\0\x01"
                        if outcome == "reject_connect"
                        else b"\x05\0\0\xff"
                    )
            assert stream.read(1) == b""
            closed.set()

    port = tcp_peer(handle)
    monkeypatch.setenv("ALL_PROXY", f"socks5h://user:password@127.0.0.1:{port}")
    with http.client() as client:
        if outcome == "cancel":
            worker = gevent.spawn(client.get, "http://provider.invalid", timeout=2)
            assert ready.wait(timeout=1)
            worker.kill(timeout=1)
            assert worker.ready()
        else:
            error = httpx2.ConnectTimeout if outcome == "timeout" else httpx2.ProxyError
            with pytest.raises(error):
                client.get(
                    "http://provider.invalid",
                    timeout=0.05 if outcome == "timeout" else 1,
                )
        assert closed.wait(timeout=1)


@pytest.mark.parametrize("tls_proxy", [False, True])
@pytest.mark.parametrize("wrong_cert", [False, True])
def test_proxy_tunnel_verifies_target_with_distinct_ca_files(
    tcp_peer: Callable,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tls_proxy: bool,
    wrong_cert: bool,
) -> None:
    target_ca, proxy_ca = trustme.CA(), trustme.CA()
    target_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    target_ca.issue_cert("wrong.invalid" if wrong_cert else "localhost").configure_cert(
        target_context
    )
    proxy_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    proxy_ca.issue_cert("127.0.0.1").configure_cert(proxy_context)
    target_file = tmp_path / "target.pem"
    target_ca.cert_pem.write_to_path(target_file)
    ca_dir = tmp_path / "ca"
    ca_dir.mkdir()
    proxy_ca.cert_pem.write_to_path(ca_dir / "proxy.pem")
    subprocess.run(["openssl", "rehash", str(ca_dir)], check=True, capture_output=True)  # ruff: ignore[subprocess-without-shell-equals-true, start-process-with-partial-path]
    monkeypatch.setenv("SSL_CERT_FILE", str(target_file))
    monkeypatch.setenv("SSL_CERT_DIR", str(ca_dir))
    sni = []
    target_context.set_servername_callback(lambda _sock, name, _ctx: sni.append(name))

    def target(sock: socket.socket) -> None:
        try:
            with target_context.wrap_socket(sock, server_side=True) as secure:
                with secure.makefile("rb") as stream:
                    receive_http(stream)
                respond(secure)
        except ssl.SSLError:
            assert wrong_cert

    target_port = tcp_peer(target)

    def proxy(sock: socket.socket) -> None:
        with ExitStack() as stack:
            connection = (
                stack.enter_context(proxy_context.wrap_socket(sock, server_side=True))
                if tls_proxy
                else sock
            )
            with connection.makefile("rb") as stream:
                first, headers = receive_http(stream)
            assert first == f"CONNECT localhost.:{target_port} HTTP/1.1\r\n".encode()
            assert headers[b"proxy-authorization"] == b"Basic " + base64.b64encode(
                b"user:password"
            )
            connection.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            upstream = stack.enter_context(
                socket.create_connection(("127.0.0.1", target_port))
            )

            def copy(source: socket.socket, destination: socket.socket) -> None:
                try:
                    while data := source.recv(65536):
                        destination.sendall(data)
                except OSError:
                    pass

            forward = gevent.spawn(copy, connection, upstream)
            try:
                copy(upstream, connection)
            finally:
                forward.kill()

    port = tcp_peer(proxy)
    monkeypatch.setenv(
        "HTTPS_PROXY",
        f"{'https' if tls_proxy else 'http'}://user:password@127.0.0.1:{port}",
    )
    file = File(url=f"https://localhost.:{target_port}/file", type=FileType.DOCUMENT)
    if wrong_cert:
        with pytest.raises(httpx2.ConnectError, match="CERTIFICATE_VERIFY_FAILED"):
            _ = file.blob
    else:
        assert file.blob == b"ok"
    assert sni == ["localhost"]


def test_tls_handshake_timeout_is_a_model_connection_error(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    received = Event()

    def handle(sock: socket.socket) -> None:
        assert sock.recv(1) == b"\x16"
        received.set()
        while sock.recv(65536):
            pass

    port = tcp_peer(handle)
    client = http.client

    def quick_client() -> httpx2.Client:
        instance = client()
        instance.event_hooks["request"].append(
            lambda request: request.extensions["timeout"].update(connect=0.05)
        )
        return instance

    monkeypatch.setattr(http, "client", quick_client)
    with pytest.raises(InvokeConnectionError):
        list(
            llm.OAICompatLargeLanguageModel([]).invoke(
                "model",
                {"mode": "chat", "endpoint_url": f"https://127.0.0.1:{port}"},
                [UserPromptMessage(content="test")],
                stream=False,
            )
        )
    assert received.is_set()


@pytest.mark.parametrize("scheme", ["socks4", "socks4a"])
def test_socks4_rejection_is_a_proxy_error(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch, scheme: str
) -> None:
    def handle(sock: socket.socket) -> None:
        assert sock.recv(4096).startswith(b"\x04\x01")
        sock.sendall(b"\0\x5b\0\0\0\0\0\0")

    port = tcp_peer(handle)
    monkeypatch.setenv("ALL_PROXY", f"{scheme}://127.0.0.1:{port}")
    with http.client() as client, pytest.raises(httpx2.ProxyError, match="rejected"):
        client.get("http://127.0.0.1", timeout=1)


def test_socks_local_dns_failure_closes_connection(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch
) -> None:
    closed = Event()

    def handle(sock: socket.socket) -> None:
        assert sock.recv(1) == b""
        closed.set()

    port = tcp_peer(handle)
    resolve = socket.getaddrinfo

    def fail_target(host: str, *args: object, **kwargs: object) -> list:
        if host == "unresolved.invalid":
            raise socket.gaierror(socket.EAI_NONAME, "fixture unresolved")
        return resolve(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fail_target)
    monkeypatch.setenv("ALL_PROXY", f"socks5://127.0.0.1:{port}")
    with http.client() as client, pytest.raises(httpx2.ProxyError):
        client.get("http://unresolved.invalid", timeout=1)
    assert closed.wait(timeout=1)


@pytest.mark.parametrize(
    ("scheme", "credentials"),
    [("socks4a", "user%00id:secret"), ("socks5h", "u:" + "p" * 256)],
)
def test_invalid_socks_credentials_are_rejected_without_exposing_them(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch, scheme: str, credentials: str
) -> None:
    closed = Event()

    def handle(sock: socket.socket) -> None:
        if scheme == "socks5h":
            assert sock.recv(4) == b"\x05\x02\0\x02"
            sock.sendall(b"\x05\x02")
        assert sock.recv(1) == b""
        closed.set()

    port = tcp_peer(handle)
    monkeypatch.setenv("ALL_PROXY", f"{scheme}://{credentials}@127.0.0.1:{port}")
    with http.client() as client, pytest.raises(httpx2.ProxyError) as caught:
        client.get("http://provider.invalid", timeout=1)
    assert credentials not in str(caught.value)
    assert closed.wait(timeout=1)


@pytest.mark.parametrize(
    "route", ["direct", "http_proxy", "https_proxy", "proxy_tls", "socks"]
)
def test_tls_cancellation_closes_socket_while_exception_is_retained(
    tcp_peer: Callable, monkeypatch: pytest.MonkeyPatch, tls_ca: trustme.CA, route: str
) -> None:
    ready, closed = Event(), Event()
    errors = []
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls_ca.issue_cert("127.0.0.1").configure_cert(context)

    def handle(sock: socket.socket) -> None:
        with ExitStack() as stack:
            connection = (
                stack.enter_context(context.wrap_socket(sock, server_side=True))
                if route == "https_proxy"
                else sock
            )
            if route in {"http_proxy", "https_proxy"}:
                with connection.makefile("rb") as stream:
                    assert receive_http(stream)[0].startswith(b"CONNECT ")
                connection.sendall(b"HTTP/1.1 200 OK\r\n\r\n")
            elif route == "socks":
                with connection.makefile("rb") as stream:
                    assert stream.read(3) == b"\x05\x01\0"
                    connection.sendall(b"\x05\0")
                    assert stream.read(4) == b"\x05\x01\0\x03"
                    stream.read(stream.read(1)[0] + 2)
                    connection.sendall(b"\x05\0\0\x01\x7f\0\0\1\0\x50")
            assert connection.recv(4096).startswith(b"\x16")
            ready.set()
            while connection.recv(4096):
                pass
            closed.set()

    port = tcp_peer(handle)
    if route != "direct":
        scheme = (
            "https"
            if route in {"https_proxy", "proxy_tls"}
            else "socks5h"
            if route == "socks"
            else "http"
        )
        monkeypatch.setenv("HTTPS_PROXY", f"{scheme}://127.0.0.1:{port}")

    class Cancelled(BaseException):
        pass

    def invoke() -> None:
        host = f"127.0.0.1:{port}" if route == "direct" else "target.invalid"
        try:
            with http.client() as client:
                client.get(f"https://{host}/file", timeout=2)
        except Cancelled as error:
            errors.append(error)

    with tls_ca.cert_pem.tempfile() as cert:
        monkeypatch.setenv("SSL_CERT_FILE", cert)
        worker = gevent.spawn(invoke)
        try:
            assert ready.wait(timeout=1)
            worker.kill(Cancelled, timeout=1)
            assert errors
            assert errors[0].__traceback__ is not None
            assert closed.wait(timeout=1)
        finally:
            worker.kill(timeout=1)
