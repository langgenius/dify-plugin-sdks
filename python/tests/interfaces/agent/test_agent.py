from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.agent import AgentInvokeMessage, AgentRuntime
from dify_plugin.entities.model.message import PromptMessage, PromptMessageRole
from dify_plugin.interfaces.agent import AgentModelConfig, AgentStrategy


def _make_agent_model_config() -> AgentModelConfig:
    return AgentModelConfig(
        provider="openai",
        model="gpt-4o-mini",
        mode="chat",
    )


def test_agent_model_config_ensure_history_prompt_messages_not_shared():
    prompt_message = PromptMessage(role=PromptMessageRole.USER, content="Content", name=None)
    cfg1 = _make_agent_model_config()
    cfg2 = _make_agent_model_config()

    assert cfg1.history_prompt_messages is not cfg2.history_prompt_messages
    # Modify cfg1's `history_prompt_messages` should not affect
    # cfg2's history_prompt_messages list.
    cfg1.history_prompt_messages.append(prompt_message)
    assert len(cfg2.history_prompt_messages) == 0


def test_constructor_of_agent_strategy():
    """
    Test the constructor of AgentStrategy

    NOTE:
    - This test is to ensure that the constructor of AgentStrategy is not overridden.
    - And ensure a breaking change will be detected by CI.
    """

    class AgentStrategyImpl(AgentStrategy):
        def _invoke(self, parameters: dict) -> Generator[AgentInvokeMessage, None, None]:
            yield self.create_text_message("Hello, world!")

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )
    agent_strategy = AgentStrategyImpl(runtime=AgentRuntime(user_id="test"), session=session)
    assert agent_strategy is not None
