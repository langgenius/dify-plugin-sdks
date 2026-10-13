from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from dify_plugin.core.entities.plugin.request import (
    ModelInvokeLLMRequest,
    ToolInvokeRequest,
)
from dify_plugin.core.runtime import Session
from dify_plugin.core.server.router import Router
from dify_plugin.entities.model.message import UserPromptMessage
from tests.servers.helpers import MemoryRequestReader, RecordingResponseWriter


@pytest.fixture
def session() -> Iterator[Session]:
    reader = MemoryRequestReader()
    with ThreadPoolExecutor(max_workers=1) as executor:
        yield Session("session-1", executor, reader, RecordingResponseWriter())
    reader.close()


def llm_request(**overrides: object) -> dict:
    return {
        "type": "model",
        "action": "invoke_llm",
        "user_id": "user-1",
        "provider": "provider",
        "model_type": "llm",
        "model": "model-1",
        "credentials": {"api_key": "test-key"},
        "model_parameters": {},
        "prompt_messages": [{"role": "user", "content": "你好"}],
        "stop": None,
        "tools": None,
        **overrides,
    }


@pytest.mark.parametrize("registration", ["function", "bound", "instance"])
def test_route_validates_real_request_before_calling_handler(
    session: Session, registration: str
) -> None:
    router = Router(session.reader, session.writer)
    calls: list[tuple[Session, ModelInvokeLLMRequest]] = []

    def handle(current: Session, data: ModelInvokeLLMRequest) -> str:
        calls.append((current, data))
        return "result"

    class Handler:
        def invoke(self, current: Session, data: ModelInvokeLLMRequest) -> str:
            return handle(current, data)

    instance = Handler()
    if registration == "function":
        router.register_route(handle, lambda data: data.get("action") == "invoke_llm")
    elif registration == "bound":
        router.register_route(
            instance.invoke, lambda data: data.get("action") == "invoke_llm"
        )
    else:
        router.register_route(
            Handler.invoke, lambda data: data.get("action") == "invoke_llm", instance
        )

    assert router.dispatch(session, llm_request()) == "result"
    assert len(calls) == 1
    current, request = calls[0]
    assert current is session
    assert isinstance(request, ModelInvokeLLMRequest)
    assert request.credentials == {"api_key": "test-key"}
    assert request.prompt_messages == [UserPromptMessage(content="你好")]
    assert request.stream is True


@pytest.mark.parametrize("with_writer", [False, True])
@pytest.mark.parametrize("instance_method", [False, True])
@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"prompt_messages": "invalid"}, TypeError),
        ({"model_type": "unknown"}, ValidationError),
        ({"credentials": []}, ValidationError),
    ],
)
def test_invalid_request_never_reaches_handler(
    session: Session,
    with_writer: bool,
    instance_method: bool,
    overrides: dict,
    error: type[Exception],
) -> None:
    router = Router(session.reader, session.writer if with_writer else None)
    calls: list[ModelInvokeLLMRequest] = []

    def handle(_session: Session, data: ModelInvokeLLMRequest) -> None:
        calls.append(data)

    class Handler:
        def invoke(self, current: Session, data: ModelInvokeLLMRequest) -> None:
            handle(current, data)

    if instance_method:
        router.register_route(Handler.invoke, lambda _data: True, Handler())
    else:
        router.register_route(handle, lambda _data: True)

    with pytest.raises(error):
        router.dispatch(session, llm_request(**overrides))
    assert calls == []


def test_first_matching_route_wins_and_unmatched_request_has_no_result(
    session: Session,
) -> None:
    router = Router(session.reader, session.writer)
    calls: list[str] = []

    def first(_session: Session, _data: ToolInvokeRequest) -> str:
        calls.append("first")
        return "first"

    def second(_session: Session, _data: ToolInvokeRequest) -> str:
        calls.append("second")
        return "second"

    for handler in (first, second):
        router.register_route(handler, lambda data: data.get("action") == "invoke_tool")

    assert router.dispatch(session, {"action": "unknown"}) is None
    assert calls == []
    assert (
        router.dispatch(
            session,
            {
                "action": "invoke_tool",
                "provider": "provider",
                "tool": "tool",
                "user_id": "user",
                "credentials": {},
                "tool_parameters": {},
            },
        )
        == "first"
    )
    assert calls == ["first"]
