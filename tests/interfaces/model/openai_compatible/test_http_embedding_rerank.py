import json
from decimal import Decimal

import pytest

from dify_plugin.entities import I18nObject
from dify_plugin.entities.model import (
    AIModelEntity,
    ModelPropertyKey,
    ModelType,
    PriceConfig,
)
from dify_plugin.errors.model import CredentialsValidateFailedError, InvokeError
from dify_plugin.interfaces.model.openai_compatible.rerank import OAICompatRerankModel
from dify_plugin.interfaces.model.openai_compatible.text_embedding import (
    OAICompatEmbeddingModel,
)
from tests.http_server import HTTPServerFactory, Response

pytestmark = pytest.mark.integration


@pytest.fixture
def embedding(monkeypatch: pytest.MonkeyPatch) -> OAICompatEmbeddingModel:
    model = OAICompatEmbeddingModel([
        AIModelEntity(
            model="model",
            label=I18nObject(en_us="model"),
            model_type=ModelType.TEXT_EMBEDDING,
            model_properties={
                ModelPropertyKey.CONTEXT_SIZE: 5,
                ModelPropertyKey.MAX_CHUNKS: 2,
            },
            parameter_rules=[],
            pricing=PriceConfig(input=Decimal(2), unit=Decimal("0.01"), currency="USD"),
        )
    ])
    monkeypatch.setattr(model, "_get_num_tokens_by_gpt2", len)
    return model


def test_embedding_batches_truncates_and_accumulates_usage(
    http_server: HTTPServerFactory, embedding: OAICompatEmbeddingModel
) -> None:
    server = http_server([
        Response(
            body=b'{"data":[{"embedding":[1,2]},{"embedding":[3,4]}],"usage":{"total_tokens":5}}'
        ),
        Response(body=b'{"data":[{"embedding":[5,6]}],"usage":{"total_tokens":2}}'),
    ])
    result = embedding.invoke(
        "model",
        {
            "endpoint_url": f"{server.url}/v1/",
            "endpoint_model_name": "upstream-model",
            "api_key": "key",
        },
        ["abcdef", "你好", ""],
        user="user-1",
    )

    assert result.embeddings == [[1, 2], [3, 4], [5, 6]]
    assert result.model == "model"
    assert result.usage.total_tokens == 7
    assert result.usage.total_price == Decimal("0.14")
    assert result.usage.latency >= 0
    assert embedding.started_at == 0
    requests = server.requests
    assert [request.path for request in requests] == [
        "/v1/embeddings",
        "/v1/embeddings",
    ]
    assert all(request.headers["Authorization"] == "Bearer key" for request in requests)
    payloads = [json.loads(request.body) for request in requests]
    assert [payload["input"] for payload in payloads] == [["abcde", "你好"], [""]]
    assert all(payload["model"] == "upstream-model" for payload in payloads)
    assert all(payload["encoding_format"] == "float" for payload in payloads)
    assert all(payload["user"] == "user-1" for payload in payloads)


def test_embedding_empty_input_does_not_request_the_server(
    http_server: HTTPServerFactory, embedding: OAICompatEmbeddingModel
) -> None:
    server = http_server([])
    result = embedding.invoke("model", {"endpoint_url": server.url}, [])
    assert result.embeddings == []
    assert result.usage.total_tokens == 0
    assert server.requests == []


@pytest.mark.parametrize(
    "response",
    [
        Response(status=429, body=b"rate limited"),
        Response(body=b"not json"),
        Response(body=b'{"data":[],"usage":{"total_tokens":0}}'),
    ],
)
def test_embedding_failure_stops_later_batches(
    http_server: HTTPServerFactory,
    embedding: OAICompatEmbeddingModel,
    response: Response,
) -> None:
    server = http_server([
        response,
        Response(body=b'{"data":[{"embedding":[5,6]}],"usage":{"total_tokens":1}}'),
    ])
    try:
        with pytest.raises(InvokeError):
            embedding.invoke(
                "model", {"endpoint_url": server.url}, ["one", "two", "three"]
            )
    finally:
        assert len(server.requests) == 1
        assert embedding.started_at == 0


@pytest.mark.parametrize("reordered", [False, True])
def test_embedding_never_assigns_a_response_index_to_the_wrong_input(
    http_server: HTTPServerFactory,
    embedding: OAICompatEmbeddingModel,
    reordered: bool,
) -> None:
    batch = [{"index": 0, "embedding": [1, 2]}, {"index": 1, "embedding": [3, 4]}]
    if reordered:
        batch.reverse()
    server = http_server([
        Response(
            body=json.dumps({"data": batch, "usage": {"total_tokens": 2}}).encode()
        ),
        Response(
            body=b'{"data":[{"index":0,"embedding":[5,6]}],"usage":{"total_tokens":1}}'
        ),
    ])

    result = embedding.invoke(
        "model", {"endpoint_url": server.url}, ["one", "two", "three"]
    )

    assert result.embeddings == [[1, 2], [3, 4], [5, 6]]
    assert result.usage.total_tokens == 3
    assert [json.loads(request.body)["input"] for request in server.requests] == [
        ["one", "two"],
        ["three"],
    ]
    assert embedding.started_at == 0


