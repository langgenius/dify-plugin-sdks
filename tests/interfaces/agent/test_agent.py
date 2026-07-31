from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities import I18nObject
from dify_plugin.entities.agent import AgentInvokeMessage, AgentRuntime
from dify_plugin.entities.model.message import PromptMessage, PromptMessageRole
from dify_plugin.entities.tool import (
    ToolDescription,
    ToolParameter,
    ToolParameterOption,
)
from dify_plugin.interfaces.agent import (
    AgentModelConfig,
    AgentStrategy,
    AgentToolIdentity,
    ToolEntity,
)


def _make_agent_model_config() -> AgentModelConfig:
    return AgentModelConfig(
        provider="openai",
        model="gpt-4o-mini",
        mode="chat",
    )


def _make_agent_strategy() -> AgentStrategy:
    class AgentStrategyImpl(AgentStrategy):
        def _invoke(
            self,
            parameters: dict,
        ) -> Generator[AgentInvokeMessage, None, None]:
            del parameters
            yield self.create_text_message("Hello, world!")

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    return AgentStrategyImpl(runtime=AgentRuntime(user_id="test"), session=session)


def test_agent_model_config_ensure_history_prompt_messages_not_shared() -> None:
    prompt_message = PromptMessage(
        role=PromptMessageRole.USER, content="Content", name=None
    )
    cfg1 = _make_agent_model_config()
    cfg2 = _make_agent_model_config()

    assert cfg1.history_prompt_messages is not cfg2.history_prompt_messages
    # Modify cfg1's `history_prompt_messages` should not affect
    # cfg2's history_prompt_messages list.
    cfg1.history_prompt_messages.append(prompt_message)
    assert len(cfg2.history_prompt_messages) == 0


def test_constructor_of_agent_strategy() -> None:
    """
    Test the constructor of AgentStrategy

    NOTE:
    - This test is to ensure that the constructor of AgentStrategy is not overridden.
    - And ensure a breaking change will be detected by CI.
    """

    agent_strategy = _make_agent_strategy()
    assert agent_strategy is not None


def test_agent_strategy_converts_tool_parameters_once() -> None:
    label = I18nObject(en_US="Search")
    input_schema = {"type": "string"}
    tool = ToolEntity(
        identity=AgentToolIdentity(
            author="test",
            name="search",
            label=label,
            provider="test",
        ),
        description=ToolDescription(human=label, llm="Search documents"),
        parameters=[
            ToolParameter(
                name="query",
                label=label,
                human_description=label,
                type=ToolParameter.ToolParameterType.SELECT,
                form=ToolParameter.ToolParameterForm.LLM,
                llm_description="Query",
                required=True,
                input_schema=input_schema,
                options=[
                    ToolParameterOption(value="docs", label=label),
                    ToolParameterOption(value="web", label=label),
                ],
            ),
            ToolParameter(
                name="upload",
                label=label,
                human_description=label,
                type=ToolParameter.ToolParameterType.FILE,
                form=ToolParameter.ToolParameterForm.LLM,
            ),
        ],
    )

    agent_strategy = _make_agent_strategy()
    prompt_tool = agent_strategy._convert_tool_to_prompt_message_tool(tool)
    agent_strategy.update_prompt_message_tool(tool, prompt_tool)

    query_schema = prompt_tool.parameters["properties"]["query"]
    assert query_schema["type"] == ToolParameter.ToolParameterType.STRING
    assert query_schema["enum"] == ["docs", "web"]
    assert query_schema is not tool.parameters[0].input_schema
    assert tool.parameters[0].input_schema == {"type": "string"}
    assert "upload" not in prompt_tool.parameters["properties"]
    assert prompt_tool.parameters["required"] == ["query"]
