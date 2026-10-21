import json
from email import policy
from email.parser import BytesParser

import pytest
from pydantic import ValidationError
from pytest_mock import MockerFixture

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.invocations.file import File, UploadFileResponse
from tests.http_server import HTTPServerFactory, Response

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("content", [b"", b"\x00\xff\x80binary", "你好".encode()])
def test_upload_preserves_signed_url_multipart_and_preview_url(
    http_server: HTTPServerFactory, mocker: MockerFixture, content: bytes
) -> None:
    upload_data = {
        "id": "uploaded-file",
        "name": "résumé.png",
        "size": len(content),
        "extension": "png",
        "mime_type": "image/png",
        "preview_url": "https://files.example/preview?sign=retained",
    }
    server = http_server([Response(status=201, body=json.dumps(upload_data).encode())])
    path = "/files/upload/for-plugin?timestamp=1&nonce=n&sign=a%2Fb%2Bc&tenant_id=t"
    file = File()
    request_url = mocker.patch.object(
        file, "_backwards_invoke", return_value=iter([{"url": server.url + path}])
    )

    result = file.upload("résumé.png", content, "image/png")

    request_url.assert_called_once_with(
        InvokeType.UploadFile, dict, {"filename": "résumé.png", "mimetype": "image/png"}
    )
    assert result.model_dump(exclude={"type"}) == upload_data
    assert result.to_app_parameter() == {
        "tool_file_id": "uploaded-file",
        "transfer_method": "tool_file",
        "type": "image",
    }
    assert len(server.requests) == 1
    request = server.requests[0]
    assert (request.method, request.path) == ("POST", path)
    message = BytesParser(policy=policy.default).parsebytes(
        f"Content-Type: {request.headers['Content-Type']}\r\n\r\n".encode()
        + request.body
    )
    parts = list(message.iter_parts())
    assert len(parts) == 1
    assert parts[0].get_param("name", header="content-disposition") == "file"
    assert parts[0].get_filename() == "résumé.png"
    assert parts[0].get_content_type() == "image/png"
    assert parts[0].get_payload(decode=True) == content


@pytest.mark.parametrize("status", [200, 400, 403, 413, 415, 500])
def test_upload_surfaces_rejected_or_unexpected_status(
    http_server: HTTPServerFactory, mocker: MockerFixture, status: int
) -> None:
    server = http_server([Response(status=status, body=b"rejected upload")])
    file = File()
    mocker.patch.object(
        file, "_backwards_invoke", return_value=iter([{"url": server.url + "/upload"}])
    )

    with pytest.raises(Exception, match=f"status code: {status}.*rejected upload"):
        file.upload("file.txt", b"test", "text/plain")
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    ("responses", "message"),
    [([], "empty response"), ([{}], "signed url"), ([{"url": ""}], "signed url")],
)
def test_upload_requires_a_signed_url(
    mocker: MockerFixture, responses: list[dict], message: str
) -> None:
    file = File()
    mocker.patch.object(file, "_backwards_invoke", return_value=iter(responses))

    with pytest.raises(Exception, match=message):
        file.upload("file.txt", b"test", "text/plain")


@pytest.mark.parametrize(
    ("mime_type", "expected"),
    [
        ("image/png", "image"),
        ("video/mp4", "video"),
        ("audio/wav", "audio"),
        ("application/pdf", "document"),
        ("application/octet-stream", "document"),
    ],
)
def test_upload_result_is_usable_as_an_app_file(mime_type: str, expected: str) -> None:
    result = UploadFileResponse(
        id="file-id", name="file", size=0, extension="", mime_type=mime_type
    )

    assert result.type == expected
    assert result.to_app_parameter() == {
        "tool_file_id": "file-id",
        "transfer_method": "tool_file",
        "type": expected,
    }


def test_upload_accepts_an_explicit_response_type() -> None:
    result = UploadFileResponse(
        id="file-id",
        name="file",
        size=0,
        extension="",
        mime_type="image/png",
        type="image",
    )

    assert result.type == UploadFileResponse.Type.IMAGE


@pytest.mark.parametrize("body", [b"not JSON", b'{"id": "incomplete"}'])
def test_upload_rejects_invalid_success_payload(
    http_server: HTTPServerFactory, mocker: MockerFixture, body: bytes
) -> None:
    server = http_server([Response(status=201, body=body)])
    file = File()
    mocker.patch.object(
        file, "_backwards_invoke", return_value=iter([{"url": server.url + "/upload"}])
    )

    with pytest.raises((ValueError, ValidationError)):
        file.upload("file.txt", b"test", "text/plain")
