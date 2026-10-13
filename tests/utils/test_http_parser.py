import pytest
from werkzeug import Response

from dify_plugin.core.utils.http_parser import deserialize_request, serialize_response


def test_deserialize_request() -> None:
    request = deserialize_request(
        b"POST /caf\xc3\xa9/a b%3Fc%23d?q[]=1 HTTP/1.1\r\n"
        b"Host: example.com:8080\r\n"
        b"Authorization: Bearer token\r\n"
        b"Content-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\n"
        b"X-Label: caf\xc3\xa9\r\n\r\n"
        b'{"id":1}',
    )

    assert request.method == "POST"
    assert request.path == "/café/a b?c#d"
    assert request.query_string == b"q[]=1"
    assert request.host == "example.com:8080"
    assert request.headers["Authorization"] == "Bearer token"
    assert request.headers["X-Label"] == "café"
    assert "Transfer-Encoding" not in request.headers
    assert request.content_length == 8
    assert request.get_json() == {"id": 1}


def test_serialize_response() -> None:
    response = Response(
        b"\x00\xff", status=201, content_type="application/octet-stream"
    )
    response.headers["X-Test"] = "café"

    assert serialize_response(response) == (
        b"HTTP/1.1 201 \r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"X-Test: caf\xc3\xa9\r\n"
        b"Content-Length: 2\r\n\r\n"
        b"\x00\xff"
    )


def test_ignores_response_reason_phrase() -> None:
    response = Response(status="200 Fine\r\nX-Injected: yes")

    raw_response = serialize_response(response)

    assert raw_response.startswith(b"HTTP/1.1 200 \r\n")
    assert b"X-Injected" not in raw_response


def test_rejects_content_length_mismatch() -> None:
    raw_request = (
        b"POST / HTTP/1.1\r\nHost: example.com\r\nContent-Length: 1\r\n\r\nbody"
    )

    with pytest.raises(ValueError, match="Content-Length"):
        deserialize_request(raw_request)


def test_rejects_decoded_newline_in_target() -> None:
    with pytest.raises(ValueError, match="request line"):
        deserialize_request(
            b"GET /safe\r\nX-Injected: yes HTTP/1.1\r\nHost: example.com\r\n\r\n",
        )


def test_rejects_ambiguous_headers() -> None:
    with pytest.raises(ValueError, match="header"):
        deserialize_request(
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Type: application/json\r\n"
            b"Content_Type: text/plain\r\n"
            b"Content-Length: 2\r\n\r\n{}",
        )

    with pytest.raises(ValueError, match="Duplicate"):
        deserialize_request(
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 2\r\n\r\n{}",
        )

    with pytest.raises(ValueError, match="framing"):
        deserialize_request(
            b"POST / HTTP/1.1\r\n"
            b"Host: example.com\r\n"
            b"Transfer-Encoding: chunked\r\n"
            b"Content-Length: 2\r\n\r\n{}",
        )


@pytest.mark.parametrize("newline", ["\r", "\n"])
def test_rejects_newlines_in_header_names(newline: str) -> None:
    name = f"X-Test{newline}Injected"

    with pytest.raises(ValueError, match="header"):
        deserialize_request(
            f"GET / HTTP/1.1\r\nHost: example.com\r\n{name}: value\r\n\r\n".encode(),
        )

    response = Response()
    response.headers[name] = "value"
    with pytest.raises(ValueError, match="header"):
        serialize_response(response)


@pytest.mark.parametrize(
    ("raw_request", "message"),
    [
        pytest.param(b"", "Empty HTTP request", id="empty"),
        pytest.param(b"GET /", "request line", id="missing-protocol"),
        pytest.param(
            b"GET / HTTP/2.0\r\nHost: example.com\r\n\r\n",
            "protocol",
            id="unsupported-protocol",
        ),
        pytest.param(
            b"GET /unsafe\tpath HTTP/1.1\r\nHost: example.com\r\n\r\n",
            "request target",
            id="control-in-target",
        ),
        pytest.param(
            b"POST / HTTP/1.1\r\nHost: example.com\r\nContent-Length: -1\r\n\r\n",
            "Content-Length",
            id="negative-content-length",
        ),
        pytest.param(
            b"POST / HTTP/1.1\r\nHost: example.com\r\n"
            b"Content-Length: 1\r\nContent-Length: 2\r\n\r\nx",
            "Content-Length",
            id="conflicting-content-lengths",
        ),
    ],
)
def test_invalid_http_envelope_raises_value_error(
    raw_request: bytes, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        deserialize_request(raw_request)


@pytest.mark.parametrize("separator", [b"\r\n", b"\n"])
@pytest.mark.parametrize("terminate_headers", [False, True])
def test_http_10_request_without_host_or_body(
    separator: bytes, terminate_headers: bool
) -> None:
    raw_request = separator.join((b"GET /health HTTP/1.0", b"Accept: text/plain"))
    if terminate_headers:
        raw_request += separator * 2

    request = deserialize_request(raw_request)

    assert request.method == "GET"
    assert request.path == "/health"
    assert request.environ["SERVER_PROTOCOL"] == "HTTP/1.0"
    assert request.host == "localhost"
    assert request.headers["Accept"] == "text/plain"
    assert request.get_data() == b""


def test_repeated_accept_headers_preserve_all_media_types() -> None:
    # The daemon copies http.Header values with Request.Write, preserving each line.
    request = deserialize_request(
        b"GET / HTTP/1.1\r\nHost: example.com\r\n"
        b"Accept: application/json\r\nAccept: text/plain\r\n\r\n"
    )

    assert request.accept_mimetypes["application/json"] == 1
    assert request.accept_mimetypes["text/plain"] == 1


def test_repeated_cookie_headers_preserve_each_cookie() -> None:
    request = deserialize_request(
        b"GET / HTTP/1.1\r\nHost: example.com\r\n"
        b"Cookie: session=one\r\nCookie: state=two\r\n\r\n"
    )

    assert request.cookies.getlist("session") == ["one"]
    assert request.cookies.getlist("state") == ["two"]


def test_response_preserves_repeated_cookies_and_replaces_body_framing() -> None:
    response = Response(b"\x00\xff", content_type="application/octet-stream")
    response.headers.add("Set-Cookie", "session=one; HttpOnly")
    response.headers.add("Set-Cookie", "state=two; SameSite=Lax")
    response.headers["Content-Length"] = "99"
    response.headers["Transfer-Encoding"] = "chunked"

    assert serialize_response(response) == (
        b"HTTP/1.1 200 \r\nContent-Type: application/octet-stream\r\n"
        b"Set-Cookie: session=one; HttpOnly\r\n"
        b"Set-Cookie: state=two; SameSite=Lax\r\n"
        b"Content-Length: 2\r\n\r\n\x00\xff"
    )
