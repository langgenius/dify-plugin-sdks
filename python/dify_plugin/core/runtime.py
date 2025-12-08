import uuid
from abc import ABC
from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Generic, TypeVar, Union

import httpx
from pydantic import BaseModel, Field, TypeAdapter
from yarl import URL

from dify_plugin.config.config import InstallMethod
from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.entities.plugin.io import (
    PluginInStream,
    PluginInStreamBase,
    PluginInStreamEvent,
)
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter

#################################################
# Session
#################################################


class ModelInvocations:
    def __init__(self, session: "Session") -> None:
        from dify_plugin.invocations.model.llm import LLMInvocation, SummaryInvocation
        from dify_plugin.invocations.model.llm_structured_output import (
            LLMStructuredOutputInvocation,
        )
        from dify_plugin.invocations.model.moderation import ModerationInvocation
        from dify_plugin.invocations.model.rerank import RerankInvocation
        from dify_plugin.invocations.model.speech2text import Speech2TextInvocation
        from dify_plugin.invocations.model.text_embedding import TextEmbeddingInvocation
        from dify_plugin.invocations.model.tts import TTSInvocation

        self.llm = LLMInvocation(session)
        self.llm_structured_output = LLMStructuredOutputInvocation(session)
        self.text_embedding = TextEmbeddingInvocation(session)
        self.rerank = RerankInvocation(session)
        self.speech2text = Speech2TextInvocation(session)
        self.tts = TTSInvocation(session)
        self.moderation = ModerationInvocation(session)
        self.summary = SummaryInvocation(session)


class AppInvocations:
    def __init__(self, session: "Session"):
        from dify_plugin.invocations.app import FetchAppInvocation
        from dify_plugin.invocations.app.chat import ChatAppInvocation
        from dify_plugin.invocations.app.completion import CompletionAppInvocation
        from dify_plugin.invocations.app.workflow import WorkflowAppInvocation

        self.chat = ChatAppInvocation(session)
        self.completion = CompletionAppInvocation(session)
        self.workflow = WorkflowAppInvocation(session)
        self.fetch_app_invocation = FetchAppInvocation(session)

    def fetch_app(self, app_id: str) -> Mapping:
        return self.fetch_app_invocation.get(app_id)


class WorkflowNodeInvocations:
    def __init__(self, session: "Session"):
        from dify_plugin.invocations.workflow_node.parameter_extractor import (
            ParameterExtractorNodeInvocation,
        )
        from dify_plugin.invocations.workflow_node.question_classifier import (
            QuestionClassifierNodeInvocation,
        )

        self.question_classifier = QuestionClassifierNodeInvocation(session)
        self.parameter_extractor = ParameterExtractorNodeInvocation(session)


class InvokeCredentials(BaseModel):
    """
    Invoke credentials

    Session Level Credentials, used to store session level credentials, such as tool call credentials.
    Especially for the backwards invoke, when invoker is not specified, we need to use the credential id from the
    session context.
    """

    tool_credentials: dict[str, str] = Field(
        default_factory=dict,
        description="This is a map of tool provider to credential id. It is used to store the credential id for the "
        "tool provider.",
    )

    def get_credential_id(self, provider: str) -> str | None:
        return self.tool_credentials.get(provider)


class SessionContext(BaseModel):
    """
    Session Context

    Session Context is used to store the session level context, such as credentials.
    In the future, we will refactor message_id and conversation_id and the others to be part of the session context.
    """

    credentials: InvokeCredentials = Field(default_factory=InvokeCredentials)


class Session:
    def __init__(
        self,
        session_id: str,
        executor: ThreadPoolExecutor,
        reader: RequestReader,
        writer: ResponseWriter,
        install_method: InstallMethod | None = None,
        dify_plugin_daemon_url: str | None = None,
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: SessionContext | dict | None = None,
        max_invocation_timeout: int = 250,
    ) -> None:
        # current session id
        self.session_id: str = session_id

        # thread pool executor
        self._executor: ThreadPoolExecutor = executor

        # reader and writer
        self.reader: RequestReader = reader
        self.writer: ResponseWriter = writer

        # conversation id
        self.conversation_id: str | None = conversation_id

        # message id
        self.message_id: str | None = message_id

        # app id
        self.app_id: str | None = app_id

        # endpoint id
        self.endpoint_id: str | None = endpoint_id

        # install method
        self.install_method: InstallMethod | None = install_method

        # context
        self.context: SessionContext = (
            SessionContext.model_validate(context) if isinstance(context, dict) else context or SessionContext()
        )

        # dify plugin daemon url
        self.dify_plugin_daemon_url: str | None = dify_plugin_daemon_url

        # max invocation timeout (seconds)
        self.max_invocation_timeout: int = max_invocation_timeout

        # register invocations
        self._register_invocations()

    def _register_invocations(self) -> None:
        from dify_plugin.invocations.file import File
        from dify_plugin.invocations.storage import StorageInvocation
        from dify_plugin.invocations.tool import ToolInvocation

        self.model = ModelInvocations(self)
        self.tool = ToolInvocation(self)
        self.app = AppInvocations(self)
        self.workflow_node = WorkflowNodeInvocations(self)
        self.storage = StorageInvocation(self)
        self.file = File(self)

    @classmethod
    def empty_session(cls) -> "Session":
        return cls(
            session_id="",
            executor=ThreadPoolExecutor(),
            reader=TCPReaderWriter(host="", port=0, key=""),
            writer=TCPReaderWriter(host="", port=0, key=""),
            install_method=None,
            dify_plugin_daemon_url=None,
            context=None,
        )


