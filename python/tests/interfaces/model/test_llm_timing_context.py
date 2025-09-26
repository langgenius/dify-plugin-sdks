import time
from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from dify_plugin.entities.model import ModelType
from dify_plugin.entities.model.llm import LLMResult, LLMResultChunk, LLMResultChunkDelta, LLMUsage
from dify_plugin.entities.model.message import AssistantPromptMessage, PromptMessage, PromptMessageTool
from dify_plugin.errors.model import InvokeError
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel


class MockLLM(LargeLanguageModel):
    model_type = ModelType.LLM

    def validate_credentials(self, model: str, credentials: Mapping) -> None:
        """
        Validate model credentials
        """
        pass

    def _invoke_error_mapping(self) -> dict[type[InvokeError], list[type[Exception]]]:
        """
        Map model invoke error to unified error
        """
        return {}

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
        """
        Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :return: full response or stream response chunk generator result
        """
        time.sleep(1)
        yield LLMResultChunk(
            model="test",
            prompt_messages=[],
            delta=LLMResultChunkDelta(
                index=0,
                message=AssistantPromptMessage(content="test"),
                usage=LLMUsage(
                    prompt_tokens=100,
                    prompt_unit_price=Decimal(100),
                    prompt_price_unit=Decimal(100),
                    prompt_price=Decimal(100),
                    completion_tokens=100,
                    completion_unit_price=Decimal(100),
                    completion_price_unit=Decimal(100),
                    completion_price=Decimal(100),
                    total_tokens=100,
                    total_price=Decimal(100),
                    currency="test",
                    latency=time.perf_counter() - self.started_at,
                ),
            ),
        )

    def get_num_tokens(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list[PromptMessage],
        tools: list[PromptMessageTool] | None = None,
    ) -> int:
        """
        Get number of tokens

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param tools: tools
        :return: number of tokens
        """
        return 0


def test_llm_timing_context():
    """
    Check if timing context is correct in single-threaded environment
    """

    model = MockLLM(model_schemas=[])
    for result in model.invoke(
        model="test",
        credentials={"test": "test"},
        prompt_messages=[],
        model_parameters={"test": "test"},
    ):
        assert result.delta.usage is not None
        assert result.delta.usage.latency > 0
        assert result.delta.usage.latency < 1.5


def test_multithreaded_llm_timing_context():
    """
    Check if timing context is correct in multi-threaded environment

    NOTE: Singleton model is not supported.
    """

    def task(_):
        model = MockLLM(model_schemas=[])
        for result in model.invoke(
            model="test",
            credentials={"test": "test"},
            prompt_messages=[],
            model_parameters={"test": "test"},
        ):
            assert result.delta.usage is not None
            assert result.delta.usage.latency > 0
            assert result.delta.usage.latency < 1.5

    with ThreadPoolExecutor(max_workers=10) as executor:
        list(executor.map(task, range(10)))
