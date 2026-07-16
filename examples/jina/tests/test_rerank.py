from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from dify_plugin.errors.model import InvokeRateLimitError
from examples.jina.models.rerank import rerank


def test_rerank_uses_urllib3_future() -> None:
    response = MagicMock(status=HTTPStatus.TOO_MANY_REQUESTS)
    response.json.return_value = {"detail": "slow down"}

    with (
        patch.object(
            rerank.urllib3_future,
            "request",
            return_value=response,
        ) as request,
        pytest.raises(InvokeRateLimitError, match="slow down"),
    ):
        rerank.JinaRerankModel([]).invoke(
            model="jina-reranker-v2-base-multilingual",
            credentials={"api_key": "test"},
            query="query",
            docs=["document"],
        )

    request.assert_called_once_with(
        "POST",
        "https://api.jina.ai/v1/rerank",
        json={
            "model": "jina-reranker-v2-base-multilingual",
            "query": "query",
            "documents": ["document"],
            "top_n": None,
        },
        headers={"Authorization": "Bearer test"},
        timeout=5,
    )
