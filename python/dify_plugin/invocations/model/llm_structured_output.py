from collections.abc import Generator
from typing import Any, Literal, cast, overload

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResultChunkWithStructuredOutput,
    LLMResultWithStructuredOutput,
    LLMUsage,
)
from dify_plugin.entities.model.message import AssistantPromptMessage, PromptMessage, PromptMessageTool


class LLMStructuredOutputInvocation(BackwardsInvocation[LLMResultChunkWithStructuredOutput]):
    @overload
    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        structured_output_schema: dict[str, Any],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[True] = True,
    ) -> Generator[LLMResultChunkWithStructuredOutput, None, None]: ...

    @overload
    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        structured_output_schema: dict[str, Any],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: Literal[False] = False,
    ) -> LLMResultWithStructuredOutput: ...

    @overload
    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        structured_output_schema: dict[str, Any],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
    ) -> Generator[LLMResultChunkWithStructuredOutput, None, None] | LLMResultWithStructuredOutput: ...

    def invoke(
        self,
        model_config: LLMModelConfig | dict,
        prompt_messages: list[PromptMessage],
        structured_output_schema: dict[str, Any],
        tools: list[PromptMessageTool] | None = None,
        stop: list[str] | None = None,
        stream: bool = True,
    ) -> Generator[LLMResultChunkWithStructuredOutput, None, None] | LLMResultWithStructuredOutput:
        """
        Invoke llm with structured output
        """
        if isinstance(model_config, dict):
            model_config = LLMModelConfig(**model_config)

        data = {
            **model_config.model_dump(),
            "prompt_messages": [message.model_dump() for message in prompt_messages],
            "structured_output_schema": structured_output_schema,
            "tools": [tool.model_dump() for tool in tools] if tools else None,
            "stop": stop,
            "stream": stream,
        }

        if stream:
            response = self._backwards_invoke(
                InvokeType.LLMStructuredOutput,
                LLMResultChunkWithStructuredOutput,
                data,
            )
            response = cast(Generator[LLMResultChunkWithStructuredOutput, None, None], response)
            return response

        result = LLMResultWithStructuredOutput(
            model=model_config.model,
            message=AssistantPromptMessage(content=""),
            usage=LLMUsage.empty_usage(),
            structured_output=None,
        )

        assert isinstance(result.message.content, str)

        for llm_result in self._backwards_invoke(
            InvokeType.LLMStructuredOutput,
            LLMResultChunkWithStructuredOutput,
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

            # Handle structured output
            if llm_result.structured_output:
                result.structured_output = llm_result.structured_output

        return result
