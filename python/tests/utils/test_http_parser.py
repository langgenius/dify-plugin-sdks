from werkzeug import Response

from dify_plugin.core.utils.http_parser import (
    convert_request_to_raw_data,
    convert_response_to_raw_data,
    parse_raw_request,
    parse_raw_response,
)


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


def test_parse_raw_response():
    raw_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"X-Custom-Header: test-value\r\n"
        b"Content-Length: 37\r\n"
        b"\r\n"
        b'{"status": "success", "data": "test"}'
    )
    response = parse_raw_response(raw_response)
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/json"
    assert response.headers["X-Custom-Header"] == "test-value"
    assert response.headers["Content-Length"] == "37"
    assert response.get_data() == b'{"status": "success", "data": "test"}'


def test_parse_raw_response_no_body():
    raw_response = b"HTTP/1.1 204 No Content\r\nX-Custom-Header: test-value\r\n\r\n"
    response = parse_raw_response(raw_response)
    assert response.status_code == 204
    assert response.headers["X-Custom-Header"] == "test-value"
    assert response.get_data() == b""


def test_parse_raw_response_with_error():
    raw_response = b"HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nContent-Length: 9\r\n\r\nNot Found"
    response = parse_raw_response(raw_response)
    assert response.status_code == 404
    assert response.headers["Content-Type"] == "text/plain"
    assert response.get_data() == b"Not Found"


def test_convert_response_to_raw_data():
    # Create a response
    original_response = Response(
        response='{"status": "success", "data": "test"}',
        status=200,
        headers={
            "Content-Type": "application/json",
            "X-Custom-Header": "test-value",
        },
    )

    # Convert to raw data
    raw_data = convert_response_to_raw_data(original_response)

    # Parse back
    parsed_response = parse_raw_response(raw_data)

    # Verify
    assert parsed_response.status_code == original_response.status_code
    assert parsed_response.get_data() == original_response.get_data()
    # Headers might be lowercase after parsing
    assert parsed_response.headers.get("content-type") == "application/json"
    assert parsed_response.headers.get("x-custom-header") == "test-value"


def test_convert_response_to_raw_data_no_body():
    # Create a response with no body
    original_response = Response(status=204)
    original_response.headers["X-Custom-Header"] = "test-value"

    # Convert to raw data
    raw_data = convert_response_to_raw_data(original_response)

    # Parse back
    parsed_response = parse_raw_response(raw_data)

    # Verify
    assert parsed_response.status_code == 204
    assert parsed_response.get_data() == b""
    assert parsed_response.headers.get("x-custom-header") == "test-value"


def test_response_round_trip():
    # Test complete round trip: Response -> raw -> Response
    test_cases = [
        # JSON response
        Response(response='{"key": "value"}', status=200, headers={"Content-Type": "application/json"}),
        # HTML response
        Response(response="<html><body>Hello</body></html>", status=200, headers={"Content-Type": "text/html"}),
        # Error response
        Response(response="Internal Server Error", status=500, headers={"Content-Type": "text/plain"}),
        # No content response
        Response(status=204),
    ]

    for original_response in test_cases:
        raw_data = convert_response_to_raw_data(original_response)
        parsed_response = parse_raw_response(raw_data)

        assert parsed_response.status_code == original_response.status_code
        assert parsed_response.get_data() == original_response.get_data()


def test_json_request_parsing():
    # Test parsing JSON request
    raw_request = (
        b"POST /api/data HTTP/1.1\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 46\r\n"
        b"Host: example.com\r\n"
        b"\r\n"
        b'{"name": "test", "value": 123, "active": true}'
    )

    request = parse_raw_request(raw_request)
    assert request.method == "POST"
    assert request.path == "/api/data"
    assert request.content_type == "application/json"

    # Verify JSON parsing works
    json_data = request.get_json()
    assert json_data == {"name": "test", "value": 123, "active": True}


def test_json_request_conversion():
    # Test converting JSON request to raw and back
    from werkzeug.test import EnvironBuilder

    json_data = {"user": "alice", "action": "update", "items": [1, 2, 3]}
    builder = EnvironBuilder(
        method="PUT", path="/api/users/123", json=json_data, headers={"Authorization": "Bearer token123"}
    )
    original_request = builder.get_request()

    # Convert to raw
    raw_data = convert_request_to_raw_data(original_request)

    # Parse back
    parsed_request = parse_raw_request(raw_data)

    # Verify
    assert parsed_request.method == "PUT"
    assert parsed_request.path == "/api/users/123"
    assert parsed_request.get_json() == json_data
    assert parsed_request.headers.get("Authorization") == "Bearer token123"


def test_json_response_parsing():
    # Test parsing JSON response
    raw_response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: 52\r\n"
        b"X-Request-Id: abc123\r\n"
        b"\r\n"
        b'{"status": "success", "data": {"id": 1, "ok": true}}'
    )

    response = parse_raw_response(raw_response)
    assert response.status_code == 200
    assert response.content_type == "application/json"

    # Verify JSON parsing
    import json

    json_data = json.loads(response.get_data(as_text=True))
    assert json_data == {"status": "success", "data": {"id": 1, "ok": True}}
    assert response.headers.get("X-Request-Id") == "abc123"


def test_form_urlencoded_request():
    # Test form-urlencoded request
    raw_request = (
        b"POST /form HTTP/1.1\r\n"
        b"Content-Type: application/x-www-form-urlencoded\r\n"
        b"Content-Length: 38\r\n"
        b"\r\n"
        b"name=John+Doe&email=john%40example.com"
    )

    request = parse_raw_request(raw_request)
    assert request.method == "POST"
    assert request.content_type == "application/x-www-form-urlencoded"

    # Verify form parsing
    assert request.form.get("name") == "John Doe"
    assert request.form.get("email") == "john@example.com"


def test_query_string_handling():
    # Test request with query string
    raw_request = (
        b"GET /search?q=test&page=2&limit=10 HTTP/1.1\r\nHost: example.com\r\nAccept: application/json\r\n\r\n"
    )

    request = parse_raw_request(raw_request)
    assert request.method == "GET"
    assert request.path == "/search"
    assert request.query_string == b"q=test&page=2&limit=10"

    # Verify query parameters
    assert request.args.get("q") == "test"
    assert request.args.get("page") == "2"
    assert request.args.get("limit") == "10"
