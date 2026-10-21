from binascii import Error as HexError
from io import BytesIO

import pytest
from pytest_mock import MockerFixture

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.entities.model import EmbeddingInputType
from dify_plugin.entities.model.moderation import (
    ModerationModelConfig,
    ModerationResult,
)
from dify_plugin.entities.model.rerank import (
    MultiModalRerankModelConfig,
    MultiModalRerankResult,
    RerankModelConfig,
    RerankResult,
)
from dify_plugin.entities.model.speech2text import (
    Speech2TextModelConfig,
    Speech2TextResult,
)
from dify_plugin.entities.model.text_embedding import (
    MultiModalContent,
    MultiModalEmbeddingModelConfig,
    MultiModalEmbeddingResult,
    TextEmbeddingModelConfig,
    TextEmbeddingResult,
)
from dify_plugin.entities.model.tts import TTSModelConfig, TTSResult
from dify_plugin.invocations.model.moderation import ModerationInvocation
from dify_plugin.invocations.model.rerank import RerankInvocation
from dify_plugin.invocations.model.speech2text import Speech2TextInvocation
from dify_plugin.invocations.model.text_embedding import TextEmbeddingInvocation
from dify_plugin.invocations.model.tts import TTSInvocation
from tests.invocations.conftest import RecordInvocation


@pytest.fixture
def embedding_response() -> dict:
    return {
        "model": "resolved-model",
        "embeddings": [[0.0, -0.5], [1.25, 0.125]],
        "usage": {
            "tokens": 5,
            "total_tokens": 5,
            "unit_price": "0.1",
            "price_unit": "0.001",
            "total_price": "0.0005",
            "currency": "USD",
            "latency": 0.25,
        },
    }


@pytest.mark.parametrize("input_type", list(EmbeddingInputType))
def test_embedding_sends_texts_and_preserves_vectors_and_usage(
    record_invocation: RecordInvocation,
    embedding_response: dict,
    input_type: EmbeddingInputType,
) -> None:
    invocation = TextEmbeddingInvocation()
    recorded = record_invocation(invocation, [embedding_response])

    result = invocation.invoke(
        TextEmbeddingModelConfig(provider="provider", model="requested-model"),
        ["hello", "你好"],
        input_type=input_type,
    )

    assert result == TextEmbeddingResult(**embedding_response)
    assert recorded.requests == [
        (
            InvokeType.TextEmbedding,
            TextEmbeddingResult,
            {
                "provider": "provider",
                "model": "requested-model",
                "model_type": "text-embedding",
                "texts": ["hello", "你好"],
                "input_type": input_type.value,
            },
        )
    ]
    assert recorded.closed


@pytest.mark.parametrize("as_dict", [False, True])
def test_multimodal_embedding_serializes_documents_and_tenant(
    record_invocation: RecordInvocation, embedding_response: dict, as_dict: bool
) -> None:
    invocation = TextEmbeddingInvocation()
    recorded = record_invocation(invocation, [embedding_response])
    documents = [
        {"content": "你好", "content_type": "text"},
        {"content": "data:image/png;base64,AA==", "content_type": "image"},
    ]
    inputs = documents if as_dict else [MultiModalContent(**item) for item in documents]

    result = invocation.invoke_multimodal(
        MultiModalEmbeddingModelConfig(
            provider="provider", model="requested-model", tenant_id="tenant"
        ),
        inputs,
    )

    assert result == MultiModalEmbeddingResult(**embedding_response)
    assert recorded.requests == [
        (
            InvokeType.MultimodalEmbedding,
            MultiModalEmbeddingResult,
            {
                "provider": "provider",
                "model": "requested-model",
                "model_type": "text-embedding",
                "tenant_id": "tenant",
                "documents": documents,
                "input_type": "query",
            },
        )
    ]
    assert recorded.closed


@pytest.mark.parametrize(
    ("multimodal", "as_dict"), [(False, False), (True, False), (True, True)]
)
def test_rerank_serializes_options_and_preserves_original_indexes(
    record_invocation: RecordInvocation, multimodal: bool, as_dict: bool
) -> None:
    invocation = RerankInvocation()
    response = {
        "model": "resolved-model",
        "docs": [{"index": 1, "text": "second", "score": 0.99}],
    }
    recorded = record_invocation(invocation, [response])
    if multimodal:
        query = {"content": "query", "content_type": "text"}
        docs = [
            {"content": "first", "content_type": "text"},
            {"content": "second", "content_type": "text"},
        ]
        result = invocation.invoke_multimodal(
            MultiModalRerankModelConfig(provider="provider", model="requested-model"),
            query if as_dict else MultiModalContent(**query),
            docs if as_dict else [MultiModalContent(**item) for item in docs],
        )
        invoke_type, response_type = InvokeType.MultimodalRerank, MultiModalRerankResult
        score_threshold, top_n = None, None
    else:
        query, docs = "query", ["first", "second"]
        result = invocation.invoke(
            RerankModelConfig(
                provider="provider", model="requested-model", score_threshold=0, top_n=1
            ),
            docs,
            query,
        )
        invoke_type, response_type = InvokeType.Rerank, RerankResult
        score_threshold, top_n = 0, 1

    assert result == response_type(**response)
    assert recorded.requests == [
        (
            invoke_type,
            response_type,
            {
                "provider": "provider",
                "model": "requested-model",
                "model_type": "rerank",
                "score_threshold": score_threshold,
                "top_n": top_n,
                "docs": docs,
                "query": query,
            },
        )
    ]
    assert recorded.closed


