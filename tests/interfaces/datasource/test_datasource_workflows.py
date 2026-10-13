import pytest

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import (
    DatasourceMessage,
    DatasourceRuntime,
    GetOnlineDocumentPageContentRequest,
    OnlineDriveBrowseFilesRequest,
    OnlineDriveDownloadFileRequest,
    WebsiteCrawlMessage,
)
from dify_plugin.plugin import Plugin
from tests.core.plugin_fixtures import contract_plugin, contract_source

__all__ = ["contract_plugin", "contract_source"]


@pytest.fixture
def session(contract_plugin: Plugin) -> Session:
    return Session(
        session_id="datasource-session",
        executor=contract_plugin.executer,
        reader=contract_plugin.request_reader,
        writer=contract_plugin.default_response_writer,
    )


@pytest.fixture
def runtime() -> DatasourceRuntime:
    return DatasourceRuntime(
        credentials={"api_key": "valid"},
        user_id="user",
        session_id="datasource-session",
    )


@pytest.mark.parametrize("outcome", ["complete", "close", "error"])
def test_website_crawl_stream_status_errors_and_cleanup(
    contract_plugin: Plugin, session: Session, runtime: DatasourceRuntime, outcome: str
) -> None:
    datasource = contract_plugin.registration.get_website_crawl_datasource_cls(
        "website", "echo"
    )(runtime=runtime, session=session)
    stream = datasource.website_crawl({
        "url": "https://example.invalid/",
        "fail": outcome == "error",
    })
    assert not hasattr(datasource, "finished")
    first = next(stream)
    assert isinstance(first, WebsiteCrawlMessage)
    assert first.result.status == "processing"
    assert first.result.completed == 0
    assert not datasource.finished
    if outcome == "close":
        stream.close()
    elif outcome == "error":
        with pytest.raises(ValueError, match="crawl failed"):
            next(stream)
    else:
        last = next(stream)
        assert last.result.status == "completed"
        assert last.result.completed == last.result.total == 1
        assert last.result.web_info_list[0].source_url == "https://example.invalid/"
        assert last.result.web_info_list[0].content == "page content"
        with pytest.raises(StopIteration):
            next(stream)
    assert datasource.finished
    assert datasource.runtime.credentials == {"api_key": "valid"}
    assert datasource.session is session


def test_document_listing_drives_content_request_and_empty_result(
    contract_plugin: Plugin, session: Session, runtime: DatasourceRuntime
) -> None:
    datasource = contract_plugin.registration.get_online_document_datasource_cls(
        "documents", "echo"
    )(runtime=runtime, session=session)
    listing = datasource.get_pages({})
    assert len(listing.result) == 1
    workspace = listing.result[0]
    assert workspace.total == len(workspace.pages) == 1
    page = workspace.pages[0]
    stream = datasource.get_content(
        GetOnlineDocumentPageContentRequest(
            workspace_id=workspace.workspace_id, page_id=page.page_id, type=page.type
        )
    )
    assert not hasattr(datasource, "finished")
    messages = list(stream)
    assert all(isinstance(message, DatasourceMessage) for message in messages)
    assert all(
        message.type == DatasourceMessage.MessageType.VARIABLE for message in messages
    )
    assert {
        message.message.variable_name: message.message.variable_value
        for message in messages
    } == {"content": "page content", "page_id": "page", "workspace_id": "workspace"}
    assert datasource.finished
    assert datasource.get_pages({"empty": True}).result == []


@pytest.mark.parametrize("outcome", ["close", "error"])
def test_document_content_early_close_and_missing_page(
    contract_plugin: Plugin, session: Session, runtime: DatasourceRuntime, outcome: str
) -> None:
    datasource = contract_plugin.registration.get_online_document_datasource_cls(
        "documents", "echo"
    )(runtime=runtime, session=session)
    stream = datasource.get_content(
        GetOnlineDocumentPageContentRequest(
            workspace_id="workspace",
            page_id="missing" if outcome == "error" else "page",
            type="page",
        )
    )
    if outcome == "error":
        with pytest.raises(ValueError, match="page not found"):
            next(stream)
    else:
        assert next(stream).message.variable_name == "content"
        assert not datasource.finished
        stream.close()
    assert datasource.finished


def test_drive_pagination_keeps_cursor_bucket_and_remote_metadata(
    contract_plugin: Plugin, session: Session, runtime: DatasourceRuntime
) -> None:
    datasource = contract_plugin.registration.get_online_drive_datasource_cls(
        "drive", "echo"
    )(runtime=runtime, session=session)
    first = datasource.browse_files(
        OnlineDriveBrowseFilesRequest(bucket="bucket", prefix="folder", max_keys=1)
    ).result[0]
    assert first.bucket == "bucket"
    assert first.is_truncated
    assert first.next_page_parameters == {"cursor": "next"}
    assert first.files[0].id == "file"
    assert first.files[0].remote_metadata == {"etag": '"v1"'}
    last = datasource.browse_files(
        OnlineDriveBrowseFilesRequest(
            bucket=first.bucket,
            prefix="folder",
            max_keys=1,
            next_page_parameters=first.next_page_parameters,
        )
    ).result[0]
    assert last.bucket == first.bucket
    assert last.files[0].id == "last-file"
    assert not last.is_truncated
    assert last.next_page_parameters is None
    assert (
        datasource.browse_files(OnlineDriveBrowseFilesRequest(prefix="empty")).result
        == []
    )


@pytest.mark.parametrize("outcome", ["complete", "close", "error"])
def test_drive_download_preserves_binary_metadata_errors_and_cleanup(
    contract_plugin: Plugin, session: Session, runtime: DatasourceRuntime, outcome: str
) -> None:
    datasource = contract_plugin.registration.get_online_drive_datasource_cls(
        "drive", "echo"
    )(runtime=runtime, session=session)
    stream = datasource.download_file(
        OnlineDriveDownloadFileRequest(
            bucket="bucket", id="broken" if outcome == "error" else "file"
        )
    )
    assert not hasattr(datasource, "finished")
    message = next(stream)
    assert isinstance(message, DatasourceMessage)
    assert message.type == DatasourceMessage.MessageType.BLOB
    assert message.message.blob == b"data"
    assert message.meta == {"mime_type": "text/plain", "file_name": "example.txt"}
    assert not datasource.finished
    if outcome == "close":
        stream.close()
    elif outcome == "error":
        with pytest.raises(ValueError, match="download interrupted"):
            next(stream)
    else:
        with pytest.raises(StopIteration):
            next(stream)
    assert datasource.finished
