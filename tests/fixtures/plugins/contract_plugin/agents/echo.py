from collections.abc import Generator

from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.interfaces.agent import AgentStrategy


class EchoAgent(AgentStrategy):
    def _invoke(self, parameters: dict) -> Generator[AgentInvokeMessage, None, None]:
        yield self.create_text_message(parameters["message"])
