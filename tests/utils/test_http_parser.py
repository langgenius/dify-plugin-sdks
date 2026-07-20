import pytest
from werkzeug import Response

from dify_plugin.core.utils.http_parser import deserialize_request, serialize_response


def test_deserialize_request() -> None:
    request = deserialize_request(
        b"POST /a%3Fb%23c?q[]=1 HTTP/1.1\r\n"
        b"Host: example.com:8080\r\n"
        b"Authorization: Bearer token\r\n"
        b"Content-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n"
        b'8\r\n{"id":1}\r\n0\r\n\r\n',
    )

    assert request.method == "POST"
    assert request.path == "/a?b#c"
    assert request.query_string == b"q[]=1"
    assert request.host == "example.com:8080"
    assert request.headers["Authorization"] == "Bearer token"
    assert request.get_json() == {"id": 1}


def test_serialize_response() -> None:
    response = Response(
        b"\x00\xff", status=201, content_type="application/octet-stream"
    )
    response.headers["X-Test"] = "value"

    assert serialize_response(response) == (
        b"HTTP/1.1 201 CREATED\r\n"
        b"Content-Type: application/octet-stream\r\n"
        b"Content-Length: 2\r\n"
        b"X-Test: value\r\n\r\n"
        b"\x00\xff"
    )


def test_rejects_trailing_request() -> None:
    raw_request = b"GET / HTTP/1.1\r\nHost: example.com\r\n\r\n"

    with pytest.raises(ValueError, match="Unexpected data"):
        deserialize_request(raw_request + raw_request)


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
