from collections.abc import Generator, Mapping
from typing import Any

from dify_plugin.entities.datasource import (
    WebsiteCrawlMessage,
    WebSiteInfo,
    WebSiteInfoDetail,
)
from dify_plugin.interfaces.datasource.website import WebsiteCrawlDatasource


class ContractWebsite(WebsiteCrawlDatasource):
    def _get_website_crawl(
        self, datasource_parameters: Mapping[str, Any]
    ) -> Generator[WebsiteCrawlMessage]:
        self.finished = False
        try:
            yield self.create_crawl_message(
                WebSiteInfo(status="processing", total=1, completed=0)
            )
            if datasource_parameters.get("fail"):
                msg = "crawl failed"
                raise ValueError(msg)
            yield self.create_crawl_message(
                WebSiteInfo(
                    status="completed",
                    total=1,
                    completed=1,
                    web_info_list=[
                        WebSiteInfoDetail(
                            source_url=datasource_parameters["url"],
                            content="page content",
                            title="Example",
                            description="Local test page",
                        )
                    ],
                )
            )
        finally:
            self.finished = True
