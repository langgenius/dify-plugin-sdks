from unittest.mock import Mock

import pytest
import requests

from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)


@pytest.mark.parametrize("error", [requests.ConnectionError, requests.Timeout])
def test_credential_request_failure_keeps_the_original_cause(
    monkeypatch: pytest.MonkeyPatch, error: type[requests.RequestException]
) -> None:
    failure = error("provider unavailable")
    monkeypatch.setattr(requests, "post", Mock(side_effect=failure))

    with pytest.raises(CredentialsValidateFailedError) as caught:
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )

    assert caught.value.__cause__ is failure


def test_response_close_failure_keeps_the_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = requests.Response()
    response.status_code = 401
    close = Mock(side_effect=OSError("close failed"))
    monkeypatch.setattr(response, "close", close)
    monkeypatch.setattr(requests, "post", Mock(return_value=response))

    with pytest.raises(CredentialsValidateFailedError, match="401"):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )

    close.assert_called_once_with()
