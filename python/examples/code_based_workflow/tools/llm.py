from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.model.llm import LLMModelConfig
from dify_plugin.entities.model.message import SystemPromptMessage, UserPromptMessage
from dify_plugin.entities.tool import ToolInvokeMessage


class LLMTool(Tool):
    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        return [
            ParameterOption(
                value="hello world",
                label=I18nObject(en_US="Prompt string"),
            )
        ]

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        response = self.session.model.llm.invoke(
            model_config=LLMModelConfig(
                provider="openai",
                model="gpt-4o-mini",
                mode="chat",
                completion_params={},
            ),
            prompt_messages=[
                SystemPromptMessage(content="you are a helpful assistant"),
                UserPromptMessage(content=tool_parameters.get("query")),
            ],
            stream=True,
        )

        for chunk in response:
            if chunk.delta.message:
                assert isinstance(chunk.delta.message.content, str)
                yield self.create_text_message(text=chunk.delta.message.content)
