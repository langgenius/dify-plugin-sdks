from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any, Optional

from dify_plugin.core.runtime import Session
from dify_plugin.entities.tool import ToolInvokeMessage, ToolParameter, ToolRuntime
from dify_plugin.file.constants import DIFY_FILE_IDENTITY
from dify_plugin.file.entities import FileType
from dify_plugin.file.file import File


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

    ############################################################
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None]:
        pass

    @classmethod
    def from_credentials(
        cls,
        credentials: dict,
        user_id: Optional[str] = None,
    ):
        return cls(
            runtime=ToolRuntime(credentials=credentials, user_id=user_id, session_id=None),
            session=Session.empty_session(),  # TODO could not fetch session here
        )

    ############################################################
    #            For plugin implementation use only            #
    ############################################################

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

    def create_blob_message(self, blob: bytes, meta: Optional[dict] = None) -> ToolInvokeMessage:
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

    def create_variable_message(self, variable_name: str, variable_value: Any) -> ToolInvokeMessage:
        """
        create a variable message

        :param variable_name: the name of the variable
        :param variable_value: the value of the variable
        :return: the variable message
        """
        return ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.VARIABLE,
            message=ToolInvokeMessage.VariableMessage(variable_name=variable_name, variable_value=variable_value),
        )

    def create_stream_variable_message(self, variable_name: str, variable_value: str) -> ToolInvokeMessage:
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

    def _get_runtime_parameters(self) -> list[ToolParameter]:
        """
        get the runtime parameters of the tool

        :return: the runtime parameters
        """
        return []

    @classmethod
    def _is_get_runtime_parameters_overridden(cls) -> bool:
        """
        check if the _get_runtime_parameters method is overridden by subclass

        :return: True if overridden, False otherwise
        """
        return "_get_runtime_parameters" in cls.__dict__

    @classmethod
    def _convert_parameters(cls, tool_parameters: dict) -> dict:
        """
        convert parameters into correct types
        """
        for parameter, value in tool_parameters.items():
            if isinstance(value, dict) and value.get("dify_model_identity") == DIFY_FILE_IDENTITY:
                tool_parameters[parameter] = File(
                    url=value["url"],
                    mime_type=value.get("mime_type"),
                    type=FileType(value.get("type")),
                    filename=value.get("filename"),
                    extension=value.get("extension"),
                    size=value.get("size"),
                )
            elif isinstance(value, list) and all(
                isinstance(item, dict) and item.get("dify_model_identity") == DIFY_FILE_IDENTITY for item in value
            ):
                tool_parameters[parameter] = [
                    File(
                        url=item["url"],
                        mime_type=item.get("mime_type"),
                        type=FileType(item.get("type")),
                        filename=item.get("filename"),
                        extension=item.get("extension"),
                        size=item.get("size"),
                    )
                    for item in value
                ]

        return tool_parameters

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None]:
        # convert parameters into correct types
        tool_parameters = self._convert_parameters(tool_parameters)
        return self._invoke(tool_parameters)

    def get_runtime_parameters(self) -> list[ToolParameter]:
        return self._get_runtime_parameters()
