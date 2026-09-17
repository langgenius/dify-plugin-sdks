import base64

from dify_plugin.entities.datasource import (
    DatasourceMessage,
    OnlineDriveBrowseFilesResponse,
    OnlineDriveFile,
)


def test_online_drive_file_keeps_legacy_payload_compatible() -> None:
    file = OnlineDriveFile(id="file-1", name="report.pdf", size=42, type="file")

    assert file.remote_metadata is None


def test_online_drive_file_serializes_optional_remote_metadata() -> None:
    metadata = {
        "version_id": "version-1",
        "etag": "etag-1",
        "checksum": {"algorithm": "sha256", "value": "a" * 64},
        "modified_time": "2026-09-17T10:20:30Z",
    }

    response = OnlineDriveBrowseFilesResponse(
        result=[
            {
                "bucket": "bucket-1",
                "files": [
                    {
                        "id": "file-1",
                        "name": "report.pdf",
                        "size": 42,
                        "type": "file",
                        "remote_metadata": metadata,
                    }
                ],
                "is_truncated": False,
            }
        ]
    )

    assert response.result[0].files[0].remote_metadata == metadata
    assert response.model_dump()["result"][0]["files"][0]["remote_metadata"] == metadata


def test_datasource_blob_message_keeps_online_drive_remote_metadata() -> None:
    metadata = {"etag": "etag-1"}
    message = DatasourceMessage(
        type=DatasourceMessage.MessageType.BLOB,
        message=DatasourceMessage.BlobMessage(blob=b"content"),
        meta={"remote_metadata": metadata},
    )

    serialized = message.model_dump()

    assert serialized["meta"] == {"remote_metadata": metadata}
    assert serialized["message"]["blob"] == base64.b64encode(b"content").decode()
