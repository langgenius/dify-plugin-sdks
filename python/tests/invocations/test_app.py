from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter


def _build_session() -> Session:
    return Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
    )


def _mock_backwards_invoke(
    invoke_type: InvokeType,
    data_type: type[dict],
    data: dict,
) -> Generator[dict, None, None]:
    _ = invoke_type
    _ = data_type
    yield data


def test_chat_app_invoke_should_pass_user_in_payload():
    session = _build_session()

    with patch.object(session.app.chat, "_backwards_invoke", side_effect=_mock_backwards_invoke):
        response = session.app.chat.invoke(
            app_id="app-id",
            query="hello",
            inputs={},
            response_mode="blocking",
            conversation_id="conversation-id",
            user="user-123",
        )

    assert response["user"] == "user-123"
    assert response["conversation_id"] == "conversation-id"


def test_completion_app_invoke_should_pass_user_in_payload():
    session = _build_session()

    with patch.object(session.app.completion, "_backwards_invoke", side_effect=_mock_backwards_invoke):
        response = session.app.completion.invoke(
            app_id="app-id",
            inputs={"foo": "bar"},
            response_mode="blocking",
            user="user-123",
        )

    assert response["user"] == "user-123"


def test_workflow_app_invoke_should_pass_user_in_payload():
    session = _build_session()

    with patch.object(session.app.workflow, "_backwards_invoke", side_effect=_mock_backwards_invoke):
        response = session.app.workflow.invoke(
            app_id="app-id",
            inputs={"foo": "bar"},
            response_mode="blocking",
            user="user-123",
        )

    assert response["user"] == "user-123"
