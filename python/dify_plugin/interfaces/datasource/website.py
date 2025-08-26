from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from typing import Any, final

from dify_plugin.core.runtime import Session
from dify_plugin.entities.datasource import DatasourceRuntime, WebsiteCrawlMessage, WebSiteInfo


class WebsiteCrawlDatasource(ABC):
    """
    Website Crawl Datasource abstract class
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

    def create_crawl_message(self, website_info: WebSiteInfo) -> WebsiteCrawlMessage:
        return WebsiteCrawlMessage(result=website_info)

    def website_crawl(self, datasource_parameters: Mapping[str, Any]) -> Generator[WebsiteCrawlMessage, None, None]:
        """
        Get the website crawl result
        """
        return self._get_website_crawl(datasource_parameters)

    @abstractmethod
    def _get_website_crawl(
        self, datasource_parameters: Mapping[str, Any]
    ) -> Generator[WebsiteCrawlMessage, None, None]:
        """
        Get the website crawl result
        """
        raise NotImplementedError("This method should be implemented by a subclass")
