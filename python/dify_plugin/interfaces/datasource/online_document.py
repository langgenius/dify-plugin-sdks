from abc import abstractmethod
from collections.abc import Mapping, Generator
from typing import Any, final

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import (
    DatasourceRuntime,
    GetOnlineDocumentPageContentRequest,
    OnlineDocumentPagesMessage, DataSourceMessage, OnlineDocumentInfo,
)
from dify_plugin.interfaces.tool import ToolLike



class OnlineDocumentDatasource(ToolLike[DataSourceMessage]):
    """
    Online Document Datasource abstract class
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

    def create_pages_message(self, pages: list[OnlineDocumentInfo]) -> OnlineDocumentPagesMessage:
        return OnlineDocumentPagesMessage(result=pages)

    def get_pages(self, datasource_parameters: Mapping[str, Any]) -> Generator[OnlineDocumentPagesMessage, None, None]:
        """
        Get the pages
        """
        return self._get_pages(datasource_parameters)

    @abstractmethod
    def _get_pages(self, datasource_parameters: Mapping[str, Any]) ->  Generator[OnlineDocumentPagesMessage, None, None]:
        """
        Get the pages
        """
        raise NotImplementedError("This method should be implemented by a subclass")

    def get_content(self, page: GetOnlineDocumentPageContentRequest) -> Generator[DataSourceMessage, None, None]:
        """
        Get the content
        """
        return self._get_content(page)

    @abstractmethod
    def _get_content(self, page: GetOnlineDocumentPageContentRequest) -> Generator[DataSourceMessage, None, None]:
        """
        Get the content
        """
        raise NotImplementedError("This method should be implemented by a subclass")
