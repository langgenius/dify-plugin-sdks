from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any, Optional

from dify_plugin.entities.tool import ToolInvokeMessage, ToolRuntime
from dify_plugin.core.runtime import Session


class ToolProvider(ABC):
    def validate_credentials(self, credentials: dict):
        return self._validate_credentials(credentials)

    @abstractmethod
    def _validate_credentials(self, credentials: dict):
        pass


class Tool(ABC):
    runtime: ToolRuntime

    def __init__(
        self,
        runtime: ToolRuntime,
        session: Session,
    ):
        self.runtime = runtime
        self.session = session

    @classmethod
    def from_credentials(
        cls,
        credentials: dict,
    ) -> "Tool":
        return cls(
            runtime=ToolRuntime(credentials=credentials, user_id=None, session_id=None),
            session=Session.empty_session(),  # TODO could not fetch session here
        )

    def create_text_message(self, text: str) -> ToolInvokeMessage:
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.TEXT,
            message=ToolInvokeMessage.TextMessage(text=text),
        )

    def create_json_message(self, json: dict) -> ToolInvokeMessage:
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.JSON,
            message=ToolInvokeMessage.JsonMessage(json_object=json),
        )

    def create_image_message(self, image_url: str) -> ToolInvokeMessage:
        """
        create an image message

        :param image: the url of the image
        :return: the image message
        """
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.IMAGE,
            message=ToolInvokeMessage.TextMessage(text=image_url),
        )

    def create_link_message(self, link: str) -> ToolInvokeMessage:
        """
        create a link message

        :param link: the url of the link
        :return: the link message
        """
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.LINK,
            message=ToolInvokeMessage.TextMessage(text=link),
        )

    def create_blob_message(
        self, blob: bytes, meta: Optional[dict] = None
    ) -> ToolInvokeMessage:
        """
        create a blob message

        :param blob: the blob
        :return: the blob message
        """
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.BLOB,
            message=ToolInvokeMessage.BlobMessage(blob=blob),
            meta=meta,
        )

    def create_variable_message(
        self, variable_name: str, variable_value: Any
    ) -> ToolInvokeMessage:
        """
        create a variable message

        :param variable_name: the name of the variable
        :param variable_value: the value of the variable
        :return: the variable message
        """
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.VARIABLE,
            message=ToolInvokeMessage.VariableMessage(
                variable_name=variable_name, variable_value=variable_value
            ),
        )

    def stream_variable_message(
        self, variable_name: str, variable_value: str
    ) -> ToolInvokeMessage:
        """
        create a variable message that will be streamed to the frontend

        NOTE: variable value should be a string, only string is streaming supported now

        :param variable_name: the name of the variable
        :param variable_value: the value of the variable
        :return: the variable message
        """
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.VARIABLE,
            message=ToolInvokeMessage.VariableMessage(
                variable_name=variable_name,
                variable_value=variable_value,
                stream=True,
            ),
        )

    @abstractmethod
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None]:
        pass

    def invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None]:
        return self._invoke(tool_parameters)