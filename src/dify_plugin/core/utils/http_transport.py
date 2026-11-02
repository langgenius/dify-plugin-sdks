"""HTTPX2 transport with SOCKS routing and cancellation-safe TLS connections."""

import ipaddress
import socket
import ssl
from collections.abc import Generator, Iterable, Iterator
from contextlib import contextmanager
from typing import cast

import gevent
import httpcore2
import httpx2
import socksio
from httpcore2._backends.sync import SyncStream  # ruff: ignore[import-private-name]

_SOCKS_AUTH_LIMIT = 255


@contextmanager
def _httpx_errors() -> Generator[None]:
    try:
        yield
    except (
        httpcore2.TimeoutException,
        httpcore2.NetworkError,
        httpcore2.ProtocolError,
        httpcore2.ProxyError,
        httpcore2.UnsupportedProtocol,
    ) as error:
        raise getattr(httpx2, type(error).__name__)(str(error)) from error


class _ResponseStream(httpx2.SyncByteStream):
    def __init__(self, response: httpcore2.Response) -> None:
        self.response = response

    def __iter__(self) -> Iterator[bytes]:
        with _httpx_errors():
            yield from self.response.iter_stream()

    def close(self) -> None:
        with _httpx_errors():
            self.response.close()


class _NetworkStream(SyncStream):
    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore2.NetworkStream:
        sock = self.get_extra_info("socket")
        try:  # ruff: ignore[too-many-statements-in-try-clause]
            if isinstance(sock, ssl.SSLSocket):
                return super().start_tls(ssl_context, server_hostname, timeout)
            sock.settimeout(timeout)
            secure = ssl_context.wrap_socket(
                sock, server_hostname=server_hostname, do_handshake_on_connect=False
            )
            try:
                # Acquire the new socket before a handshake can yield to cancellation.
                secure.do_handshake()
            except BaseException:
                secure.close()
                raise
            return _NetworkStream(secure)
        except TimeoutError as error:
            self.close()
            raise httpcore2.ConnectTimeout(str(error)) from error
        except OSError as error:
            self.close()
            raise httpcore2.ConnectError(str(error)) from error
        except BaseException:
            self.close()
            raise


class _NetworkBackend(httpcore2.SyncBackend):
    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore2.SOCKET_OPTION] | None = None,
    ) -> httpcore2.NetworkStream:
        stream = super().connect_tcp(host, port, timeout, local_address, socket_options)
        return _NetworkStream(stream.get_extra_info("socket"))


