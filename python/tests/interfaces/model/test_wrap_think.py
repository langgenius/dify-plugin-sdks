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


class TestWrapThinking(unittest.TestCase):
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

    def test_wrap_thinking_logic_closure(self):
        """
        Test that when reasoning_content ends, even if content is empty (e.g. followed immediately by tool_calls),
        the <think> tag should be closed correctly.
        """

        # Simulate simulated streaming data:
        # 1. Has reasoning_content
        # 2. reasoning_content ends, followed immediately by tool_calls (content is None)

        chunks = [
            # Chunk 1: Thinking started
            {"reasoning_content": "Thinking started.", "content": ""},
            # Chunk 2: Still thinking
            {"reasoning_content": " Still thinking.", "content": ""},
            # Chunk 3: Thinking ended, transitioned to Tool Call (reasoning_content=None, content=None/Empty)
            # This is a critical point, old logic would fail here because content is empty
            {"reasoning_content": None, "content": "", "tool_calls": [{"id": "call_1", "function": {}}]},
            # Chunk 4: Subsequent tool parameter stream
            {"reasoning_content": None, "content": "", "tool_calls": [{"function": {"arguments": "{"}}]},
        ]

        # Use the "new logic" from PR for testing.
        # We can directly call self.llm._wrap_thinking_by_reasoning_content.

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
        assert "</think>" in full_output, "Should verify <think> tag is closed properly"

        # Verify the position of the closing tag: should be after the thinking content
        expected_part = "Thinking started. Still thinking.\n</think>"
        assert expected_part in full_output

    def test_standard_reasoning_flow(self):
        """Test standard reasoning -> text flow"""
        chunks = [
            {"reasoning_content": "Thinking.", "content": ""},
            {"reasoning_content": None, "content": "Hello world."},
        ]

        is_reasoning = False
        full_output = ""
        for chunk in chunks:
            # Directly call the implementation in SDK
            output, is_reasoning = self.llm._wrap_thinking_by_reasoning_content(chunk, is_reasoning)
            full_output += output

        assert full_output == "<think>\nThinking.\n</think>Hello world."
