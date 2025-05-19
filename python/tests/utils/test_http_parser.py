from dify_plugin.core.utils.http_parser import convert_request_to_raw_data, parse_raw_request


def test_parse_raw_request():
    request = parse_raw_request(
        b"GET / HTTP/1.1\r\nHost: localhost:8000\r\nUser-Agent: curl/8.1.2\r\nAccept: */*\r\n\r\n"
    )
    assert request.method == "GET"
    assert request.path == "/"
    assert request.headers["Host"] == "localhost:8000"
    assert request.headers["User-Agent"] == "curl/8.1.2"
    assert request.headers["Accept"] == "*/*"
    assert request.data == b""


def test_parse_raw_request_with_body():
    request = parse_raw_request(
        b"POST / HTTP/1.1\r\nHost: localhost:8000\r\nUser-Agent: curl/8.1.2"
        b"\r\nAccept: */*\r\nContent-Length: 13\r\n\r\n"
        b"Hello, World!"
    )
    assert request.method == "POST"
    assert request.path == "/"
    assert request.data == b"Hello, World!"


def test_parse_raw_request_with_body_and_headers():
    request = parse_raw_request(
        b"POST / HTTP/1.1\r\nHost: localhost:8000\r\nUser-Agent: curl/8.1.2"
        b"\r\nAccept: */*\r\nContent-Length: 13\r\n\r\n"
        b"Hello, World!"
    )
    assert request.method == "POST"
    assert request.path == "/"
    assert request.data == b"Hello, World!"
    assert request.headers["Content-Length"] == "13"
    assert request.headers["User-Agent"] == "curl/8.1.2"
    assert request.headers["Accept"] == "*/*"


def test_convert_request_to_raw_data():
    request = parse_raw_request(
        b"POST / HTTP/1.1\r\nHost: localhost:8000\r\nUser-Agent: curl/8.1.2"
        b"\r\nAccept: */*\r\nContent-Length: 13\r\n\r\n"
        b"Hello, World!"
    )
    raw_data = convert_request_to_raw_data(request)
    request = parse_raw_request(raw_data)
    assert request.method == "POST"
    assert request.path == "/"
    assert request.data == b"Hello, World!"
    assert request.headers["Content-Length"] == "13"
    assert request.headers["User-Agent"] == "curl/8.1.2"
    assert request.headers["Accept"] == "*/*"
