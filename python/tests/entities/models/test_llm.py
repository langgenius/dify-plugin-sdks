from dify_plugin.entities.model.llm import (
    LLMResult,
    LLMResultChunk,
    LLMResultChunkDelta,
    LLMUsage,
)
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageRole,
)


class TestLLMResultChunk:
    def test_init(self):
        model = "gpt-4o"
        delta = LLMResultChunkDelta(
            index=0,
            message=AssistantPromptMessage(content="Hello, World!", role=PromptMessageRole.ASSISTANT),
        )
        prompt_message = PromptMessage(
            role=PromptMessageRole.USER,
            content="Hello",
        )
        LLMResultChunk(model=model, delta=delta)

        LLMResultChunk(model=model, delta=delta, system_fingerprint="123")

        LLMResultChunk(model=model, prompt_messages=[], delta=delta, system_fingerprint="123")

        LLMResultChunk(model=model, prompt_messages=[prompt_message], delta=delta, system_fingerprint="123")


class TestLLMResult:
    def test_init(self):
        model = "gpt-4o"
        assistant_message = AssistantPromptMessage(content="Hello, World!", role=PromptMessageRole.ASSISTANT)
        usage = LLMUsage.empty_usage()
        prompt_message = PromptMessage(
            role=PromptMessageRole.USER,
            content="Hello",
        )

        LLMResult(model=model, message=assistant_message, usage=usage)

        LLMResult(model=model, prompt_messages=[], message=assistant_message, usage=usage, system_fingerprint="123")

        LLMResult(
            model=model,
            prompt_messages=[prompt_message],
            message=assistant_message,
            usage=usage,
            system_fingerprint="123",
        )
