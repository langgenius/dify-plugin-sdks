"""Shared configuration for the SDK's synchronous HTTPX2 clients."""

import os
import re
import ssl
from collections.abc import Mapping

import httpx2
from httpx2._utils import get_environment_proxies  # ruff: ignore[import-private-name]

from dify_plugin.core.utils.http_transport import Transport

_HEADER_NAME = re.compile(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_HEADER_VALUE = re.compile(rb"(?:[\x21-\x7e\x80-\xff][\t\x20-\x7e\x80-\xff]*)?")


def headers(values: Mapping[str, str | bytes]) -> httpx2.Headers:
    """Encode HTTP fields without including their values in encoding errors."""
    raw = []
    for name, value in values.items():
        if not isinstance(name, str) or not name.isascii():
            msg = "HTTP header names must be ASCII text"
            raise httpx2.LocalProtocolError(msg)
        if isinstance(value, str):
            if value and max(value) > "\xff":
                msg = "HTTP header values must be Latin-1 text or bytes"
                raise httpx2.LocalProtocolError(msg)
            encoded = value.encode("latin-1")
        elif isinstance(value, bytes):
            encoded = value
        else:
            msg = "HTTP header values must be text or bytes"
            raise httpx2.LocalProtocolError(msg)
        raw.append((name.encode("ascii"), encoded))
    return httpx2.Headers(raw)


def _prepare_request(request: httpx2.Request) -> None:
    raw = []
    for name, value in request.headers.raw:
        if not _HEADER_NAME.fullmatch(name):
            msg = "Invalid HTTP header name"
            raise httpx2.LocalProtocolError(msg, request=request)
        normalized = value.rstrip(b" \t")
        if not _HEADER_VALUE.fullmatch(normalized):
            msg = "Invalid HTTP header value"
            raise httpx2.LocalProtocolError(msg, request=request)
        raw.append((name, normalized))
    request.headers = httpx2.Headers(raw)
    if request.url.host.endswith("."):
        request.extensions.setdefault("sni_hostname", request.url.host.rstrip("."))


def client() -> httpx2.Client:
    """Use native HTTPX2 objects, environment proxy rules and system trust."""
    cafile = (
        os.getenv("SSL_CERT_FILE")
        or os.getenv("REQUESTS_CA_BUNDLE")
        or os.getenv("CURL_CA_BUNDLE")
    )
    capath = os.getenv("SSL_CERT_DIR")
    context = (
        ssl.create_default_context(cafile=cafile, capath=capath)
        if cafile or capath
        else httpx2.create_ssl_context()
    )
    mounts: dict[str, httpx2.BaseTransport | None] = {}
    for pattern, proxy_url in get_environment_proxies().items():
        if proxy_url is None:
            mounts[pattern] = None
        else:
            mounts[pattern] = Transport(context, httpx2.URL(proxy_url))
    return httpx2.Client(
        transport=Transport(context),
        mounts=mounts,
        trust_env=False,
        auth=httpx2.NetRCAuth(os.environ["NETRC"]) if os.getenv("NETRC") else None,
        event_hooks={"request": [_prepare_request]},
    )
