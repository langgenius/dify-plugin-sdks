import signal
from collections.abc import Generator
from copy import deepcopy
from decimal import Decimal

import pytest
from pydantic import ValidationError

from dify_plugin.core.runtime import Session
from dify_plugin.entities import I18nObject
from dify_plugin.entities.agent import AgentInvokeMessage, AgentRuntime
from dify_plugin.entities.model import (
    AIModelEntity,
    ModelPropertyKey,
    ModelType,
    ParameterRule,
)
from dify_plugin.entities.model.llm import LLMUsage
from dify_plugin.entities.model.message import (
    AssistantPromptMessage,
    PromptMessage,
    PromptMessageTool,
    TextPromptMessageContent,
    ToolPromptMessage,
    UserPromptMessage,
)
from dify_plugin.entities.tool import ToolParameter
from dify_plugin.file.constants import DIFY_FILE_IDENTITY
from dify_plugin.interfaces.agent import (
    AgentModelConfig,
    AgentStrategy,
    AgentToolIdentity,
    ToolEntity,
)


class SchemaAgent(AgentStrategy):
    def _invoke(self, parameters: dict) -> Generator[AgentInvokeMessage]:
        for file in parameters.get("files", []):
            yield self.create_variable_message("filename", file.filename)
        for tool in self._init_prompt_tools(parameters.get("tools")):
            yield self.create_json_message(tool.model_dump())


@pytest.fixture
def agent() -> Generator[SchemaAgent]:
    original_sigint = signal.getsignal(signal.SIGINT)
    session = Session.empty_session()
    try:
        yield SchemaAgent(runtime=AgentRuntime(user_id="user"), session=session)
    finally:
        session.reader.close()
        session.writer.close()
        session._executor.shutdown(wait=True)
        signal.signal(signal.SIGINT, original_sigint)


def make_tool(name: str, parameters: list[ToolParameter] | None = None) -> ToolEntity:
    return ToolEntity(
        identity=AgentToolIdentity(
            author="sdk_tests",
            name=name,
            label=I18nObject(en_us=name),
            provider="contract",
        ),
        parameters=parameters or [],
    )


def test_agent_public_invoke_converts_files_and_builds_only_llm_parameters(
    agent: SchemaAgent,
) -> None:
    label = I18nObject(en_us="Input")
    parameters = [
        ToolParameter(
            name=name,
            type=kind,
            form=form,
            required=True,
            label=label,
            human_description=label,
            llm_description="Input value",
        )
        for name, kind, form in [
            ("count", "number", "llm"),
            ("enabled", "boolean", "llm"),
            ("settings", "object", "llm"),
            ("items", "array", "llm"),
            ("key", "secret-input", "form"),
            ("schema", "string", "schema"),
            ("file", "file", "llm"),
            ("files", "files", "llm"),
        ]
    ]
    messages = list(
        agent.invoke({
            "files": [
                {
                    "dify_model_identity": DIFY_FILE_IDENTITY,
                    "url": "https://files.invalid/a.txt",
                    "type": "document",
                    "filename": "a.txt",
                }
            ],
            "tools": [make_tool("configure", parameters)],
        })
    )

    assert all(isinstance(message, AgentInvokeMessage) for message in messages)
    assert messages[0].message.variable_value == "a.txt"
    schema = messages[1].message.json_object
    assert schema["name"] == "configure"
    assert not schema["description"]
    assert schema["parameters"] == {
        "type": "object",
        "properties": {
            "count": {"type": "number", "description": "Input value"},
            "enabled": {"type": "boolean", "description": "Input value"},
            "settings": {"type": "object", "description": "Input value"},
            "items": {"type": "array", "description": "Input value"},
        },
        "required": ["count", "enabled", "settings", "items"],
    }


