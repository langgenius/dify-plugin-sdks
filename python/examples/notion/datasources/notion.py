from collections.abc import Mapping
from typing import Any

from dify_plugin.entities.datasource import (
    GetOnlineDocumentPageContentRequest,
    GetOnlineDocumentPageContentResponse,
    GetOnlineDocumentPagesResponse,
    OnlineDocumentPageContent,
)
from dify_plugin.interfaces.datasource.online_document import OnlineDocumentDatasource


class NotionDatasource(OnlineDocumentDatasource):
    def _get_pages(self, datasource_parameters: Mapping[str, Any]) -> GetOnlineDocumentPagesResponse:
        return GetOnlineDocumentPagesResponse(result=[])

    def _get_content(self, page: GetOnlineDocumentPageContentRequest) -> GetOnlineDocumentPageContentResponse:
        return GetOnlineDocumentPageContentResponse(
            result=OnlineDocumentPageContent(
                content="",
                workspace_id="",
                page_id="",
            )
        )
