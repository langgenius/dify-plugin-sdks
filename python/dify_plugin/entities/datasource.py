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

    key: str = Field(..., description="The key of the file")
    size: int = Field(..., description="The size of the file")


class OnlineDriveFileBucket(BaseModel):
    """
    Online drive file bucket
    """

    bucket: str | None = Field(..., description="The bucket of the file")
    files: list[OnlineDriveFile] = Field(..., description="The files of the bucket")
    is_truncated: bool = Field(..., description="Whether the bucket has more files")


class OnlineDriveBrowseFilesRequest(BaseModel):
    """
    Get online drive file list request
    """

    prefix: str | None = Field(None, description="File path prefix for filtering eg: 'docs/dify/'")
    bucket: str | None = Field(None, description="Storage bucket name")
    max_keys: int = Field(20, description="Maximum number of files to return")
    start_after: str | None = Field(
        None, description="Pagination token for continuing from a specific file eg: 'docs/dify/1.txt'"
    )


class OnlineDriveBrowseFilesResponse(BaseModel):
    """
    Get online drive file list response
    """

    result: list[OnlineDriveFileBucket] = Field(..., description="The bucket of the files")


class OnlineDriveDownloadFileRequest(BaseModel):
    """
    Get online drive file
    """

    key: str = Field(..., description="The name of the file")
    bucket: str | None = Field(None, description="The name of the bucket")
