from io import BytesIO
from urllib.parse import quote_from_bytes, unquote_to_bytes, urlsplit

import h11
from werkzeug import Request, Response


def deserialize_request(raw_data: bytes) -> Request:
    if not raw_data:
        msg = "Empty HTTP request"
        raise ValueError(msg)

    header_data, separator, body = raw_data.partition(b"\r\n\r\n")
    line_separator = b"\r\n"
    if not separator:
        header_data, separator, body = raw_data.partition(b"\n\n")
        line_separator = b"\n"
    if not separator:
        line_separator = b"\r\n" if b"\r\n" in raw_data else b"\n"

    lines = header_data.split(line_separator)
    method, space, remainder = lines[0].partition(b" ")
    target, version_space, protocol = remainder.rpartition(b" ")
    if not space or not version_space:
        msg = "Invalid HTTP request line"
        raise ValueError(msg)

    if protocol not in {b"HTTP/1.0", b"HTTP/1.1"}:
        msg = "Invalid HTTP protocol"
        raise ValueError(msg)
    full_path = target.decode()
    if not full_path.isprintable():
        msg = "Invalid HTTP request target"
        raise ValueError(msg)

    normalized_target = quote_from_bytes(
        target,
        safe="/%:?#[]@!$&'()*+,;=",
    ).encode()
    request_line = b" ".join((method, normalized_target, protocol))
    request_head = b"\r\n".join((request_line, *lines[1:], b"", b""))
    connection = h11.Connection(h11.SERVER)
    try:
        connection.receive_data(request_head)
        request_event = connection.next_event()
    except h11.ProtocolError as exc:
        raise ValueError(str(exc)) from exc
    if not isinstance(request_event, h11.Request):
        msg = "Invalid HTTP request"
        raise TypeError(msg)
    if any(b"_" in name for name, _ in request_event.headers):
        msg = "Invalid HTTP header"
        raise ValueError(msg)

    raw_path, _, query_string = full_path.partition("?")

    header_values = dict(request_event.headers)
    host = header_values.get(b"host", b"localhost").decode()
    parsed_host = urlsplit(f"//{host}")
    server_name = parsed_host.hostname or host
    server_port = str(80 if parsed_host.port is None else parsed_host.port)

    environ = {
        "REQUEST_METHOD": request_event.method.decode("ascii"),
        "PATH_INFO": unquote_to_bytes(raw_path).decode("latin-1"),
        "QUERY_STRING": query_string,
        "SERVER_NAME": server_name,
        "SERVER_PORT": server_port,
        "SERVER_PROTOCOL": f"HTTP/{request_event.http_version.decode('ascii')}",
        "wsgi.input": BytesIO(body),
        "wsgi.input_terminated": True,
        "wsgi.url_scheme": "http",
    }

    content_length = header_values.get(b"content-length")
    transfer_encoding = header_values.get(b"transfer-encoding")
    if content_length is not None and transfer_encoding is not None:
        msg = "Ambiguous HTTP body framing"
        raise ValueError(msg)
    if content_length is not None and int(content_length) != len(body):
        msg = "HTTP body does not match Content-Length"
        raise ValueError(msg)

    for name, value in request_event.headers:
        if name == b"transfer-encoding":
            continue
        env_name = name.decode("ascii").upper().replace("-", "_")
        key = (
            env_name
            if name in {b"content-type", b"content-length"}
            else f"HTTP_{env_name}"
        )
        if key in environ and name in {b"content-type", b"content-length"}:
            msg = f"Duplicate HTTP header: {name.decode('ascii')}"
            raise ValueError(msg)
        environ[key] = value.decode()

    if content_length is None and body:
        environ["CONTENT_LENGTH"] = str(len(body))

    return Request(environ)


def serialize_response(response: Response) -> bytes:
    body = response.get_data()
    try:
        response_event = h11.Response(
            status_code=response.status_code,
            headers=[
                (name.encode("ascii"), value.encode())
                for name, value in response.headers
                if name.lower() not in {"content-length", "transfer-encoding"}
            ]
            + [(b"Content-Length", str(len(body)).encode())],
        )
        connection = h11.Connection(h11.SERVER)
        return b"".join(
            chunk or b""
            for chunk in (
                connection.send(response_event),
                connection.send(h11.Data(data=body)),
                connection.send(h11.EndOfMessage()),
            )
        )
    except h11.ProtocolError as exc:
        raise ValueError(str(exc)) from exc
