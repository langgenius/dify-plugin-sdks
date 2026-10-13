import base64

import pytest

from dify_plugin.entities.datasource import (
    DatasourceMessage,
    OnlineDriveBrowseFilesResponse,
    OnlineDriveFile,
)
from dify_plugin.entities.datasource_manifest import DatasourceEntity


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


def test_online_drive_file_accepts_provider_specific_checksum_algorithm() -> None:
    metadata = {
        "checksum": {"algorithm": "sha1", "value": "b" * 40},
    }

    file = OnlineDriveFile(
        id="file-1",
        name="report.pdf",
        size=42,
        type="file",
        remote_metadata=metadata,
    )

    assert file.remote_metadata == metadata


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


@pytest.mark.parametrize("default", [False, True])
def test_datasource_manifest_preserves_boolean_defaults_for_crawl_requests(
    default: bool,
) -> None:
    # Tavily and Firecrawl pass these boolean defaults to their upstream APIs.
    datasource = DatasourceEntity.model_validate({
        "identity": {
            "author": "langgenius",
            "name": "crawl",
            "label": {"en_US": "Crawl"},
        },
        "description": {"en_US": "Crawl a website"},
        "extra": {"python": {"source": "datasources/crawl.py"}},
        "parameters": [
            {
                "name": "only_main_content",
                "type": "boolean",
                "default": default,
                "label": {"en_US": "Only main content"},
                "description": {"en_US": "Exclude navigation and footer content"},
            }
        ],
    })

    assert datasource.model_dump(mode="json")["parameters"][0]["default"] is default
