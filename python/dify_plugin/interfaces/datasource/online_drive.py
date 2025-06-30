from abc import abstractmethod
from collections.abc import Generator
from typing import final

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import (
    DataSourceMessage,
    DatasourceRuntime,
    OnlineDriveBrowseFilesRequest,
    OnlineDriveBrowseFilesResponse,
    OnlineDriveDownloadFileRequest,
    OnlineDriveFileBucket,
)
from dify_plugin.interfaces.tool import ToolLike


class OnlineDriveDatasource(ToolLike[DataSourceMessage]):
    """
    Online Drive Datasource abstract class
    """

    runtime: DatasourceRuntime
    session: Session

    @final
    def __init__(
        self,
        runtime: DatasourceRuntime,
        session: Session,
    ):
        """
        Initialize the datasource

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.runtime = runtime
        self.session = session
        self.response_type = DataSourceMessage

    def browse_files(self, request: OnlineDriveBrowseFilesRequest) -> OnlineDriveBrowseFilesResponse:
        """
        Get the file list
        """
        return OnlineDriveBrowseFilesResponse(result=self._browse_files(request))

    @abstractmethod
    def _browse_files(self, request: OnlineDriveBrowseFilesRequest) -> list[OnlineDriveFileBucket]:
        """
        Browse the files
        """
        raise NotImplementedError("This method should be implemented by a subclass")

    def download_file(self, request: OnlineDriveDownloadFileRequest) -> Generator[DataSourceMessage, None, None]:
        """
        Get the file content
        """
        return self._download_file(request)

    @abstractmethod
    def _download_file(self, request: OnlineDriveDownloadFileRequest) -> Generator[DataSourceMessage, None, None]:
        """
        Download the file content
        """
        raise NotImplementedError("This method should be implemented by a subclass")
