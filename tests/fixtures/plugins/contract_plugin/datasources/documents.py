from collections.abc import Generator, Mapping
from typing import Any

from dify_plugin.entities.datasource import (
    DatasourceGetPagesResponse,
    DatasourceMessage,
    GetOnlineDocumentPageContentRequest,
    OnlineDocumentInfo,
    OnlineDocumentPage,
)
from dify_plugin.interfaces.datasource.online_document import OnlineDocumentDatasource


class ContractDocuments(OnlineDocumentDatasource):
    def _get_pages(
        self, datasource_parameters: Mapping[str, Any]
    ) -> DatasourceGetPagesResponse:
        if datasource_parameters.get("empty"):
            return DatasourceGetPagesResponse(result=[])
        return DatasourceGetPagesResponse(
            result=[
                OnlineDocumentInfo(
                    workspace_id="workspace",
                    workspace_name="Documents",
                    workspace_icon="",
                    total=1,
                    pages=[
                        OnlineDocumentPage(
                            page_id="page",
                            page_name="Example",
                            type="page",
                            last_edited_time="2026-01-01T00:00:00Z",
                        )
                    ],
                )
            ]
        )

    def _get_content(
        self, page: GetOnlineDocumentPageContentRequest
    ) -> Generator[DatasourceMessage]:
        self.finished = False
        try:
            if page.page_id == "missing":
                msg = "page not found"
                raise ValueError(msg)
            yield self.create_variable_message("content", "page content")
            yield self.create_variable_message("page_id", page.page_id)
            yield self.create_variable_message("workspace_id", page.workspace_id)
        finally:
            self.finished = True
