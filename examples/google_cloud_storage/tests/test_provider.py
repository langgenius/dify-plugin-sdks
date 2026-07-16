from unittest.mock import patch

import pytest

from dify_plugin.errors.tool import ToolProviderCredentialValidationError
from examples.google_cloud_storage.provider import google_cloud_storage


def test_validation_probes_storage_access() -> None:
    with patch.object(
        google_cloud_storage.storage.Client,
        "from_service_account_info",
    ) as from_service_account_info:
        client = from_service_account_info.return_value
        client.list_buckets.return_value = iter(())
        google_cloud_storage.GoogleCloudStorageDatasourceProvider().validate_credentials({
            "credentials": "{}"
        })

    from_service_account_info.assert_called_once_with({})
    client.list_buckets.assert_called_once_with(max_results=1)


def test_validation_wraps_client_errors() -> None:
    with (
        patch.object(
            google_cloud_storage.storage.Client,
            "from_service_account_info",
            side_effect=ValueError("invalid credentials"),
        ),
        pytest.raises(
            ToolProviderCredentialValidationError,
            match="invalid credentials",
        ),
    ):
        google_cloud_storage.GoogleCloudStorageDatasourceProvider().validate_credentials({
            "credentials": "{}"
        })
