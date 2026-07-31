from unittest.mock import MagicMock, patch

import pytest

from dify_plugin.interfaces.model.openai_compatible.rerank import (
    OAICompatRerankModel,
)


@pytest.mark.parametrize(
    ("credentials", "expected_headers"),
    [
        (
            {"endpoint_url": "https://example.com/v1"},
            {"Content-Type": "application/json"},
        ),
        (
            {"endpoint_url": "https://example.com/v1", "api_key": None},
            {"Content-Type": "application/json"},
        ),
        (
            {"endpoint_url": "https://example.com/v1", "api_key": ""},
            {"Content-Type": "application/json"},
        ),
        (
            {"endpoint_url": "https://example.com/v1", "api_key": str(123)},
            {
                "Authorization": "Bearer 123",
                "Content-Type": "application/json",
            },
        ),
    ],
)
def test_invoke_only_sends_authorization_with_api_key(
    credentials: dict, expected_headers: dict[str, str]
) -> None:
    response = MagicMock()
    response.json.return_value = {"results": [{"index": 0, "relevance_score": 1.0}]}

    with patch(
        "dify_plugin.interfaces.model.openai_compatible.rerank.post",
        return_value=response,
    ) as post:
        OAICompatRerankModel([]).invoke(
            model="model",
            credentials=credentials,
            query="query",
            docs=["document"],
        )

    assert post.call_args.kwargs["headers"] == expected_headers