@pytest.mark.parametrize("flagged", [False, True])
def test_moderation_preserves_boolean_result(
    record_invocation: RecordInvocation, flagged: bool
) -> None:
    invocation = ModerationInvocation()
    recorded = record_invocation(invocation, [{"result": flagged}])

    result = invocation.invoke(
        ModerationModelConfig(provider="provider", model="model"), "文本"
    )

    assert result is flagged
    assert recorded.requests == [
        (
            InvokeType.Moderation,
            ModerationResult,
            {
                "provider": "provider",
                "model": "model",
                "model_type": "moderation",
                "text": "文本",
            },
        )
    ]
    assert recorded.closed


@pytest.mark.parametrize("transcript", ["", "你好"])
def test_speech_to_text_serializes_binary_and_keeps_caller_file_open(
    record_invocation: RecordInvocation, transcript: str
) -> None:
    invocation = Speech2TextInvocation()
    recorded = record_invocation(invocation, [{"result": transcript}])
    audio = BytesIO(b"prefix\x00\xff\x80audio")
    audio.seek(6)

    result = invocation.invoke(
        Speech2TextModelConfig(provider="provider", model="model"), audio
    )

    assert result == transcript
    assert recorded.requests == [
        (
            InvokeType.Speech2Text,
            Speech2TextResult,
            {
                "provider": "provider",
                "model": "model",
                "model_type": "speech2text",
                "file": "00ff80617564696f",
            },
        )
    ]
    assert not audio.closed
    assert recorded.closed


def test_tts_decodes_binary_chunks_lazily_and_closes_on_cancel(
    record_invocation: RecordInvocation,
    mocker: MockerFixture,
) -> None:
    invocation = TTSInvocation()
    recorded = record_invocation(
        invocation,
        [{"result": "00ff80", "mime_type": "audio/mpeg"}, {"result": "6162"}],
    )
    backwards = mocker.spy(invocation, "_backwards_invoke")

    output = invocation.invoke(
        TTSModelConfig(provider="provider", model="model", voice="voice"), "你好"
    )
    assert not recorded.requests
    assert next(output) == b"\x00\xff\x80"
    try:
        output.close()
        assert recorded.closed
    finally:
        backwards.spy_return.close()

    assert recorded.requests == [
        (
            InvokeType.TTS,
            TTSResult,
            {
                "provider": "provider",
                "model": "model",
                "model_type": "tts",
                "voice": "voice",
                "content_text": "你好",
            },
        )
    ]
    assert recorded.yielded == 1


@pytest.mark.parametrize("chunks", [[], [""], ["00ff", "80", "6162"]])
def test_tts_preserves_audio_order_and_empty_stream(
    record_invocation: RecordInvocation, chunks: list[str]
) -> None:
    invocation = TTSInvocation()
    recorded = record_invocation(invocation, [{"result": chunk} for chunk in chunks])
    output = invocation.invoke(
        TTSModelConfig(provider="provider", model="model", voice="voice"), "text"
    )

    assert list(output) == [bytes.fromhex(chunk) for chunk in chunks]
    assert recorded.closed


def test_tts_rejects_corrupt_audio_and_closes_response(
    record_invocation: RecordInvocation,
    mocker: MockerFixture,
) -> None:
    invocation = TTSInvocation()
    recorded = record_invocation(invocation, [{"result": "not-hex"}])
    backwards = mocker.spy(invocation, "_backwards_invoke")

    with pytest.raises(HexError):
        list(
            invocation.invoke(
                TTSModelConfig(provider="provider", model="model", voice="voice"),
                "text",
            )
        )
    try:
        assert recorded.closed
    finally:
        backwards.spy_return.close()


@pytest.mark.parametrize(
    "operation",
    [
        "embedding",
        "multimodal_embedding",
        "rerank",
        "multimodal_rerank",
        "moderation",
        "speech2text",
        "tts",
    ],
)
@pytest.mark.parametrize("remote_error", [False, True])
def test_model_failures_reach_the_caller_and_close_response(
    record_invocation: RecordInvocation, operation: str, remote_error: bool
) -> None:
    if operation == "embedding":
        invocation = TextEmbeddingInvocation()
        arguments = (TextEmbeddingModelConfig(provider="provider", model="model"), [])
    elif operation == "multimodal_embedding":
        invocation = TextEmbeddingInvocation()
        arguments = (
            MultiModalEmbeddingModelConfig(
                provider="provider", model="model", tenant_id="tenant"
            ),
            [],
        )
    elif operation == "rerank":
        invocation = RerankInvocation()
        arguments = (
            RerankModelConfig(
                provider="provider", model="model", score_threshold=0, top_n=1
            ),
            [],
            "query",
        )
    elif operation == "multimodal_rerank":
        invocation = RerankInvocation()
        arguments = (
            MultiModalRerankModelConfig(provider="provider", model="model"),
            MultiModalContent(content="query", content_type="text"),
            [],
        )
    elif operation == "moderation":
        invocation = ModerationInvocation()
        arguments = (ModerationModelConfig(provider="provider", model="model"), "text")
    elif operation == "speech2text":
        invocation = Speech2TextInvocation()
        arguments = (
            Speech2TextModelConfig(provider="provider", model="model"),
            BytesIO(),
        )
    else:
        invocation = TTSInvocation()
        arguments = (
            TTSModelConfig(provider="provider", model="model", voice="voice"),
            "text",
        )
    error = RuntimeError("model unavailable")
    recorded = record_invocation(invocation, [error] if remote_error else [])

    def invoke() -> object:
        method = (
            invocation.invoke_multimodal
            if operation.startswith("multimodal_")
            else invocation.invoke
        )
        result = method(*arguments)
        return list(result) if operation == "tts" else result

    if remote_error:
        with pytest.raises(RuntimeError) as caught:
            invoke()
        assert caught.value is error
    elif operation == "tts":
        assert invoke() == []
    else:
        with pytest.raises(Exception, match="No response from"):
            invoke()
    assert recorded.closed
