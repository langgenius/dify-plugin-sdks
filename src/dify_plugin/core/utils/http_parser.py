from io import BytesIO
from typing import cast
from urllib.parse import unquote_to_bytes

import h11
from werkzeug import Request, Response


def deserialize_request(raw_data: bytes) -> Request:
    if not raw_data:
        msg = "Empty HTTP request"
        raise ValueError(msg)

    connection = h11.Connection(h11.SERVER)
    body = bytearray()
    try:
        connection.receive_data(raw_data)
        # raw_data is a complete message, so EOF terminates the request.
        connection.receive_data(b"")
        request_event = cast("h11.Request", connection.next_event())
        while isinstance(event := connection.next_event(), h11.Data):
            body.extend(event.data)
    except h11.ProtocolError as exc:
        raise ValueError(str(exc)) from exc

    trailing_data, _ = connection.trailing_data
    if trailing_data:
        msg = "Unexpected data after HTTP request"
        raise ValueError(msg)

    full_path = request_event.target.decode("ascii")
    raw_path, separator, query_string = full_path.partition("?")
    if not separator:
        query_string = ""

    host = next(
        (value for name, value in request_event.headers if name == b"host"),
        b"localhost",
    ).decode("latin-1")
    if ":" in host:
        server_name, server_port = host.rsplit(":", 1)
    else:
        server_name, server_port = host, "80"

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

    for name, value in request_event.headers:
        env_name = name.decode("ascii").upper().replace("-", "_")
        key = (
            env_name
            if env_name in {"CONTENT_TYPE", "CONTENT_LENGTH"}
            else f"HTTP_{env_name}"
        )
        environ[key] = value.decode("latin-1")

    return Request(environ)


def serialize_response(response: Response) -> bytes:
    try:
        response_event = h11.Response(
            status_code=response.status_code,
            reason=response.status.partition(" ")[2].encode("latin-1"),
            headers=[
                (name.encode("ascii"), value.encode("latin-1"))
                for name, value in response.headers
            ],
        )
        connection = h11.Connection(h11.SERVER)
        return b"".join(
            chunk or b""
            for chunk in (
                connection.send(response_event),
                connection.send(h11.Data(data=response.get_data())),
                connection.send(h11.EndOfMessage()),
            )
        )
    except h11.ProtocolError as exc:
        raise ValueError(str(exc)) from exc
