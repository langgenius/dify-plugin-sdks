from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

import requests

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from dify_plugin.interfaces.datasource import DatasourceProvider


class FirecrawlDatasourceProvider(DatasourceProvider):
    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        try:
            api_key = credentials.get("firecrawl_api_key", "")
            if not api_key:
                msg = "api key is required"
                raise ToolProviderCredentialValidationError(msg)

            base_url = credentials.get("base_url") or "https://api.firecrawl.dev"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }
            payload = {
                "url": "https://example.com",
                "includePaths": [],
                "excludePaths": [],
                "limit": 1,
                "scrapeOptions": {"onlyMainContent": True},
            }
            response = requests.post(
                f"{base_url}/v1/crawl",
                json=payload,
                headers=headers,
                timeout=10,
            )
            if response.status_code == HTTPStatus.OK:
                return True
            msg = "api key is invalid"
            raise ToolProviderCredentialValidationError(msg)

        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
