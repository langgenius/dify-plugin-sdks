from http import HTTPStatus
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from dify_plugin.errors.model import CredentialsValidateFailedError
from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


@pytest.mark.parametrize(
    ("stream_mode_auth", "stream", "max_tokens"),
    [("not_use", False, 5), ("use", True, 10)],
)
def test_validate_credentials_passes_extra_headers(
    stream_mode_auth: str,
    stream: bool,
    max_tokens: int,
) -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = {"object": "chat.completion"}
    response.close.side_effect = RuntimeError("close failed")
    api_key = str(123)
    credentials = {
        "api_key": api_key,
        "endpoint_url": "https://example.com/v1",
        "extra_headers": {
            "Authorization": str(456),
            "Content-Type": "application/custom+json",
            "X-Api-Key": str(789),
        },
        "mode": "chat",
        "stream_mode_auth": stream_mode_auth,
    }

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        return_value=response,
    ) as post:
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    assert post.call_args.kwargs["headers"] == {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/custom+json",
        "X-Api-Key": str(789),
    }
    assert post.call_args.kwargs.get("stream", False) is stream
    assert post.call_args.kwargs["json"]["max_tokens"] == max_tokens
    response.close.assert_called_once()


@pytest.mark.parametrize("extra_headers", [False, "", [], [("X-Api-Key", "value")]])
def test_validate_credentials_rejects_non_mapping_extra_headers(
    extra_headers: object,
) -> None:
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "extra_headers": extra_headers,
        "mode": "chat",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
        ) as post,
        pytest.raises(CredentialsValidateFailedError),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    post.assert_not_called()


def test_validate_credentials_wraps_unreadable_error_response() -> None:
    response = MagicMock(status_code=HTTPStatus.BAD_REQUEST)
    type(response).text = PropertyMock(side_effect=RuntimeError("broken body"))
    response.close.side_effect = RuntimeError("close failed")
    credentials = {
        "endpoint_url": "https://example.com/v1",
        "mode": "chat",
        "stream_mode_auth": "use",
    }

    with (
        patch(
            "dify_plugin.interfaces.model.openai_compatible.llm.requests.post",
            return_value=response,
        ),
        pytest.raises(CredentialsValidateFailedError, match="broken body"),
    ):
        OAICompatLargeLanguageModel([]).validate_credentials("model", credentials)

    response.close.assert_called_once()