@pytest.mark.parametrize(
    "data_json",
    [
        '[{"index":0,"embedding":[1,2]}]',
        '[{"index":0,"embedding":[1,2]},{"index":0,"embedding":[3,4]}]',
        '[{"index":0,"embedding":[1,2]},{"index":2,"embedding":[3,4]}]',
        '[{"index":0,"embedding":[]},{"index":1,"embedding":[3,4]}]',
        '[{"index":0,"embedding":[1e400,1]},{"index":1,"embedding":[3,4]}]',
    ],
    ids=[
        "missing-vector",
        "duplicate-index",
        "out-of-range-index",
        "empty-vector",
        "non-finite-vector",
    ],
)
def test_invalid_embedding_batch_fails_before_requesting_the_next_batch(
    http_server: HTTPServerFactory, embedding: OAICompatEmbeddingModel, data_json: str
) -> None:
    server = http_server([
        Response(body=f'{{"data":{data_json},"usage":{{"total_tokens":2}}}}'.encode()),
        Response(body=b'{"data":[{"embedding":[5,6]}],"usage":{"total_tokens":1}}'),
    ])

    try:
        with pytest.raises(InvokeError):
            embedding.invoke(
                "model", {"endpoint_url": server.url}, ["one", "two", "three"]
            )
    finally:
        assert len(server.requests) == 1
        assert embedding.started_at == 0


def test_embedding_uses_safe_batch_defaults_when_schema_omits_limits(
    http_server: HTTPServerFactory,
) -> None:
    server = http_server([
        Response(body=b'{"data":[{"embedding":[1,2]}],"usage":{"total_tokens":1}}'),
        Response(body=b'{"data":[{"embedding":[3,4]}],"usage":{"total_tokens":1}}'),
    ])
    model = OAICompatEmbeddingModel([
        AIModelEntity(
            model="model", model_type=ModelType.TEXT_EMBEDDING, model_properties={}
        )
    ])

    result = model.invoke("model", {"endpoint_url": server.url}, ["Hello", "World"])

    assert result.embeddings == [[1, 2], [3, 4]]
    assert result.usage.total_tokens == 2
    assert [json.loads(request.body)["input"] for request in server.requests] == [
        ["Hello"],
        ["World"],
    ]


@pytest.mark.parametrize(
    ("response", "valid"),
    [
        (Response(body=b'{"model":"upstream"}'), True),
        (Response(status=401, body=b"unauthorized"), False),
        (Response(body=b"not json"), False),
        (Response(body=b"{}"), False),
        (Response(body=b"1"), False),
        (Response(body=b'"model"'), False),
        (Response(body=b'["model"]'), False),
    ],
)
def test_embedding_validates_credentials_over_http(
    http_server: HTTPServerFactory, response: Response, valid: bool
) -> None:
    server = http_server([response])
    model = OAICompatEmbeddingModel([])
    credentials = {"endpoint_url": server.url, "api_key": "key"}
    if valid:
        model.validate_credentials("model", credentials)
    else:
        with pytest.raises(CredentialsValidateFailedError):
            model.validate_credentials("model", credentials)
    request = server.requests[0]
    assert request.path == "/embeddings"
    assert request.headers["Authorization"] == "Bearer key"
    assert json.loads(request.body) == {"input": ["ping"], "model": "model"}


@pytest.mark.parametrize("threshold", [None, 0.5])
def test_rerank_uses_response_indices_documents_and_normalized_scores(
    http_server: HTTPServerFactory, threshold: float | None
) -> None:
    server = http_server([
        Response(
            body=json.dumps({
                "results": [
                    {
                        "index": 2,
                        "relevance_score": -2,
                        "document": {"text": "replacement"},
                    },
                    {"index": 0, "relevance_score": -4, "document": "original"},
                    {"index": 1, "relevance_score": 0},
                ]
            }).encode()
        )
    ])
    model = OAICompatRerankModel([])
    result = model.invoke(
        "model",
        {"endpoint_url": server.url, "endpoint_model_name": "reranker"},
        "query",
        ["zero", "one", "two"],
        score_threshold=threshold,
        top_n=3,
    )

    expected = [(1, "one", 1), (2, "replacement", 0.5)]
    if threshold is None:
        expected.append((0, "original", 0))
    assert [(doc.index, doc.text, doc.score) for doc in result.docs] == expected
    request = server.requests[0]
    assert request.path == "/rerank"
    assert "Authorization" not in request.headers
    assert json.loads(request.body) == {
        "model": "reranker",
        "query": "query",
        "documents": ["zero", "one", "two"],
        "top_n": 3,
        "return_documents": True,
    }
    assert model.started_at == 0


def test_rerank_accepts_empty_results(http_server: HTTPServerFactory) -> None:
    server = http_server([Response(body=b'{"results":[]}')])
    result = OAICompatRerankModel([]).invoke(
        "model", {"endpoint_url": server.url}, "query", ["document"]
    )
    assert result.docs == []