def test_one_invalid_tool_is_diagnosed_without_dropping_valid_tools(
    agent: SchemaAgent,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    convert = agent._convert_tool_to_prompt_message_tool

    def convert_with_removed_tool(tool: ToolEntity) -> PromptMessageTool:
        if tool.identity.name == "removed":
            msg = "provider was removed"
            raise ValueError(msg)
        return convert(tool)

    monkeypatch.setattr(
        agent, "_convert_tool_to_prompt_message_tool", convert_with_removed_tool
    )
    messages = list(
        agent.invoke({
            "tools": [make_tool("before"), make_tool("removed"), make_tool("after")]
        })
    )
    assert [message.message.json_object["name"] for message in messages] == [
        "before",
        "after",
    ]
    assert len(caplog.records) == 1
    assert "removed" in caplog.records[0].message
    assert "conversion failed" in caplog.records[0].message
    assert isinstance(caplog.records[0].exc_info[1], ValueError)
    assert list(agent.invoke({"tools": None})) == []


def test_usage_accumulation_preserves_existing_shared_result_behavior(
    agent: SchemaAgent,
) -> None:
    first = LLMUsage.empty_usage().model_copy(
        update={
            "prompt_tokens": 10,
            "completion_tokens": 4,
            "total_tokens": 14,
            "prompt_price": Decimal("0.01"),
            "completion_price": Decimal("0.008"),
            "total_price": Decimal("0.018"),
        }
    )
    second = LLMUsage.empty_usage().model_copy(
        update={
            "prompt_tokens": 3,
            "completion_tokens": 2,
            "total_tokens": 5,
            "prompt_price": Decimal("0.003"),
            "completion_price": Decimal("0.004"),
            "total_price": Decimal("0.007"),
        }
    )
    total: dict[str, LLMUsage | None] = {"usage": None}
    agent.increase_usage(total, first)
    agent.increase_usage(total, second)
    assert total["usage"] is first
    assert total["usage"].prompt_tokens == 13
    assert total["usage"].completion_tokens == 6
    assert total["usage"].total_tokens == 19
    assert total["usage"].prompt_price == Decimal("0.013")
    assert total["usage"].completion_price == Decimal("0.012")
    assert total["usage"].total_price == Decimal("0.025")

    agent.increase_usage(total, first)
    assert total["usage"].prompt_tokens == 26
    assert total["usage"].completion_tokens == 12
    assert total["usage"].total_tokens == 38
    assert total["usage"].prompt_price == Decimal("0.026")
    assert total["usage"].completion_price == Decimal("0.024")
    assert total["usage"].total_price == Decimal("0.050")


@pytest.mark.parametrize("parameter_name", ["max_tokens", "max_completion_tokens"])
@pytest.mark.parametrize(("requested", "expected"), [(30, 30), (60, 60), (80, 60)])
def test_max_tokens_respects_context_limit_and_provider_parameter_name(
    agent: SchemaAgent,
    monkeypatch: pytest.MonkeyPatch,
    parameter_name: str,
    requested: int,
    expected: int,
) -> None:
    model = AIModelEntity(
        model="test",
        model_type=ModelType.LLM,
        model_properties={ModelPropertyKey.CONTEXT_SIZE: 100},
        parameter_rules=[ParameterRule(name=parameter_name, use_template="max_tokens")],
    )
    prompts = [UserPromptMessage(content="model input")]

    def count_tokens(messages: list[PromptMessage]) -> int:
        assert messages == prompts
        return 40

    monkeypatch.setattr(agent, "_get_num_tokens_by_gpt2", count_tokens)
    parameters = {parameter_name: requested, "temperature": 0.2}
    agent.recalc_llm_max_tokens(model, prompts, parameters)
    assert parameters == {parameter_name: expected, "temperature": 0.2}


def test_model_without_context_limit_keeps_request_and_skips_tokenization(
    agent: SchemaAgent, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = AIModelEntity(
        model="unbounded", model_type=ModelType.LLM, model_properties={}
    )

    def reject_tokenization(_messages: list[PromptMessage]) -> int:
        pytest.fail("a model without a context limit must not tokenize the prompt")

    monkeypatch.setattr(agent, "_get_num_tokens_by_gpt2", reject_tokenization)
    parameters = {"max_tokens": 100}
    agent.recalc_llm_max_tokens(model, [], parameters)
    assert parameters == {"max_tokens": 100}


@pytest.mark.parametrize("remaining", [15, 1, 0, -1])
def test_context_estimate_keeps_the_provider_call_possible(
    agent: SchemaAgent, monkeypatch: pytest.MonkeyPatch, remaining: int
) -> None:
    model = AIModelEntity(
        model="test",
        model_type=ModelType.LLM,
        model_properties={ModelPropertyKey.CONTEXT_SIZE: 100},
        parameter_rules=[ParameterRule(name="max_tokens", use_template="max_tokens")],
    )
    monkeypatch.setattr(agent, "_get_num_tokens_by_gpt2", lambda _: 100 - remaining)
    parameters = {"max_tokens": 16}

    agent.recalc_llm_max_tokens(model, [], parameters)

    assert parameters == {"max_tokens": 16}


def test_model_history_reconstructs_tool_calls_and_multimodal_content() -> None:
    # The official ReAct and FunctionCalling strategies parse this Dify payload.
    data = {
        "provider": "openai",
        "model": "gpt-4o",
        "mode": "chat",
        "history_prompt_messages": [
            {
                "role": "user",
                "content": [{"type": "text", "data": "Search documentation"}],
            },
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "search-1",
                        "type": "function",
                        "function": {"name": "search", "arguments": '{"query":"SDK"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "search-1", "content": "Result"},
        ],
    }
    original = deepcopy(data)

    first = AgentModelConfig.model_validate(data)
    second = AgentModelConfig.model_validate(data)
    user, assistant, tool = first.history_prompt_messages

    assert isinstance(user, UserPromptMessage)
    assert user.get_text_content() == "Search documentation"
    assert isinstance(assistant, AssistantPromptMessage)
    assert isinstance(tool, ToolPromptMessage)
    assert assistant.tool_calls[0].id == tool.tool_call_id == "search-1"
    assert assistant.tool_calls[0].function.arguments == '{"query":"SDK"}'
    assert first == second
    assert data == original


@pytest.mark.parametrize(
    "history",
    [
        {"role": "user", "content": "hello"},
        [{"role": "tool", "content": "missing call ID"}],
    ],
)
def test_model_history_rejects_malformed_history(history: object) -> None:
    with pytest.raises((TypeError, ValidationError)):
        AgentModelConfig.model_validate({
            "provider": "openai",
            "model": "gpt-4o",
            "mode": "chat",
            "history_prompt_messages": history,
        })


@pytest.mark.parametrize("multipart", [False, True])
def test_real_tokenizer_preserves_budget_for_each_content_form(
    agent: SchemaAgent, multipart: bool
) -> None:
    model = AIModelEntity(
        model="test",
        model_type=ModelType.LLM,
        model_properties={ModelPropertyKey.CONTEXT_SIZE: 100},
        parameter_rules=[ParameterRule(name="max_tokens", use_template="max_tokens")],
    )
    text = "hello " * 50
    content = [TextPromptMessageContent(data=text)] if multipart else text
    parameters = {"max_tokens": 80}

    agent.recalc_llm_max_tokens(model, [UserPromptMessage(content=content)], parameters)

    assert parameters["max_tokens"] == (80 if multipart else 49)


def test_gpt2_overestimate_does_not_reject_a_valid_provider_prompt(
    agent: SchemaAgent,
) -> None:
    # GPT-4o encodes this text in 48,000 tokens; GPT-2 estimates 128,000.
    text = "今天天气很好\uff0c我们一起去公园散步。" * 4000
    model = AIModelEntity(
        model="gpt-4o",
        model_type=ModelType.LLM,
        model_properties={ModelPropertyKey.CONTEXT_SIZE: 128000},
        parameter_rules=[ParameterRule(name="max_tokens", use_template="max_tokens")],
    )
    parameters = {"max_tokens": 1024}

    agent.recalc_llm_max_tokens(model, [UserPromptMessage(content=text)], parameters)

    assert parameters["max_tokens"] > 0


def test_real_tokenizer_preserves_special_token_error(
    agent: SchemaAgent,
) -> None:
    model = AIModelEntity(
        model="test",
        model_type=ModelType.LLM,
        model_properties={ModelPropertyKey.CONTEXT_SIZE: 100},
        parameter_rules=[ParameterRule(name="max_tokens", use_template="max_tokens")],
    )
    parameters = {"max_tokens": 1}

    with pytest.raises(ValueError, match="special token"):
        agent.recalc_llm_max_tokens(
            model,
            [UserPromptMessage(content="Explain <|endoftext|> as ordinary text")],
            parameters,
        )

    assert parameters == {"max_tokens": 1}
