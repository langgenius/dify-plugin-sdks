from collections.abc import Mapping, Generator
from typing import Any

from dify_plugin.entities.datasource import (
    GetOnlineDocumentPageContentRequest,
    OnlineDocumentPagesMessage,
    DataSourceMessage, OnlineDocumentPage, OnlineDocumentInfo,
)
from dify_plugin.interfaces.datasource.online_document import OnlineDocumentDatasource


class NotionDatasource(OnlineDocumentDatasource):
    _NOTION_PAGE_SEARCH = "https://api.notion.com/v1/search"
    _NOTION_BLOCK_SEARCH = "https://api.notion.com/v1/blocks"
    _NOTION_BOT_USER = "https://api.notion.com/v1/users/me"

    def _get_pages(self, datasource_parameters: Mapping[str, Any]) -> Generator[OnlineDocumentPagesMessage, None, None]:
        yield self.create_pages_message(
            pages=[
                OnlineDocumentInfo(
                    workspace_id=datasource_parameters["workspace_id"],
                    workspace_name=datasource_parameters["workspace_name"],
                    workspace_icon=datasource_parameters["workspace_icon"],
                    total=1,
                    pages=[
                        OnlineDocumentPage(
                            page_id="page_id",
                            page_title="page_title",
                            page_icon=None,
                            type="type",
                            last_edited_time="last_edited_time",
                        )
                    ],
                )
            ]
        )

    def _get_content(self, page: GetOnlineDocumentPageContentRequest) -> Generator[
        DataSourceMessage, None, None]:
        yield DataSourceMessage(
            type=DataSourceMessage.Type.TEXT,
            message=DataSourceMessage.TextMessage(
                text=f"Notion page content for {page.workspace_id} - {page.page_id}"
            )
        )
