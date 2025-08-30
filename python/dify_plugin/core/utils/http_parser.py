from dpkt.http import Request as DpktRequest
from dpkt.http import Response as DpktResponse
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response


def parse_raw_request(raw_data: bytes):
    """
    Parse raw HTTP data into a Request object.

    Supports various content types including:
    - application/json
    - multipart/form-data (file uploads)
    - application/x-www-form-urlencoded
    - text/plain and others

    Args:
        raw_data: The raw HTTP data as bytes.

    Returns:
        A Werkzeug Request object.
    """
    req = DpktRequest(raw_data)
    
    # Extract content type to handle different request types
    content_type = req.headers.get('content-type', '')
    
    # Build the request with proper handling for different content types
    builder = EnvironBuilder(
        method=req.method,
        path=req.uri,
        headers=dict(req.headers),
        data=req.body,
    )
    return Request(builder.get_environ())


def convert_request_to_raw_data(request: Request) -> bytes:
    """
    Convert a Request object to raw HTTP data.
    
    Properly handles various content types including:
    - application/json
    - application/x-www-form-urlencoded
    - text/plain and others
    
    NOTE: For multipart/form-data (file uploads), this function will include
    the raw body if it's still available in the request stream. However,
    if the request has already been parsed (e.g., form fields accessed),
    the multipart body may not be fully reconstructible.

    Args:
        request: The Request object to convert.

    Returns:
        The raw HTTP data as bytes.
    """
    # Start with the request line
    method = request.method
    path = request.full_path if request.query_string else request.path
    protocol = "HTTP/1.1"
    raw_data = f"{method} {path} {protocol}\r\n".encode()

    # Get the body first to ensure Content-Length is correct
    body = request.get_data(as_text=False)
    
    # Build headers dict, excluding some werkzeug-specific headers
    headers_to_skip = {'HTTP_VERSION', 'REQUEST_METHOD', 'PATH_INFO', 'QUERY_STRING', 
                       'SCRIPT_NAME', 'SERVER_NAME', 'SERVER_PORT', 'SERVER_PROTOCOL',
                       'wsgi.version', 'wsgi.url_scheme', 'wsgi.input', 'wsgi.errors',
                       'wsgi.multithread', 'wsgi.multiprocess', 'wsgi.run_once'}
    
    # Add important headers
    if request.content_type:
        raw_data += f"Content-Type: {request.content_type}\r\n".encode()
    
    if body:
        raw_data += f"Content-Length: {len(body)}\r\n".encode()
    
    # Add other headers
    for header_name, header_value in request.headers.items():
        # Skip already added headers and internal headers
        if header_name.lower() not in ('content-type', 'content-length') and header_name not in headers_to_skip:
            raw_data += f"{header_name}: {header_value}\r\n".encode()

    # Add empty line to separate headers from body
    raw_data += b"\r\n"

    # Add body if exists
    if body:
        raw_data += body

    return raw_data


def parse_raw_response(raw_data: bytes) -> Response:
    """
    Parse raw HTTP response data into a Response object.

    Args:
        raw_data: The raw HTTP response data as bytes.

    Returns:
        A Werkzeug Response object.
    """
    resp = DpktResponse(raw_data)

    # Extract status code from the status line
    status_code = resp.status

    # Create Response object with body and status
    response = Response(
        response=resp.body,
        status=status_code,
        headers=dict(resp.headers),
    )

    return response


def convert_response_to_raw_data(response: Response) -> bytes:
    """
    Convert a Response object to raw HTTP response data.

    Args:
        response: The Response object to convert.

    Returns:
        The raw HTTP response data as bytes.
    """
    # Start with the status line
    protocol = "HTTP/1.1"
    status_code = response.status_code
    status_text = response.status or "OK"
    raw_data = f"{protocol} {status_code} {status_text}\r\n".encode()

    # Add headers
    for header_name, header_value in response.headers.items():
        raw_data += f"{header_name}: {header_value}\r\n".encode()

    # Add empty line to separate headers from body
    raw_data += b"\r\n"

    # Add body if exists
    body = response.get_data(as_text=False)
    if body:
        raw_data += body

    return raw_data
