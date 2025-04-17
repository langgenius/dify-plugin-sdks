import uuid
from abc import ABC
from collections.abc import Generator, Mapping
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Generic, Optional, TypeVar, Union

import httpx
from pydantic import BaseModel, TypeAdapter
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
        from dify_plugin.invocations.model.moderation import ModerationInvocation
        from dify_plugin.invocations.model.rerank import RerankInvocation
        from dify_plugin.invocations.model.speech2text import Speech2TextInvocation
        from dify_plugin.invocations.model.text_embedding import TextEmbeddingInvocation
        from dify_plugin.invocations.model.tts import TTSInvocation

        self.llm = LLMInvocation(session)
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


class Session:
    def __init__(
        self,
        session_id: str,
        executor: ThreadPoolExecutor,
        reader: RequestReader,
        writer: ResponseWriter,
        install_method: Optional[InstallMethod] = None,
        dify_plugin_daemon_url: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        app_id: Optional[str] = None,
        endpoint_id: Optional[str] = None,
    ) -> None:
        # current session id
        self.session_id: str = session_id

        # thread pool executor
        self._executor: ThreadPoolExecutor = executor

        # reader and writer
        self.reader: RequestReader = reader
        self.writer: ResponseWriter = writer

        # conversation id
        self.conversation_id: Optional[str] = conversation_id

        # message id
        self.message_id: Optional[str] = message_id

        # app id
        self.app_id: Optional[str] = app_id

        # endpoint id
        self.endpoint_id: Optional[str] = endpoint_id

        # install method
        self.install_method: Optional[InstallMethod] = install_method

        # dify plugin daemon url
        self.dify_plugin_daemon_url: Optional[str] = dify_plugin_daemon_url

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
    data: Optional[dict]


T = TypeVar("T", bound=Union[BaseModel, dict, str])


class BackwardsInvocation(Generic[T], ABC):
    def __init__(
        self,
        session: Optional[Session] = None,
    ) -> None:
        self.session = session

    def _generate_backwards_request_id(self):
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

        for chunk in generator:
            """
            accept response from input stream and wait for at most 60 seconds
            """
            if chunk is None:
                empty_response_count += 1
                # if no response for 250 seconds, break
                if empty_response_count >= 250:
                    raise Exception("invocation exited without response")
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
                    300,
                    300,
                    300,
                    300,
                ),  # 300 seconds for connection, read, write, and pool
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
