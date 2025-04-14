from dify_plugin.entities.model.message import PromptMessage, PromptMessageRole
from dify_plugin.interfaces.agent import AgentModelConfig


def _make_agent_model_config() -> AgentModelConfig:
    return AgentModelConfig(
        provider="openai",
        model="gpt-4o-mini",
        mode="chat",)


def test_agent_model_config_ensure_history_prompt_messages_not_shared():
    prompt_message = PromptMessage(
        role=PromptMessageRole.USER,
        content="Content",
        name=None)
    cfg1 = _make_agent_model_config()
    cfg2 = _make_agent_model_config()

    assert cfg1.history_prompt_messages is not cfg2.history_prompt_messages
    # Modify cfg1's `history_prompt_messages` should not affect
    # cfg2's history_prompt_messages list.
    cfg1.history_prompt_messages.append(prompt_message)
    assert len(cfg2.history_prompt_messages) == 0
