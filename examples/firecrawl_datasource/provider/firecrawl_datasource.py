from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

import urllib3_future

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from dify_plugin.interfaces.datasource import DatasourceProvider


class FirecrawlDatasourceProvider(DatasourceProvider):
    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        api_key = credentials.get("firecrawl_api_key", "")
        if not api_key:
            msg = "api key is required"
            raise ToolProviderCredentialValidationError(msg)

        base_url = credentials.get("base_url") or "https://api.firecrawl.dev"
        try:
            response = urllib3_future.request(
                "POST",
                f"{base_url}/v1/crawl",
                json={
                    "url": "https://example.com",
                    "includePaths": [],
                    "excludePaths": [],
                    "limit": 1,
                    "scrapeOptions": {"onlyMainContent": True},
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
        except urllib3_future.exceptions.HTTPError as e:
            raise ToolProviderCredentialValidationError(str(e)) from e

        if response.status != HTTPStatus.OK:
            msg = "api key is invalid"
            raise ToolProviderCredentialValidationError(msg)
