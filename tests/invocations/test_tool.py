from copy import deepcopy

import pytest

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import Session
from dify_plugin.entities.tool import ToolInvokeMessage, ToolProviderType
from dify_plugin.invocations.tool import ToolInvocation
from tests.invocations.conftest import RecordInvocation


@pytest.mark.parametrize(
    ("credential_id", "session_credential", "expected"),
    [
        (None, None, None),
        (None, "", None),
        (None, "session-credential", "session-credential"),
        ("explicit-credential", "session-credential", "explicit-credential"),
        ("explicit-credential", None, "explicit-credential"),
        ("", "session-credential", ""),
    ],
)
@pytest.mark.parametrize("app_id", [None, "app"])
def test_tool_credential_precedence_and_app_context(
    record_invocation: RecordInvocation,
    session: Session,
    credential_id: str | None,
    session_credential: str | None,
    expected: str | None,
    app_id: str | None,
) -> None:
    session.app_id = app_id
    if session_credential is not None:
        session.context.credentials.tool_credentials["provider"] = session_credential
    session.context.credentials.tool_credentials["other-provider"] = "other-credential"
    invocation = session.tool
    response = {"type": "text", "message": {"text": "hello"}}
    recorded = record_invocation(invocation, [response])
    parameters = {"query": "你好", "filters": {"limit": 0, "include_archived": False}}
    original = deepcopy(parameters)
    context = session.context.model_dump()

    result = list(
        invocation.invoke(
            ToolProviderType.BUILT_IN,
            "provider",
            "search",
            parameters,
            credential_id=credential_id,
        )
    )

    payload = {
        "tool_type": "builtin",
        "provider": "provider",
        "tool": "search",
        "tool_parameters": original,
    }
    if app_id is not None:
        payload["app_id"] = app_id
    if expected is not None:
        payload["credential_id"] = expected
    assert recorded.requests == [(InvokeType.Tool, ToolInvokeMessage, payload)]
    assert result == [ToolInvokeMessage(**response)]
    assert parameters == original
    assert session.context.model_dump() == context
    assert recorded.closed


def test_tool_credentials_do_not_cross_sessions(
    record_invocation: RecordInvocation, session: Session
) -> None:
    session.context.credentials.tool_credentials["provider"] = "first-credential"
    second = Session("second", session._executor, session.reader, session.writer)
    first_recorded = record_invocation(session.tool, [])
    second_recorded = record_invocation(second.tool, [])

    list(session.tool.invoke_builtin_tool("provider", "search", {}))
    list(second.tool.invoke_builtin_tool("provider", "search", {}))

    assert first_recorded.requests[0][2]["credential_id"] == "first-credential"
    assert "credential_id" not in second_recorded.requests[0][2]
    assert "app_id" not in second_recorded.requests[0][2]
    assert second.context.credentials.tool_credentials == {}


@pytest.mark.parametrize(
    ("method", "provider_type"),
    [
        ("invoke_builtin_tool", "builtin"),
        ("invoke_workflow_tool", "workflow"),
        ("invoke_api_tool", "api"),
    ],
)
def test_tool_shortcuts_forward_parameters_and_cancel_stream(
    record_invocation: RecordInvocation, method: str, provider_type: str
) -> None:
    invocation = ToolInvocation()
    recorded = record_invocation(
        invocation,
        [
            {"type": "text", "message": {"text": "first"}},
            {"type": "text", "message": {"text": "second"}},
        ],
    )

    output = getattr(invocation, method)("provider", "search", {"query": "hello"})
    assert next(output).message.text == "first"
    output.close()

    assert recorded.requests == [
        (
            InvokeType.Tool,
            ToolInvokeMessage,
            {
                "tool_type": provider_type,
                "provider": "provider",
                "tool": "search",
                "tool_parameters": {"query": "hello"},
            },
        )
    ]
    assert recorded.yielded == 1
    assert recorded.closed


def test_tool_does_not_swallow_an_error_after_output(
    record_invocation: RecordInvocation,
) -> None:
    invocation = ToolInvocation()
    error = RuntimeError("tool unavailable")
    recorded = record_invocation(
        invocation,
        [
            {"type": "text", "message": {"text": "partial"}},
            error,
        ],
    )
    output = invocation.invoke_api_tool("provider", "tool", {})
    assert next(output).message.text == "partial"

    with pytest.raises(RuntimeError) as caught:
        next(output)
    assert caught.value is error
    assert recorded.closed
