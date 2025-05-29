from collections.abc import Mapping
from typing import Any, Optional

from pydantic import BaseModel, Field


class DatasourceRuntime(BaseModel):
    credentials: Mapping[str, Any]
    user_id: Optional[str]
    session_id: Optional[str]


class WebSiteInfo(BaseModel):
    """
    Website info
    """

    source_url: str = Field(..., description="The url of the website")
    content: str = Field(..., description="The content of the website")
    title: str = Field(..., description="The title of the website")
    description: str = Field(..., description="The description of the website")


class GetWebsiteCrawlResponse(BaseModel):
    """
    Get website crawl response
    """

    result: list[WebSiteInfo]


class OnlineDocumentPageIcon(BaseModel):
    """
    Online document page icon
    """

    type: str = Field(..., description="The type of the icon")
    url: str = Field(..., description="The url of the icon")


class OnlineDocumentPage(BaseModel):
    """
    Online document page
    """

    page_id: str = Field(..., description="The page id")
    page_title: str = Field(..., description="The page title")
    page_icon: Optional[OnlineDocumentPageIcon] = Field(None, description="The page icon")
    type: str = Field(..., description="The type of the page")
    last_edited_time: str = Field(..., description="The last edited time")


class OnlineDocumentInfo(BaseModel):
    """
    Online document info
    """

    workspace_id: str = Field(..., description="The workspace id")
    workspace_name: str = Field(..., description="The workspace name")
    workspace_icon: str = Field(..., description="The workspace icon")
    total: int = Field(..., description="The total number of documents")
    pages: list[OnlineDocumentPage] = Field(..., description="The pages of the online document")


class GetOnlineDocumentPagesResponse(BaseModel):
    """
    Get online document pages response
    """

    result: list[OnlineDocumentInfo]


class GetOnlineDocumentPageContentRequest(BaseModel):
    """
    Get online document page content request
    """

    workspace_id: str = Field(..., description="The workspace id")
    page_id: str = Field(..., description="The page id")
    type: str = Field(..., description="The type of the page")


class OnlineDocumentPageContent(BaseModel):
    """
    Online document page content
    """

    workspace_id: str = Field(..., description="The workspace id")
    page_id: str = Field(..., description="The page id")
    content: str = Field(..., description="The content of the page")


class GetOnlineDocumentPageContentResponse(BaseModel):
    """
    Get online document page content response
    """

    result: OnlineDocumentPageContent