#################################################
# Backwards Invocation Request
#################################################


class BackwardsInvocationResponseEvent(BaseModel):
    class Event(Enum):
        response = "response"
        Error = "error"
        End = "end"

    backwards_request_id: str
    event: Event
    message: str
    data: dict | None


T = TypeVar("T", bound=Union[BaseModel, dict, str])


class BackwardsInvocation(Generic[T], ABC):
    def __init__(
        self,
        session: Session | None = None,
    ) -> None:
        """Initializes a backwards invocation handler.

        Backwards invocations allow the plugin to call back to the Dify platform
        to use its features like models, tools, or storage.

        :param session: The session object containing context for the invocation.
        """
        self.session = session

    def _generate_backwards_request_id(self):
        """
        generate a unique request id for backwards invocation

        :return: request id
        """
        return uuid.uuid4().hex

    def _backwards_invoke(
        self,
        type: InvokeType,  # noqa: A002
        data_type: type[T],
        data: dict,
    ) -> Generator[T, None, None]:
        """
        backwards invoke dify depends on current runtime type
        """
        backwards_request_id = self._generate_backwards_request_id()

        if not self.session:
            raise Exception("current tool runtime does not support backwards invoke")
        if self.session.install_method in [InstallMethod.Local, InstallMethod.Remote]:
            return self._full_duplex_backwards_invoke(backwards_request_id, type, data_type, data)
        return self._http_backwards_invoke(backwards_request_id, type, data_type, data)

    def _line_converter_wrapper(
        self,
        generator: Generator[PluginInStreamBase | None, None, None],
        data_type: type[T],
    ) -> Generator[T, None, None]:
        """
        convert string into type T
        """
        empty_response_count = 0
        # get max timeout count, each wait is 1 second, so timeout count equals timeout seconds
        max_timeout_count = self.session.max_invocation_timeout if self.session else 250

        for chunk in generator:
            """
            accept response from input stream and wait,
            exit when consecutive empty responses exceed configured timeout value
            """
            if chunk is None:
                empty_response_count += 1
                # if consecutive empty responses exceed max timeout count, break
                if empty_response_count >= max_timeout_count:
                    raise Exception(f"invocation exited without response after {max_timeout_count} seconds")
                continue

            event = BackwardsInvocationResponseEvent(**chunk.data)
            if event.event == BackwardsInvocationResponseEvent.Event.End:
                break

            if event.event == BackwardsInvocationResponseEvent.Event.Error:
                raise Exception(event.message)

            if event.data is None:
                break

            empty_response_count = 0
            try:
                yield data_type(**event.data)
            except Exception as e:
                raise Exception(f"Failed to parse response: {e!s}") from e

    def _http_backwards_invoke(
        self,
        backwards_request_id: str,
        type: InvokeType,  # noqa: A002
        data_type: type[T],
        data: dict,
    ) -> Generator[T, None, None]:
        """
        http backwards invoke
        """
        if not self.session or not self.session.dify_plugin_daemon_url:
            raise Exception("current tool runtime does not support backwards invoke")

        url = URL(self.session.dify_plugin_daemon_url) / "backwards-invocation" / "transaction"
        headers = {
            "Dify-Plugin-Session-ID": self.session.session_id,
        }

        payload = self.session.writer.session_message_text(
            session_id=self.session.session_id,
            data=self.session.writer.stream_invoke_object(
                data={
                    "type": type.value,
                    "backwards_request_id": backwards_request_id,
                    "request": data,
                }
            ),
        )

        with (
            httpx.Client() as client,
            client.stream(
                method="POST",
                url=str(url),
                headers=headers,
                content=payload,
                timeout=(
                    self.session.max_invocation_timeout,  # connection timeout
                    self.session.max_invocation_timeout,  # read timeout
                    self.session.max_invocation_timeout,  # write timeout
                    self.session.max_invocation_timeout,  # pool timeout
                ),
            ) as response,
        ):

            def generator():
                for line in response.iter_lines():
                    if not line:
                        continue

                    data = TypeAdapter(dict[str, Any]).validate_json(line)
                    yield PluginInStreamBase(
                        session_id=data["session_id"],
                        event=PluginInStreamEvent.value_of(data["event"]),
                        data=data["data"],
                    )

            yield from self._line_converter_wrapper(generator(), data_type)

    def _full_duplex_backwards_invoke(
        self,
        backwards_request_id: str,
        type: InvokeType,  # noqa: A002
        data_type: type[T],
        data: dict,
    ) -> Generator[T, None, None]:
        if not self.session:
            raise Exception("current tool runtime does not support backwards invoke")

        self.session.writer.session_message(
            session_id=self.session.session_id,
            data=self.session.writer.stream_invoke_object(
                data={
                    "type": type.value,
                    "backwards_request_id": backwards_request_id,
                    "request": data,
                }
            ),
        )

        def filter(data: PluginInStream) -> bool:  # noqa: A001
            return (
                data.event == PluginInStreamEvent.BackwardInvocationResponse
                and data.data.get("backwards_request_id") == backwards_request_id
            )

        with self.session.reader.read(filter) as reader:
            yield from self._line_converter_wrapper(reader.read(timeout_for_round=1), data_type)