def test_rerank_empty_documents_does_not_request_the_server(
    http_server: HTTPServerFactory,
) -> None:
    server = http_server([])
    result = OAICompatRerankModel([]).invoke(
        "model", {"endpoint_url": server.url}, "query", []
    )
    assert result.docs == []
    assert server.requests == []


def test_rerank_equal_scores_remain_finite(http_server: HTTPServerFactory) -> None:
    server = http_server([
        Response(
            body=b'{"results":[{"index":0,"relevance_score":2},{"index":1,"relevance_score":2}]}'
        )
    ])
    result = OAICompatRerankModel([]).invoke(
        "model", {"endpoint_url": server.url}, "query", ["first", "second"]
    )
    assert [(doc.text, doc.score) for doc in result.docs] == [
        ("first", 0),
        ("second", 0),
    ]


@pytest.mark.parametrize(
    ("scores", "threshold", "expected"),
    [
        ([0.9], 0.5, [(0, 0.9)]),
        ([0.8, 0.9], 0.5, [(1, 0.9), (0, 0.8)]),
        ([0.8, 0.9], 0.9, [(1, 0.9)]),
        ([0.9, 0.9], 0.5, [(0, 0.9), (1, 0.9)]),
        ([0.0, 1.0], None, [(1, 1.0), (0, 0.0)]),
    ],
)
def test_rerank_preserves_normalized_scores_and_thresholds(
    http_server: HTTPServerFactory,
    scores: list[float],
    threshold: float | None,
    expected: list[tuple[int, float]],
) -> None:
    server = http_server([
        Response(
            body=json.dumps({
                "results": [
                    {"index": index, "relevance_score": score}
                    for index, score in enumerate(scores)
                ]
            }).encode()
        )
    ])

    result = OAICompatRerankModel([]).invoke(
        "model",
        {"endpoint_url": server.url},
        "query",
        ["first", "second"][: len(scores)],
        score_threshold=threshold,
    )

    assert [(doc.index, doc.score) for doc in result.docs] == expected


@pytest.mark.parametrize(
    "response",
    [
        Response(status=503, body=b"unavailable"),
        Response(body=b"invalid json"),
        Response(body=b'{"results":[{"index":2,"relevance_score":1}]}'),
    ],
)
def test_rerank_errors_reach_the_public_interface(
    http_server: HTTPServerFactory, response: Response
) -> None:
    server = http_server([response])
    model = OAICompatRerankModel([])
    with pytest.raises(InvokeError):
        model.invoke("model", {"endpoint_url": server.url}, "query", ["document"])
    assert model.started_at == 0


@pytest.mark.parametrize(
    "results_json",
    [
        '[{"index":-1,"relevance_score":0.9}]',
        '[{"index":true,"relevance_score":0.9}]',
        '[{"index":0,"relevance_score":true}]',
        '[{"index":0,"relevance_score":"0.9"}]',
        '[{"index":0,"relevance_score":1e400}]',
        '[{"index":0,"relevance_score":-1e400}]',
        '[{"index":0,"relevance_score":1e308},{"index":1,"relevance_score":-1e308}]',
    ],
    ids=[
        "negative-index",
        "boolean-index",
        "boolean-score",
        "string-score",
        "positive-overflow",
        "negative-overflow",
        "normalization-overflow",
    ],
)
def test_rerank_rejects_invalid_indices_and_scores(
    http_server: HTTPServerFactory, results_json: str
) -> None:
    # JSON permits 1e400; decoding it must not turn a score into null on the wire.
    body = f'{{"results":{results_json}}}'.encode()
    server = http_server([Response(body=body)])
    model = OAICompatRerankModel([])

    with pytest.raises(InvokeError):
        model.invoke(
            "model", {"endpoint_url": server.url}, "query", ["first", "second"]
        )
    assert len(server.requests) == 1
    assert model.started_at == 0


@pytest.mark.parametrize("status", [200, 401])
def test_rerank_validates_credentials_over_http(
    http_server: HTTPServerFactory, status: int
) -> None:
    server = http_server([
        Response(status=status, body=b'{"results":[{"index":0,"relevance_score":1}]}')
    ])
    model = OAICompatRerankModel([])
    if status == 200:
        model.validate_credentials("model", {"endpoint_url": server.url})
    else:
        with pytest.raises(CredentialsValidateFailedError):
            model.validate_credentials("model", {"endpoint_url": server.url})
    assert json.loads(server.requests[0].body)["query"]


@pytest.mark.parametrize(
    ("model_name", "endpoint_url", "error"),
    [("model", "", "server_url is required"), ("", None, "model_name is required")],
)
def test_rerank_rejects_missing_configuration_before_requesting(
    http_server: HTTPServerFactory,
    model_name: str,
    endpoint_url: str | None,
    error: str,
) -> None:
    server = http_server([])
    credentials = {"endpoint_url": server.url if endpoint_url is None else endpoint_url}
    with pytest.raises(CredentialsValidateFailedError, match=error):
        OAICompatRerankModel([]).validate_credentials(model_name, credentials)
    assert server.requests == []
