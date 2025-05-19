from abc import ABC, abstractmethod
from collections.abc import Generator, Mapping
from typing import Any, Generic, Optional, TypeVar, final

from werkzeug import Request

from dify_plugin.core.runtime import Session
from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.entities.tool import LogMetadata, ToolInvokeMessage, ToolParameter, ToolRuntime, ToolSelector
from dify_plugin.file.constants import DIFY_FILE_IDENTITY, DIFY_TOOL_SELECTOR_IDENTITY
from dify_plugin.file.entities import FileType
from dify_plugin.file.file import File

T = TypeVar("T", bound=ToolInvokeMessage | AgentInvokeMessage)


class ToolLike(ABC, Generic[T]):
    response_type: type[T]

    ############################################################
    #            For plugin implementation use only            #
    ############################################################

    def create_text_message(self, text: str) -> T:
        return self.response_type(
            type=ToolInvokeMessage.MessageType.TEXT,
            message=ToolInvokeMessage.TextMessage(text=text),
        )

    def create_json_message(self, json: Mapping | list) -> T:
        return self.response_type(
            type=ToolInvokeMessage.MessageType.JSON,
            message=ToolInvokeMessage.JsonMessage(json_object=json),
        )

    def create_image_message(self, image_url: str) -> T:
        """
        create an image message

        :param image: the url of the image
        :return: the image message
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.IMAGE,
            message=ToolInvokeMessage.TextMessage(text=image_url),
        )

    def create_link_message(self, link: str) -> T:
        """
        create a link message

        :param link: the url of the link
        :return: the link message
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.LINK,
            message=ToolInvokeMessage.TextMessage(text=link),
        )

    def create_blob_message(self, blob: bytes, meta: Optional[dict] = None) -> T:
        """
        create a blob message

        :param blob: the blob
        :return: the blob message
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.BLOB,
            message=ToolInvokeMessage.BlobMessage(blob=blob),
            meta=meta,
        )

    def create_variable_message(self, variable_name: str, variable_value: Any) -> T:
        """
        create a variable message

        :param variable_name: the name of the variable
        :param variable_value: the value of the variable
        :return: the variable message
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.VARIABLE,
            message=ToolInvokeMessage.VariableMessage(variable_name=variable_name, variable_value=variable_value),
        )

    def create_stream_variable_message(self, variable_name: str, variable_value: str) -> T:
        """
        create a variable message that will be streamed to the frontend

        NOTE: variable value should be a string, only string is streaming supported now

        :param variable_name: the name of the variable
        :param variable_value: the value of the variable
        :return: the variable message
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.VARIABLE,
            message=ToolInvokeMessage.VariableMessage(
                variable_name=variable_name,
                variable_value=variable_value,
                stream=True,
            ),
        )

    def create_log_message(
        self,
        label: str,
        data: Mapping[str, Any],
        status: ToolInvokeMessage.LogMessage.LogStatus = ToolInvokeMessage.LogMessage.LogStatus.SUCCESS,
        parent: T | None = None,
        metadata: Optional[Mapping[LogMetadata, Any]] = None,
    ) -> T:
        """
        create a log message with status "start"
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.LOG,
            message=ToolInvokeMessage.LogMessage(
                label=label,
                data=data,
                status=status,
                parent_id=parent.message.id
                if parent and isinstance(parent.message, ToolInvokeMessage.LogMessage)
                else None,
                metadata=metadata,
            ),
        )

    def create_retriever_resource_message(
        self,
        retriever_resources: list[ToolInvokeMessage.RetrieverResourceMessage.RetrieverResource],
        context: str,
    ) -> T:
        """
        create a retriever resource message
        """
        return self.response_type(
            type=ToolInvokeMessage.MessageType.RETRIEVER_RESOURCES,
            message=ToolInvokeMessage.RetrieverResourceMessage(
                retriever_resources=retriever_resources,
                context=context,
            ),
        )

    def finish_log_message(
        self,
        log: T,
        status: ToolInvokeMessage.LogMessage.LogStatus = ToolInvokeMessage.LogMessage.LogStatus.SUCCESS,
        error: Optional[str] = None,
        data: Optional[Mapping[str, Any]] = None,
        metadata: Optional[Mapping[LogMetadata, Any]] = None,
    ) -> T:
        """
        mark log as finished
        """
        assert isinstance(log.message, ToolInvokeMessage.LogMessage)
        return self.response_type(
            type=ToolInvokeMessage.MessageType.LOG,
            message=ToolInvokeMessage.LogMessage(
                id=log.message.id,
                label=log.message.label,
                data=data or log.message.data,
                status=status,
                parent_id=log.message.parent_id,
                error=error,
                metadata=metadata or log.message.metadata,
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
            elif isinstance(value, dict) and value.get("dify_model_identity") == DIFY_TOOL_SELECTOR_IDENTITY:
                tool_parameters[parameter] = ToolSelector.model_validate(value)
            elif isinstance(value, list) and all(
                isinstance(item, dict) and item.get("dify_model_identity") == DIFY_TOOL_SELECTOR_IDENTITY
                for item in value
            ):
                tool_parameters[parameter] = [ToolSelector.model_validate(item) for item in value]

        return tool_parameters


class ToolProvider:
    def validate_credentials(self, credentials: dict):
        return self._validate_credentials(credentials)

    def _validate_credentials(self, credentials: dict):
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        return self._oauth_get_authorization_url(system_credentials)

    def _oauth_get_authorization_url(self, system_credentials: Mapping[str, Any]) -> str:
        raise NotImplementedError("This method should be implemented by a subclass")

    def oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        return self._oauth_get_credentials(system_credentials, request)

    def _oauth_get_credentials(self, system_credentials: Mapping[str, Any], request: Request) -> Mapping[str, Any]:
        raise NotImplementedError("This method should be implemented by a subclass")


class Tool(ToolLike[ToolInvokeMessage]):
    runtime: ToolRuntime
    session: Session

    @final
    def __init__(
        self,
        runtime: ToolRuntime,
        session: Session,
    ):
        """
        Initialize the tool

        NOTE:
        - This method has been marked as final, DO NOT OVERRIDE IT.
        """
        self.runtime = runtime
        self.session = session
        self.response_type = ToolInvokeMessage

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
    #        Methods that can be implemented by plugin         #
    ############################################################

    @abstractmethod
    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None, None]:
        pass

    ############################################################
    #                 For executor use only                    #
    ############################################################

    def invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage, None, None]:
        # convert parameters into correct types
        tool_parameters = self._convert_parameters(tool_parameters)
        return self._invoke(tool_parameters)

    def get_runtime_parameters(self) -> list[ToolParameter]:
        return self._get_runtime_parameters()
