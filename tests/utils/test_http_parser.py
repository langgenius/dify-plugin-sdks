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
