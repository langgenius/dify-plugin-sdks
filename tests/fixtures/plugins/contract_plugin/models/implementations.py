from collections.abc import Generator, Mapping, Sequence
from typing import IO, Literal

from pydantic import JsonValue

import dify_plugin as sdk
from dify_plugin.entities.model import EmbeddingInputType
from dify_plugin.entities.model.llm import (
    LLMPollingResult,
    LLMPollingStatus,
    LLMResult,
    LLMResultChunk,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
)
from dify_plugin.entities.model.rerank import (
    MultiModalRerankResult,
    RerankDocument,
    RerankResult,
)
from dify_plugin.entities.model.text_embedding import (
    EmbeddingUsage,
    MultiModalContent,
    MultiModalEmbeddingResult,
    TextEmbeddingResult,
)
from dify_plugin.errors.model import InvokeError


class ContractCredentials:
    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        del model
        if credentials.get("api_key") != "valid":
            message = "invalid credentials"
            raise ValueError(message)

    @property
    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        return {}


class ContractLLM(ContractCredentials, sdk.LargeLanguageModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
        user: str | None = None,
    ) -> LLMResult | Generator[LLMResultChunk, None, None]:
        del credentials, model_parameters, tools, stop, user
        result = LLMResult(
            model=model,
            message=AssistantPromptMessage(content=prompt_messages[0].content),
            usage=LLMUsage.empty_usage(),
        )
        if not stream:
            return result

        def chunks() -> Generator[LLMResultChunk, None, None]:
            yield result.to_llm_result_chunk()

        return chunks()

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        del model, credentials, tools
        return sum(len(message.content) for message in prompt_messages)

    def _start_polling(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        model_parameters: dict,
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[False] = False,
        user: str | None = None,
        json_schema: dict[str, JsonValue] | None = None,
    ) -> LLMPollingResult:
        del credentials, model_parameters, tools, stop, stream, user
        return LLMPollingResult(
            status=LLMPollingStatus.RUNNING,
            plugin_state={
                "model": model,
                "content": prompt_messages[0].content,
                "json_schema": json_schema,
            },
            next_check_after_seconds=1,
        )

    def _check_polling(
        self,
        model: str,
        credentials: dict,
        plugin_state: dict[str, JsonValue],
        user: str | None = None,
    ) -> LLMPollingResult:
        del credentials, user
        return LLMPollingResult(
            status=LLMPollingStatus.SUCCEEDED,
            result=LLMResult(
                model=model,
                message=AssistantPromptMessage(content=plugin_state["content"]),
                usage=LLMUsage.empty_usage(),
            ),
        )


class ContractEmbedding(ContractCredentials, sdk.TextEmbeddingModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        texts: list[str],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> TextEmbeddingResult:
        del credentials, user, input_type
        return TextEmbeddingResult(
            model=model,
            embeddings=[[float(len(text))] for text in texts],
            usage=EmbeddingUsage(
                tokens=0,
                total_tokens=0,
                unit_price=0,
                price_unit=0,
                total_price=0,
                currency="USD",
                latency=0,
            ),
        )

    def _invoke_multimodal(
        self,
        model: str,
        credentials: dict,
        documents: list[MultiModalContent],
        user: str | None = None,
        input_type: EmbeddingInputType = EmbeddingInputType.DOCUMENT,
    ) -> MultiModalEmbeddingResult:
        result = self._invoke(
            model, credentials, [doc.content for doc in documents], user, input_type
        )
        return MultiModalEmbeddingResult(**result.model_dump())

    def get_num_tokens(
        self, model: str, credentials: dict, texts: list[str]
    ) -> list[int]:
        del model, credentials
        return [len(text) for text in texts]


class ContractRerank(ContractCredentials, sdk.RerankModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        query: str,
        docs: list[str],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> RerankResult:
        del credentials, query, score_threshold, top_n, user
        return RerankResult(
            model=model, docs=[RerankDocument(index=0, text=docs[0], score=0.9)]
        )

    def _invoke_multimodal(
        self,
        model: str,
        credentials: dict,
        query: MultiModalContent,
        docs: Sequence[MultiModalContent],
        score_threshold: float | None = None,
        top_n: int | None = None,
        user: str | None = None,
    ) -> MultiModalRerankResult:
        result = self._invoke(
            model,
            credentials,
            query.content,
            [doc.content for doc in docs],
            score_threshold,
            top_n,
            user,
        )
        return MultiModalRerankResult(**result.model_dump())


class ContractTTS(ContractCredentials, sdk.TTSModel):
    def _invoke(
        self,
        model: str,
        tenant_id: str,
        credentials: dict,
        content_text: str,
        voice: str,
        user: str | None = None,
    ) -> bytes:
        del model, tenant_id, credentials, voice, user
        return content_text.encode()


class ContractSpeechToText(ContractCredentials, sdk.Speech2TextModel):
    def _invoke(
        self,
        model: str,
        credentials: dict,
        file: IO[bytes],
        user: str | None = None,
    ) -> str:
        del model, credentials, user
        return file.read().decode()


class ContractModeration(ContractCredentials, sdk.ModerationModel):
    def _invoke(
        self, model: str, credentials: dict, text: str, user: str | None = None
    ) -> bool:
        del model, credentials, user
        return text == "blocked"
