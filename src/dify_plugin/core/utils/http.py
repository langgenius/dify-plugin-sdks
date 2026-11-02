"""Synchronous HTTPX2 transport with the SDK's existing HTTP interfaces."""

import ssl
from base64 import b64encode
from collections.abc import Buffer, Generator, Iterator
from contextlib import ExitStack, contextmanager
from http.client import HTTPMessage
from io import BufferedReader, RawIOBase
from pathlib import Path
from typing import Any, cast

import httpx
import httpx2
import requests
import requests.certs
from httpx._utils import get_environment_proxies  # ruff: ignore[import-private-name]
from requests.adapters import BaseAdapter
from requests.cookies import extract_cookies_to_jar
from requests.structures import CaseInsensitiveDict
from requests.utils import (
    get_encoding_from_headers,
    prepend_scheme_if_needed,
    select_proxy,
)
from urllib3 import HTTPHeaderDict, HTTPResponse
from urllib3.exceptions import ProtocolError, ReadTimeoutError
from urllib3.exceptions import SSLError as UrllibSSLError
from urllib3.util.ssl_ import create_urllib3_context


def _is_ssl_error(error: BaseException | None) -> bool:
    while error is not None:
        if isinstance(error, ssl.SSLError):
            return True
        error = error.__cause__ or error.__context__
    return False


@contextmanager
def _requests_errors(
    request: requests.PreparedRequest, proxy_url: str | None
) -> Generator[None]:
    try:
        yield
    except (ssl.SSLError, httpx2.HTTPError, httpx2.InvalidURL) as error:
        if isinstance(error, httpx2.ProxyError) or (
            proxy_url
            and isinstance(error, (httpx2.ConnectError, httpx2.ConnectTimeout))
        ):
            error_type = requests.exceptions.ProxyError
        elif _is_ssl_error(error):
            error_type = requests.exceptions.SSLError
        elif isinstance(error, httpx2.ConnectTimeout):
            error_type = requests.exceptions.ConnectTimeout
        elif isinstance(error, httpx2.ReadTimeout):
            error_type = requests.exceptions.ReadTimeout
        elif isinstance(error, httpx2.InvalidURL):
            error_type = requests.exceptions.InvalidURL
        else:
            error_type = requests.exceptions.ConnectionError
        raise error_type(str(error), request=request) from error


class _ResponseBody(RawIOBase):
    def __init__(self, response: httpx2.Response, client: httpx2.Client) -> None:
        self.response = response
        self.client = client
        self.chunks = response.iter_raw()
        self.pending = b""
        self.msg = HTTPMessage()
        for name, value in response.headers.raw:
            self.msg[name.decode("ascii")] = value.decode("latin-1")

    def readable(self) -> bool:
        return True

    def isclosed(self) -> bool:
        return self.closed

    def readinto(self, buffer: Buffer, /) -> int:
        with memoryview(buffer).cast("B") as view:
            if not view:
                return 0
            try:
                while not self.pending:
                    self.pending = next(self.chunks, b"")
                    if not self.pending:
                        return 0
            except httpx2.ReadTimeout as error:
                # No urllib3 connection pool owns this response.
                raise ReadTimeoutError(
                    None,  # ty: ignore[invalid-argument-type]
                    str(self.response.url),
                    str(error),
                ) from error
            except httpx2.HTTPError as error:
                if _is_ssl_error(error):
                    raise UrllibSSLError(str(error)) from error
                raise ProtocolError(str(error)) from error
            length = min(len(view), len(self.pending))
            view[:length] = self.pending[:length]
            self.pending = self.pending[length:]
            return length

    def close(self) -> None:
        if not self.closed:
            try:
                self.response.close()
            finally:
                try:
                    self.client.close()
                finally:
                    super().close()


class _RequestsResponse(HTTPResponse):
    def stream(
        self, amt: int | None = 65536, decode_content: bool | None = None
    ) -> Generator[bytes]:
        # read1 preserves streaming latency after HTTPX2 removes HTTP chunk framing.
        if amt == 0:
            return
        try:
            while data := self.read1(amt, decode_content=decode_content):
                yield data
        finally:
            self.close()


