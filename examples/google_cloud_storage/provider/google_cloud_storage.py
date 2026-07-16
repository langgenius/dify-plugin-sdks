import json
from collections.abc import Mapping
from typing import Any

from google.cloud import storage

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from dify_plugin.interfaces.datasource import DatasourceProvider


class GoogleCloudStorageDatasourceProvider(DatasourceProvider):
    def _validate_credentials(self, credentials: Mapping[str, Any]) -> None:
        credentials_json = credentials.get("credentials")
        if not credentials_json:
            msg = "Google Cloud Storage credentials are required."
            raise ToolProviderCredentialValidationError(msg)
        if not isinstance(credentials_json, str):
            msg = "Google Cloud Storage credentials must be a string json."
            raise ToolProviderCredentialValidationError(msg)

        try:
            client = storage.Client.from_service_account_info(
                json.loads(credentials_json)
            )
            next(client.list_buckets(max_results=1), None)
        except Exception as e:
            raise ToolProviderCredentialValidationError(str(e)) from e