class _SocksBackend(_NetworkBackend):
    def __init__(self, proxy: httpx2.URL) -> None:
        self.proxy = proxy

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[httpcore2.SOCKET_OPTION] | None = None,
    ) -> httpcore2.NetworkStream:
        stream = super().connect_tcp(
            self.proxy.raw_host.decode("ascii"),
            self.proxy.port or 1080,
            timeout,
            local_address,
            socket_options,
        )
        try:
            with gevent.Timeout(
                timeout, httpcore2.ConnectTimeout("SOCKS handshake timed out")
            ):
                self._connect(stream, host, port, timeout)
        except (httpcore2.ReadTimeout, httpcore2.WriteTimeout) as error:
            stream.close()
            msg = "SOCKS handshake timed out"
            raise httpcore2.ConnectTimeout(msg) from error
        except (OSError, socksio.SOCKSError) as error:
            stream.close()
            msg = "SOCKS proxy connection failed"
            raise httpcore2.ProxyError(msg) from error
        except BaseException:
            stream.close()
            raise
        return stream

    def _connect(
        self,
        stream: httpcore2.NetworkStream,
        host: str,
        port: int,
        timeout: float | None,
    ) -> None:
        version4 = self.proxy.scheme in {"socks4", "socks4a"}
        if self.proxy.scheme in {"socks4", "socks5"}:
            family = socket.AF_INET if version4 else socket.AF_UNSPEC
            host = cast(
                "str",
                socket.getaddrinfo(host, port, family, socket.SOCK_STREAM)[0][4][0],
            )
        if version4:
            self._connect4(stream, host, port, timeout)
        else:
            self._connect5(stream, host, port, timeout)

    @staticmethod
    def _read(
        stream: httpcore2.NetworkStream, size: int, timeout: float | None
    ) -> bytes:
        data = bytearray()
        while len(data) < size:
            chunk = stream.read(size - len(data), timeout)
            if not chunk:
                msg = "SOCKS proxy closed the connection during its handshake"
                raise httpcore2.ProxyError(msg)
            data.extend(chunk)
        return bytes(data)

    def _connect4(
        self,
        stream: httpcore2.NetworkStream,
        host: str,
        port: int,
        timeout: float | None,
    ) -> None:
        try:
            ipaddress.ip_address(host)
            request_type = socksio.SOCKS4Request
        except ValueError:
            request_type = socksio.SOCKS4ARequest
        if "\0" in self.proxy.username:
            msg = "SOCKS4 user IDs cannot contain null bytes"
            raise httpcore2.ProxyError(msg)
        request = request_type.from_address(
            socksio.SOCKS4Command.CONNECT,
            (host, port),
            user_id=self.proxy.username.encode(),
        )
        stream.write(request.dumps(), timeout)
        reply = socksio.SOCKS4Reply.loads(self._read(stream, 8, timeout))
        if reply.reply_code != socksio.SOCKS4ReplyCode.REQUEST_GRANTED:
            msg = "SOCKS4 proxy rejected the connection"
            raise httpcore2.ProxyError(msg)

    def _connect5(
        self,
        stream: httpcore2.NetworkStream,
        host: str,
        port: int,
        timeout: float | None,
    ) -> None:
        methods = [socksio.SOCKS5AuthMethod.NO_AUTH_REQUIRED]
        if self.proxy.userinfo:
            methods.append(socksio.SOCKS5AuthMethod.USERNAME_PASSWORD)
        stream.write(socksio.SOCKS5AuthMethodsRequest(methods).dumps(), timeout)
        reply = self._read(stream, 2, timeout)
        if reply[:1] != b"\x05" or reply[1:] not in methods:
            msg = "SOCKS5 proxy rejected the authentication methods"
            raise httpcore2.ProxyError(msg)
        if reply[1:] == socksio.SOCKS5AuthMethod.USERNAME_PASSWORD:
            username, password = (
                self.proxy.username.encode(),
                self.proxy.password.encode(),
            )
            if len(username) > _SOCKS_AUTH_LIMIT or len(password) > _SOCKS_AUTH_LIMIT:
                msg = "SOCKS5 credentials exceed the protocol's length limit"
                raise httpcore2.ProxyError(msg)
            stream.write(
                socksio.SOCKS5UsernamePasswordRequest(username, password).dumps(),
                timeout,
            )
            if self._read(stream, 2, timeout) != b"\x01\x00":
                msg = "SOCKS5 proxy rejected the credentials"
                raise httpcore2.ProxyError(msg)
        stream.write(
            socksio.SOCKS5CommandRequest.from_address(
                socksio.SOCKS5Command.CONNECT, (host, port)
            ).dumps(),
            timeout,
        )
        reply = self._read(stream, 4, timeout)
        if reply[:3] != b"\x05\x00\x00":
            msg = "SOCKS5 proxy rejected the connection"
            raise httpcore2.ProxyError(msg)
        if reply[3:] == socksio.SOCKS5AType.IPV4_ADDRESS:
            size = 4
        elif reply[3:] == socksio.SOCKS5AType.IPV6_ADDRESS:
            size = 16
        elif reply[3:] == socksio.SOCKS5AType.DOMAIN_NAME:
            size = self._read(stream, 1, timeout)[0]
        else:
            msg = "SOCKS5 proxy returned an invalid address type"
            raise httpcore2.ProxyError(msg)
        self._read(stream, size + 2, timeout)


class Transport(httpx2.BaseTransport):
    def __init__(
        self, context: ssl.SSLContext, proxy: httpx2.URL | None = None
    ) -> None:
        limits = httpx2.Limits()
        backend: httpcore2.NetworkBackend = _NetworkBackend()
        core_proxy = None
        if proxy is not None:
            if proxy.scheme in {"socks4", "socks4a", "socks5", "socks5h"}:
                backend = _SocksBackend(proxy)
            else:
                settings = httpx2.Proxy(proxy)
                core_proxy = httpcore2.Proxy(
                    url=str(settings.url),
                    auth=settings.raw_auth,
                    ssl_context=context if proxy.scheme == "https" else None,
                )
        self.pool = httpcore2.ConnectionPool(
            ssl_context=context,
            proxy=core_proxy,
            network_backend=backend,
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
        )

    def handle_request(self, request: httpx2.Request) -> httpx2.Response:
        native = httpcore2.Request(
            method=request.method,
            url=httpcore2.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        with _httpx_errors():
            response = self.pool.handle_request(native)
        return httpx2.Response(
            response.status,
            headers=response.headers,
            stream=_ResponseStream(response),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self.pool.close()
