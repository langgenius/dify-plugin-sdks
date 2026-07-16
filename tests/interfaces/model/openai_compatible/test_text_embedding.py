from http import HTTPStatus
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)


class DuckEmbeddingResponse:
    def __init__(self) -> None:
        self.trace: list[str] = []

    def __contains__(self, key: object) -> bool:
        del key
        self.trace.append("contains")
        return True


class UnstringableResponseError(Exception):
    def __init__(self, error: RuntimeError) -> None:
        super().__init__()
        self.error = error

    def __str__(self) -> str:
        raise self.error


def test_validate_credentials_rejects_non_object_response() -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = 1
    response.close.side_effect = OSError("close failed")

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.text_embedding.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError),
    ):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )

    response.close.assert_called_once_with()


def test_validate_credentials_wraps_response_inspection_errors() -> None:
    response = MagicMock()
    type(response).status_code = PropertyMock(
        side_effect=RuntimeError("broken status"),
    )

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.text_embedding.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError, match="broken status"),
    ):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model", {"endpoint_url": "https://example.com/v1"}
        )

    response.close.assert_called_once_with()


def test_validate_credentials_wraps_credential_preparation_errors() -> None:
    error_message = "lazy credentials failed"
    sentinel = CredentialsValidateFailedError(error_message)
    credentials = MagicMock()
    credentials.get.side_effect = sentinel

    with pytest.raises(CredentialsValidateFailedError) as exc_info:
        OAICompatEmbeddingModel([]).validate_credentials(
            "model",
            credentials,
        )

    assert exc_info.value is sentinel


def test_validate_credentials_accepts_duck_typed_response() -> None:
    json_result = DuckEmbeddingResponse()
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = json_result

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.text_embedding.requests.post",
        return_value=response,
    ):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model",
            {"endpoint_url": "https://example.com/v1"},
        )

    assert json_result.trace == ["contains"]


def test_validate_credentials_preserves_response_credential_errors() -> None:
    sentinel = CredentialsValidateFailedError("response failed")
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.side_effect = sentinel

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.text_embedding.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError) as exc_info,
    ):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model",
            {"endpoint_url": "https://example.com/v1"},
        )

    assert exc_info.value is sentinel


def test_validate_credentials_preserves_string_conversion_errors() -> None:
    sentinel = RuntimeError()
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.side_effect = UnstringableResponseError(sentinel)

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.text_embedding.requests.post",
            return_value=response,
        ),
        pytest.raises(RuntimeError) as exc_info,
    ):
        OAICompatEmbeddingModel([]).validate_credentials(
            "model",
            {"endpoint_url": "https://example.com/v1"},
        )

    assert exc_info.value is sentinel
