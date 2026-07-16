from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)


def test_validate_credentials_rejects_non_object_response() -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = 1
    response.close.side_effect = OSError("close failed")

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.text_embedding.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError, match="invalid response"),
    ):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )

    response.close.assert_called_once_with()