class _RequestsTransport(BaseAdapter):
    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float | None, float | None] | None = None,
        verify: bool | str | None = True,
        cert: str | tuple[str, str] | None = None,
        proxies: dict[str, str] | None = None,
    ) -> requests.Response:
        del stream
        if request.url is None or request.method is None:
            msg = "An HTTP request must be prepared before sending"
            raise ValueError(msg)
        proxy_url = select_proxy(request.url, proxies or {})
        if proxy_url:
            proxy_url = prepend_scheme_if_needed(proxy_url, "http")
        with _requests_errors(request, proxy_url), ExitStack() as stack:
            context = create_urllib3_context(
                cert_reqs=ssl.CERT_REQUIRED if verify else ssl.CERT_NONE
            )
            if verify and (
                request.url.startswith("https:")
                or (proxy_url or "").startswith("https:")
            ):
                bundle = verify if isinstance(verify, str) else requests.certs.where()
                if Path(bundle).is_dir():
                    context.load_verify_locations(capath=bundle)
                else:
                    context.load_verify_locations(cafile=bundle)
            if cert:
                context.load_cert_chain(*(cert if isinstance(cert, tuple) else (cert,)))
            proxy = None
            if proxy_url:
                try:
                    proxy = httpx2.Proxy(
                        proxy_url,
                        ssl_context=context if proxy_url.startswith("https:") else None,
                    )
                except ValueError as error:
                    raise requests.exceptions.InvalidURL(
                        str(error), request=request
                    ) from error
                if proxy.auth and proxy.auth[0]:
                    credentials = b":".join(
                        part.encode("latin-1") for part in proxy.auth
                    )
                    proxy.headers["Proxy-Authorization"] = (
                        f"Basic {b64encode(credentials).decode('ascii')}"
                    )
                proxy.auth = None
            connect, read = (
                timeout if isinstance(timeout, tuple) else (timeout, timeout)
            )
            client = stack.enter_context(
                httpx2.Client(
                    verify=context,
                    proxy=proxy,
                    timeout=httpx2.Timeout(
                        None, connect=connect, read=read, write=connect
                    ),
                    trust_env=False,
                )
            )
            native_response = client.send(
                httpx2.Request(
                    request.method,
                    request.url,
                    headers=[
                        (
                            name.encode("ascii"),
                            value.encode("latin-1")
                            if isinstance(value, str)
                            else value,
                        )
                        for name, value in request.headers.items()
                    ],
                    content=cast("str | bytes | None", request.body),
                ),
                stream=True,
                auth=None,
            )
            body = _ResponseBody(native_response, client)
            raw = _RequestsResponse(
                body=BufferedReader(body),
                headers=HTTPHeaderDict(body.msg.items()),
                status=native_response.status_code,
                reason=native_response.reason_phrase,
                preload_content=False,
                decode_content=False,
                original_response=body,  # ty: ignore[invalid-argument-type] - urllib3 uses the HTTPMessage and close protocol.
                request_method=request.method,
                request_url=request.url,
            )
            response = requests.Response()
            response.status_code = native_response.status_code
            response.headers = CaseInsensitiveDict(raw.headers)
            response.encoding = get_encoding_from_headers(response.headers)
            response.raw = raw
            response.reason = native_response.reason_phrase
            response.url = request.url
            response.request = request
            response.connection = self  # ty: ignore[invalid-assignment] - Requests supports any BaseAdapter.
            extract_cookies_to_jar(response.cookies, request, raw)
            stack.pop_all()
            return response

    def close(self) -> None:
        # Each response owns its client until the body is consumed or closed.
        pass


def post(url: str, **kwargs: Any) -> requests.Response:  # ruff: ignore[any-type]
    """Keep provider hooks, multipart bodies, redirects and auth compatible."""
    with requests.Session() as session:
        transport = _RequestsTransport()
        session.mount("http://", transport)
        session.mount("https://", transport)
        return session.post(url, **kwargs)


@contextmanager
def _httpx_errors() -> Generator[None]:
    try:
        yield
    except (httpx2.RequestError, httpx2.InvalidURL) as error:
        error_type = getattr(httpx, type(error).__name__, httpx.RequestError)
        raise error_type(str(error)) from error


class _HTTPXStream(httpx.SyncByteStream):
    def __init__(self, response: httpx2.Response) -> None:
        self.response = response

    def __iter__(self) -> Iterator[bytes]:
        with _httpx_errors():
            yield from self.response.iter_raw()

    def close(self) -> None:
        self.response.close()


class _HTTPXTransport(httpx.BaseTransport):
    def __init__(self) -> None:
        context = httpx.create_ssl_context()
        # Reuse HTTPX's proxy selection rules, including its NO_PROXY semantics.
        mounts = {
            pattern: httpx2.HTTPTransport(
                verify=context,
                proxy=httpx2.Proxy(
                    url,
                    ssl_context=(
                        httpx.create_ssl_context(trust_env=False)
                        if url.startswith("https:")
                        else None
                    ),
                ),
            )
            if url
            else None
            for pattern, url in get_environment_proxies().items()
        }
        self.client = httpx2.Client(verify=context, mounts=mounts, trust_env=False)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        with _httpx_errors():
            response = self.client.send(
                httpx2.Request(
                    request.method,
                    str(request.url),
                    headers=request.headers.raw,
                    content=request.stream,
                    extensions=request.extensions,
                ),
                stream=True,
                auth=None,
            )
        return httpx.Response(
            response.status_code,
            headers=response.headers.raw,
            stream=_HTTPXStream(response),
            extensions=response.extensions,
        )

    def close(self) -> None:
        self.client.close()


def httpx_client() -> httpx.Client:
    """Keep the HTTPX response and exception types exposed by file and runtime APIs."""
    with _httpx_errors():
        return httpx.Client(transport=_HTTPXTransport(), trust_env=False)
