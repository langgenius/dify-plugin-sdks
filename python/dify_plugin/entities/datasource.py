from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, Field

from dify_plugin.entities.invoke_message import InvokeMessage

#########################
# Data source common message
#########################


class DatasourceMessage(InvokeMessage):
    pass


#########################
# Online document
#########################


class DatasourceRuntime(BaseModel):
    credentials: Mapping[str, Any]
    user_id: str | None
    session_id: str | None


class WebSiteInfoDetail(BaseModel):
    source_url: str = Field(..., description="The url of the website")
    content: str = Field(..., description="The content of the website")
    title: str = Field(..., description="The title of the website")
    description: str = Field(..., description="The description of the website")


class WebSiteInfo(BaseModel):
    """
    Website info
    """

    status: str | None = Field(..., description="crawl job status")
    web_info_list: list[WebSiteInfoDetail] | None = []
    total: int | None = Field(default=0, description="The total number of websites")
    completed: int | None = Field(default=0, description="The number of completed websites")


class WebsiteCrawlMessage(BaseModel):
    """
    Get website crawl response
    """

    result: WebSiteInfo


class OnlineDocumentPage(BaseModel):
    """
    Online document page
    """

    page_id: str = Field(..., description="The page id")
    page_name: str = Field(..., description="The page name")
    page_icon: dict | None = Field(None, description="The page icon")
    type: str = Field(..., description="The type of the page")
    last_edited_time: str = Field(..., description="The last edited time")
    parent_id: str | None = Field(None, description="The parent page id")


class OnlineDocumentInfo(BaseModel):
    """
    Online document info
    """

    workspace_id: str = Field(..., description="The workspace id")
    workspace_name: str = Field(..., description="The workspace name")
    workspace_icon: str = Field(..., description="The workspace icon")
    total: int = Field(..., description="The total number of documents")
    pages: list[OnlineDocumentPage] = Field(..., description="The pages of the online document")


class DatasourceGetPagesResponse(BaseModel):
    """
    Get online document pages response
    """

    result: list[OnlineDocumentInfo] = Field(..., description="The pages of the online document")


class GetOnlineDocumentPageContentRequest(BaseModel):
    """
    Get online document page content request
    """

    workspace_id: str = Field(..., description="The workspace id")
    page_id: str = Field(..., description="The page id")
    type: str = Field(..., description="The type of the page")


#########################
# Online drive file
#########################


class OnlineDriveFile(BaseModel):
    """
    Online drive file
    """

    id: str = Field(..., description="File ID")
    name: str = Field(..., description="File name")
    size: int = Field(..., description="File size")
    type: str = Field(..., description="File type (folder/file)")


class OnlineDriveFileBucket(BaseModel):
    """
    Online drive file bucket
    """

    bucket: str | None = Field(None, description="File bucket")
    files: list[OnlineDriveFile] = Field(..., description="File contents")
    is_truncated: bool = Field(..., description="Whether the result is truncated")
    next_page_parameters: dict | None = Field(None, description="Parameters for fetching the next page")


class OnlineDriveBrowseFilesRequest(BaseModel):
    """
    Get online drive file list request
    """

    bucket: str | None = Field(None, description="File bucket")
    prefix: str | None = Field(..., description="Parent ID")
    max_keys: int = Field(20, description="Page size")
    next_page_parameters: dict | None = Field(None, description="Parameters for fetching the next page")


class OnlineDriveBrowseFilesResponse(BaseModel):
    """
    Get online drive file list response
    """

    result: list[OnlineDriveFileBucket] = Field(..., description="File list")


class OnlineDriveDownloadFileRequest(BaseModel):
    """
    Get online drive file
    """

    bucket: str | None = Field(None, description="File bucket")
    id: str = Field(..., description="File ID")


class DatasourceOAuthCredentials(BaseModel):
    """
    DatasourceOAuth credentials
    """

    name: str | None = Field(None, description="The name of the OAuth credential")
    avatar_url: str | None = Field(None, description="The avatar url of the OAuth")
    credentials: Mapping[str, Any] = Field(..., description="The credentials of the OAuth")
    expires_at: int | None = Field(
        default=-1,
        description="""The expiration timestamp (in seconds since Unix epoch, UTC) of the credentials.
        Set to -1 or None if the credentials do not expire.""",
    )
