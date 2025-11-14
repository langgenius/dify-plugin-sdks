from collections.abc import Mapping

from dify_plugin.entities.datasource_manifest import DatasourceProviderManifest
from dify_plugin.interfaces.datasource import DatasourceProvider
from dify_plugin.interfaces.datasource.online_document import OnlineDocumentDatasource
from dify_plugin.interfaces.datasource.online_drive import OnlineDriveDatasource
from dify_plugin.interfaces.datasource.website import WebsiteCrawlDatasource


class DatasourceProviderMapping:
    """
    mapping of datasource provider to datasource provider configuration
    """

    provider: str
    configuration: DatasourceProviderManifest
    provider_cls: type[DatasourceProvider]

    website_crawl_datasource_mapping: Mapping[str, type[WebsiteCrawlDatasource]]
    online_document_datasource_mapping: Mapping[str, type[OnlineDocumentDatasource]]
    online_drive_datasource_mapping: Mapping[str, type[OnlineDriveDatasource]]

    def __init__(
        self,
        provider: str,
        provider_cls: type[DatasourceProvider],
        configuration: DatasourceProviderManifest,
        website_crawl_datasource_mapping: Mapping[str, type[WebsiteCrawlDatasource]] | None = None,
        online_document_datasource_mapping: Mapping[str, type[OnlineDocumentDatasource]] | None = None,
        online_drive_datasource_mapping: Mapping[str, type[OnlineDriveDatasource]] | None = None,
    ) -> None:
        self.provider = provider
        self.provider_cls = provider_cls
        self.configuration = configuration
        self.website_crawl_datasource_mapping = website_crawl_datasource_mapping or {}
        self.online_document_datasource_mapping = online_document_datasource_mapping or {}
        self.online_drive_datasource_mapping = online_drive_datasource_mapping or {}
