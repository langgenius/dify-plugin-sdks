from collections.abc import Generator
from copy import deepcopy

import pytest

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.invocations.app.chat import ChatAppInvocation
from dify_plugin.invocations.app.completion import CompletionAppInvocation
from dify_plugin.invocations.app.fetch_app import FetchAppInvocation
from dify_plugin.invocations.app.workflow import WorkflowAppInvocation
from tests.invocations.conftest import RecordInvocation


@pytest.mark.parametrize(
    ("invocation_type", "extra", "default_mode"),
    [
        (
            ChatAppInvocation,
            {"query": "你好", "conversation_id": "conversation-1"},
            "streaming",
        ),
        (CompletionAppInvocation, {}, "blocking"),
        (WorkflowAppInvocation, {}, "blocking"),
    ],
)
@pytest.mark.parametrize("response_mode", [None, "streaming", "blocking"])
def test_app_request_and_response_modes(
    record_invocation: RecordInvocation,
    invocation_type: type[
        ChatAppInvocation | CompletionAppInvocation | WorkflowAppInvocation
    ],
    extra: dict,
    default_mode: str,
    response_mode: str | None,
) -> None:
    invocation = invocation_type()
    responses = [{"event": "message", "answer": "你好"}, {"event": "message_end"}]
    recorded = record_invocation(invocation, responses)
    arguments = {
        "app_id": "app-1",
        "inputs": {"query": {"filters": ["文档"]}},
        "user": "user-1",
        **extra,
    }
    original = deepcopy(arguments)
    if response_mode is not None:
        arguments["response_mode"] = response_mode

    result = invocation.invoke(**arguments)
    mode = response_mode or default_mode
    if mode == "streaming":
        assert isinstance(result, Generator)
        assert not recorded.requests
        assert list(result) == responses
        assert recorded.yielded == 2
    else:
        assert result == responses[0]
        assert recorded.yielded == 1

    assert recorded.requests == [
        (InvokeType.App, dict, original | {"response_mode": mode})
    ]
    assert recorded.closed
    assert arguments["inputs"] == original["inputs"]


@pytest.mark.parametrize(
    "invocation_type",
    [ChatAppInvocation, CompletionAppInvocation, WorkflowAppInvocation],
)
@pytest.mark.parametrize("failure", [None, RuntimeError("application unavailable")])
def test_blocking_app_cannot_succeed_without_a_response(
    record_invocation: RecordInvocation,
    invocation_type: type[
        ChatAppInvocation | CompletionAppInvocation | WorkflowAppInvocation
    ],
    failure: Exception | None,
) -> None:
    invocation = invocation_type()
    recorded = record_invocation(invocation, [] if failure is None else [failure])
    arguments = {"app_id": "app-1", "inputs": {}, "response_mode": "blocking"}
    if isinstance(invocation, ChatAppInvocation):
        arguments["query"] = "hello"

    with pytest.raises(
        Exception, match=r"No response|application unavailable"
    ) as caught:
        invocation.invoke(**arguments)

    if failure is not None:
        assert caught.value is failure
    assert recorded.closed


@pytest.mark.parametrize("fail_after_first", [False, True])
def test_streaming_app_close_and_remote_error(
    record_invocation: RecordInvocation, fail_after_first: bool
) -> None:
    invocation = ChatAppInvocation()
    error = RuntimeError("application stopped")
    recorded = record_invocation(invocation, [{"answer": "first"}, error])
    response = invocation.invoke(app_id="app", query="hello", inputs={})
    assert isinstance(response, Generator)
    assert next(response) == {"answer": "first"}

    if fail_after_first:
        with pytest.raises(RuntimeError) as caught:
            next(response)
        assert caught.value is error
    else:
        response.close()
    assert recorded.closed
    assert recorded.yielded == 1


def test_fetch_app_records_the_requested_app(
    record_invocation: RecordInvocation,
) -> None:
    invocation = FetchAppInvocation()
    response = {"id": "app-2", "name": "中文应用"}
    recorded = record_invocation(invocation, [response])

    assert invocation.get("app-2") == response
    assert recorded.requests == [(InvokeType.FetchApp, dict, {"app_id": "app-2"})]
    assert recorded.closed


def test_fetch_app_rejects_an_empty_response(
    record_invocation: RecordInvocation,
) -> None:
    invocation = FetchAppInvocation()
    record_invocation(invocation, [])

    with pytest.raises(Exception, match="No response"):
        invocation.get("missing-app")
