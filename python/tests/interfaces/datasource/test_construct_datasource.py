from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.datasource import (
    DatasourceRuntime,
    GetOnlineDocumentPageContentRequest,
    GetOnlineDocumentPageContentResponse,
    GetOnlineDocumentPagesResponse,
    GetWebsiteCrawlResponse,
    OnlineDocumentPageContent,
)
from dify_plugin.interfaces.datasource.online_document import OnlineDocumentDatasource
from dify_plugin.interfaces.datasource.website import WebsiteCrawlDatasource


def test_construct_website_crawl_datasource():
    """
    Test WebsiteCrawlDatasource can be constructed in specific session
    """

    class Website(WebsiteCrawlDatasource):
        def _get_website_crawl(self, datasource_parameters: Mapping[str, Any]) -> GetWebsiteCrawlResponse:
            return GetWebsiteCrawlResponse(result=[])

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
        def _get_pages(self, datasource_parameters: Mapping[str, Any]) -> GetOnlineDocumentPagesResponse:
            return GetOnlineDocumentPagesResponse(result=[])

        def _get_content(self, page: GetOnlineDocumentPageContentRequest) -> GetOnlineDocumentPageContentResponse:
            return GetOnlineDocumentPageContentResponse(
                result=OnlineDocumentPageContent(
                    workspace_id="test",
                    page_id="test",
                    content="test",
                )
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
