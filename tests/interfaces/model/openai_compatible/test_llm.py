from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from dify_plugin.interfaces.model.openai_compatible.llm import (
    OAICompatLargeLanguageModel,
)


@pytest.mark.parametrize(
    ("stream_mode_auth", "stream"),
    [("not_use", False), ("use", True)],
)
def test_validate_credentials_passes_extra_headers(
    stream_mode_auth: str,
    stream: bool,
) -> None:
    response = MagicMock(status_code=HTTPStatus.OK)
    response.json.return_value = {"object": "chat.completion"}
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
