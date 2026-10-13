from collections.abc import Generator
from threading import Barrier

from dify_plugin.entities import I18nObject
from dify_plugin.entities.tool import ToolInvokeMessage, ToolParameter
from dify_plugin.interfaces.tool import Tool

peers = Barrier(2)


class EchoTool(Tool):
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        if tool_parameters.get("wait_for_peer"):
            peers.wait(timeout=2)
        message = tool_parameters["message"]
        yield self.create_text_message(message)
        yield self.create_json_message({"echo": message})

    def _get_runtime_parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="message",
                type=ToolParameter.ToolParameterType.STRING,
                form=ToolParameter.ToolParameterForm.LLM,
                label=I18nObject(en_us="Message"),
                human_description=I18nObject(en_us="Message to return."),
                llm_description="Message to return.",
                required=True,
            ),
            ToolParameter(
                name="wait_for_peer",
                type=ToolParameter.ToolParameterType.BOOLEAN,
                form=ToolParameter.ToolParameterForm.LLM,
                label=I18nObject(en_us="Wait for another invocation"),
                human_description=I18nObject(en_us="Synchronize test invocations."),
                llm_description="Synchronize test invocations.",
                required=False,
            ),
        ]
