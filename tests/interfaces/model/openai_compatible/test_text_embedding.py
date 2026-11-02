from unittest.mock import Mock

import httpx2
import pytest

from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)


@pytest.mark.parametrize("error", [httpx2.ConnectError, httpx2.ReadTimeout])
def test_credential_request_failure_keeps_the_original_cause(
    monkeypatch: pytest.MonkeyPatch, error: type[httpx2.RequestError]
) -> None:
    failure = error("provider unavailable")
    monkeypatch.setattr(httpx2.Client, "send", Mock(side_effect=failure))
    with pytest.raises(CredentialsValidateFailedError) as caught:
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )
    assert caught.value.__cause__ is failure


def test_validation_uses_the_buffered_error_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx2.Response(401)
    monkeypatch.setattr(httpx2.Client, "send", Mock(return_value=response))
    with pytest.raises(CredentialsValidateFailedError, match="401"):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )
    assert response.is_closed
