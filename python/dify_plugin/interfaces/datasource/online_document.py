from abc import abstractmethod
from collections.abc import Generator, Mapping
from typing import Any, final

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import (
    DatasourceGetPagesResponse,
    DatasourceMessage,
    DatasourceRuntime,
    GetOnlineDocumentPageContentRequest,
)
from dify_plugin.interfaces.tool import ToolLike


class OnlineDocumentDatasource(ToolLike[DatasourceMessage]):
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
        self.response_type = DatasourceMessage

    def get_pages(self, datasource_parameters: Mapping[str, Any]) -> DatasourceGetPagesResponse:
        """
        Get the pages
        """
        return self._get_pages(datasource_parameters)

    @abstractmethod
    def _get_pages(self, datasource_parameters: Mapping[str, Any]) -> DatasourceGetPagesResponse:
        """
        Get the pages
        """
        raise NotImplementedError("This method should be implemented by a subclass")

    def get_content(self, page: GetOnlineDocumentPageContentRequest) -> Generator[DatasourceMessage, None, None]:
        """
        Get the content
        """
        return self._get_content(page)

    @abstractmethod
    def _get_content(self, page: GetOnlineDocumentPageContentRequest) -> Generator[DatasourceMessage, None, None]:
        """
        Get the content
        """
        raise NotImplementedError("This method should be implemented by a subclass")
