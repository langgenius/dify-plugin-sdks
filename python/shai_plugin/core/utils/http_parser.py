from dpkt.http import Request as DpktRequest
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request


def parse_raw_request(raw_data: bytes):
    """
    Parse raw HTTP data into a Request object.

    Args:
        raw_data: The raw HTTP data as bytes.

    Returns:

    """
    req = DpktRequest(raw_data)
    builder = EnvironBuilder(
        method=req.method,
        path=req.uri,
        headers=req.headers,
        data=req.body,
    )
    return Request(builder.get_environ())


def convert_request_to_raw_data(request: Request) -> bytes:
    """
    Convert a Request object to raw HTTP data.

    Args:
        request: The Request object to convert.

    Returns:
        The raw HTTP data as bytes.
    """
    # Start with the request line
    method = request.method
    path = request.path
    protocol = request.headers.get("HTTP_VERSION", "HTTP/1.1")
    raw_data = f"{method} {path} {protocol}\r\n".encode()

    # Add headers
    for header_name, header_value in request.headers.items():
        raw_data += f"{header_name}: {header_value}\r\n".encode()

    # Add empty line to separate headers from body
    raw_data += b"\r\n"

    # Add body if exists
    body = request.get_data(as_text=False)
    if body:
        raw_data += body

    return raw_data
