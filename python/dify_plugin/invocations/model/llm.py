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
from dify_plugin.entities.model.message import AssistantPromptMessage, PromptMessage, PromptMessageTool


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
            response = cast(Generator[LLMResultChunk, None, None], response)
            return response

        result = LLMResult(
            model=model_config.model,
            message=AssistantPromptMessage(content=""),
            usage=LLMUsage.empty_usage(),
        )

        assert isinstance(result.message.content, str)

        for llm_result in self._backwards_invoke(
            InvokeType.LLM,
            LLMResultChunk,
            data,
        ):
            if isinstance(llm_result.delta.message.content, str):
                result.message.content += llm_result.delta.message.content
            if len(llm_result.delta.message.tool_calls) > 0:
                result.message.tool_calls = llm_result.delta.message.tool_calls
            if llm_result.delta.usage:
                result.usage.prompt_tokens += llm_result.delta.usage.prompt_tokens
                result.usage.completion_tokens += llm_result.delta.usage.completion_tokens
                result.usage.total_tokens += llm_result.delta.usage.total_tokens

                result.usage.completion_price = llm_result.delta.usage.completion_price
                result.usage.prompt_price = llm_result.delta.usage.prompt_price
                result.usage.total_price = llm_result.delta.usage.total_price
                result.usage.currency = llm_result.delta.usage.currency
                result.usage.latency = llm_result.delta.usage.latency

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

        raise Exception("No response from summary")
