import unittest

from dify_plugin.entities.model import AIModelEntity, ModelPropertyKey, ModelType
from dify_plugin.entities.model.llm import LLMMode, LLMResult
from dify_plugin.interfaces.model.large_language_model import LargeLanguageModel


class MockLLM(LargeLanguageModel):
    """
    Concrete Mock class for testing non-abstract methods of LargeLanguageModel.
    """

    def _invoke(
        self,
        model: str,
        credentials: dict,
        prompt_messages: list,
        model_parameters: dict,
        tools: list,
        stop: list,
        stream: bool,
        user: str,
    ) -> LLMResult:
        pass

    def get_num_tokens(self, model: str, credentials: dict, prompt_messages: list, tools: list) -> int:
        return 0

    def validate_credentials(self, model: str, credentials: dict) -> None:
        pass

    @property
    def _invoke_error_mapping(self) -> dict:
        return {}


class TestOllamaAdapter(unittest.TestCase):
    def setUp(self):
        # Create a dummy model schema to satisfy AIModel.__init__
        dummy_schema = AIModelEntity(
            model="mock_model",
            label={"en_US": "Mock Model"},
            model_type=ModelType.LLM,
            features=[],
            model_properties={ModelPropertyKey.MODE: LLMMode.CHAT.value, ModelPropertyKey.CONTEXT_SIZE: 4096},
            parameter_rules=[],
            pricing=None,
            deprecated=False,
        )
        self.llm = MockLLM(model_schemas=[dummy_schema])


    def test_with_reasoning_content(self):
        """
        The test includes reasoning_content,
        and the output should contain the <think> tag.
        """

        # Simulate simulated streaming data:
        # 1. Has reasoning_content

        chunks = [
            # Chunk 1: Thinking started
            {"reasoning_content": "Thinking started.", "content": ""},
            # Chunk 2: Still thinking
            {"reasoning_content": " Still thinking.", "content": ""},
        ]

        # Assume we are testing the logic function itself:
        is_reasoning = False
        full_output = ""

        for chunk in chunks:
            # Directly call the implementation in SDK to verify real code logic
            output, is_reasoning = self.llm._wrap_thinking_by_reasoning_content(chunk, is_reasoning)
            full_output += output

        # Verify results
        print(f"DEBUG Output: {full_output!r}")

        assert "<think>" in full_output
        assert "Thinking started. Still thinking." in full_output


    def test_with_reasoning(self):
        """
        The test includes reasoning,
        and the output should contain the <think> tag.
        """

        # Simulate simulated streaming data:
        # 1. Has reasoning

        chunks = [
            # Chunk 1: Thinking started
            {"reasoning": "Thinking started.", "content": ""},
            # Chunk 2: Still thinking
            {"reasoning": " Still thinking.", "content": ""},
        ]

        # Assume we are testing the logic function itself:
        is_reasoning = False
        full_output = ""

        for chunk in chunks:
            # Directly call the implementation in SDK to verify real code logic
            output, is_reasoning = self.llm._wrap_thinking_by_reasoning_content(chunk, is_reasoning)
            full_output += output

        # Verify results
        print(f"DEBUG Output: {full_output!r}")

        assert "<think>" in full_output
        assert "Thinking started. Still thinking." in full_output


    def test_without_reasoning(self):
        """
        The test does not include reasoning_content or reasoning.
        The output should not contain the <think> tag.
        """

        # Simulate simulated streaming data:
        # 1. Has no reasoning_content and reasoning

        chunks = [
            # Chunk 1: No Thinking
            {"content": "Content started."},
            # Chunk 2: Still No thinking
            {"content": " Still content."},
        ]

        # Assume we are testing the logic function itself:
        is_reasoning = False
        full_output = ""

        for chunk in chunks:
            # Directly call the implementation in SDK to verify real code logic
            output, is_reasoning = self.llm._wrap_thinking_by_reasoning_content(chunk, is_reasoning)
            full_output += output

        # Verify results
        print(f"DEBUG Output: {full_output!r}")

        assert "<think>" not in full_output
        assert "Content started. Still content." in full_output
