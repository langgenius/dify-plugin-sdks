from collections.abc import Generator
from typing import Literal, cast, overload

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultChunk,
    LLMUsage,
    SummaryResult,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
    TextPromptMessageContent,
)


def merge_llm_result_chunk(result: LLMResult, chunk: LLMResultChunk) -> None:
    content = chunk.delta.message.content
    if isinstance(content, str):
        if isinstance(result.message.content, list):
            if content:
                result.message.content.append(TextPromptMessageContent(data=content))
        else:
            result.message.content = (result.message.content or "") + content
    elif isinstance(content, list) and content:
        if not isinstance(result.message.content, list):
            result.message.content = (
                [TextPromptMessageContent(data=result.message.content)]
                if result.message.content
                else []
            )
        result.message.content.extend(content)
    if len(chunk.delta.message.tool_calls) > 0:
        result.message.tool_calls = chunk.delta.message.tool_calls
    if chunk.delta.message.opaque_body is not None:
        result.message.opaque_body = chunk.delta.message.opaque_body
    if chunk.delta.usage:
        result.usage.prompt_tokens += chunk.delta.usage.prompt_tokens
        result.usage.completion_tokens += chunk.delta.usage.completion_tokens
        result.usage.total_tokens += chunk.delta.usage.total_tokens

        result.usage.completion_price = chunk.delta.usage.completion_price
        result.usage.prompt_price = chunk.delta.usage.prompt_price
        result.usage.total_price = chunk.delta.usage.total_price
        result.usage.currency = chunk.delta.usage.currency
        result.usage.latency = chunk.delta.usage.latency


class LLMInvocation(BackwardsInvocation[LLMResultChunk]):
    @overload
    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[True] = True,
    ) -> Generator[LLMResultChunk, None, None]: ...

    @overload
    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[False] = False,
    ) -> LLMResult: ...

    @overload
    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
    ) -> Generator[LLMResultChunk, None, None] | LLMResult: ...

    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
    ) -> Generator[LLMResultChunk, None, None] | LLMResult:
        """
        Invoke llm
        """
        if isinstance(model_config, dict):
            model_config = LLMModelConfig(**model_config)

        data = {
            **model_config.model_dump(),
            "prompt_messages": [message.model_dump() for message in prompt_messages],
            "tools": [tool.model_dump() for tool in tools] if tools else None,
            "stop": stop,
            "stream": stream,
        }

        if stream:
            response = self._backwards_invoke(
                InvokeType.LLM,
                LLMResultChunk,
                data,
            )
            return cast(Generator[LLMResultChunk, None, None], response)

        result = LLMResult(
            model=model_config.model,
            message=AssistantPromptMessage(content=""),
            usage=LLMUsage.empty_usage(),
        )

        for llm_result in self._backwards_invoke(
            InvokeType.LLM,
            LLMResultChunk,
            data,
        ):
            merge_llm_result_chunk(result, llm_result)

        return result


class SummaryInvocation(BackwardsInvocation[SummaryResult]):
    def invoke(
        self,
        text: str,
        instruction: str,
        min_summarize_length: int = 1024,
    ) -> str:
        """
        Invoke summary
        """

        if len(text) < min_summarize_length:
            return text

        data = {
            "text": text,
            "instruction": instruction,
        }

        for llm_result in self._backwards_invoke(
            InvokeType.SYSTEM_SUMMARY,
            SummaryResult,
            data,
        ):
            data = cast(SummaryResult, llm_result)
            return data.summary

        msg = "No response from summary"
        raise Exception(msg)
