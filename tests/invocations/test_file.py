from dify_plugin.invocations.file import UploadFileResponse


def test_upload_response_converts_to_tool_file_parameter() -> None:
    response = UploadFileResponse(
        id="file-id",
        name="image.png",
        size=1,
        extension="png",
        mime_type="image/png",
    )

    assert response.to_app_parameter() == {
        "tool_file_id": "file-id",
        "transfer_method": "tool_file",
        "type": "image",
    }
