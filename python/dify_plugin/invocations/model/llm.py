from collections.abc import Generator
from typing import Literal, cast, overload

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation
from dify_plugin.entities.model.llm import (
    LLMModelConfig,
    LLMResult,
    LLMResultChunk,
    SummaryResult,
)
from dify_plugin.entities.model.message import PromptMessage, PromptMessageTool


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

        response = self._backwards_invoke(
            InvokeType.LLM,
            LLMResultChunk,
            data,
        )
        response = cast(Generator[LLMResultChunk, None, None], response)
        return response


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
