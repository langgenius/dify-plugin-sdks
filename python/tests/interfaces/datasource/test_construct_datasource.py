from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.datasource import (
    DatasourceGetPagesResponse,
    DatasourceMessage,
    DatasourceRuntime,
    GetOnlineDocumentPageContentRequest,
)
from dify_plugin.interfaces.datasource.online_document import OnlineDocumentDatasource
from dify_plugin.interfaces.datasource.website import WebsiteCrawlDatasource


def test_construct_website_crawl_datasource():
    """
    Test WebsiteCrawlDatasource can be constructed in specific session
    """

    class Website(WebsiteCrawlDatasource):
        def _get_website_crawl(
            self, datasource_parameters: Mapping[str, Any]
        ) -> Generator[DatasourceMessage, None, None]:
            yield DatasourceMessage(
                type=DatasourceMessage.MessageType.TEXT,
                message=DatasourceMessage.TextMessage(
                    text=f"Website crawl result for {datasource_parameters.get('url', 'unknown')}"
                ),
            )

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    datasource = Website(runtime=DatasourceRuntime(credentials={}, user_id="test", session_id="test"), session=session)
    assert datasource is not None


def test_construct_online_document_datasource():
    """
    Test OnlineDocumentDatasource can be constructed in specific session
    """

    class OnlineDocument(OnlineDocumentDatasource):
        def _get_pages(self, datasource_parameters: Mapping[str, Any]) -> DatasourceGetPagesResponse:
            return DatasourceGetPagesResponse(result=[])

        def _get_content(self, page: GetOnlineDocumentPageContentRequest) -> Generator[DatasourceMessage, None, None]:
            yield DatasourceMessage(
                type=DatasourceMessage.MessageType.TEXT,
                message=DatasourceMessage.TextMessage(
                    text=f"Online document page content for {page.workspace_id} - {page.page_id}"
                ),
            )

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    datasource = OnlineDocument(
        runtime=DatasourceRuntime(credentials={}, user_id="test", session_id="test"), session=session
    )
    assert datasource is not None
