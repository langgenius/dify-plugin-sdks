from typing import Any

import pytest

from .stdio import StdioPlugin

pytestmark = pytest.mark.integration


def _invoke(session_id: str, message: str) -> dict[str, Any]:
    return {
        "session_id": session_id,
        "event": "request",
        "data": {
            "type": "tool",
            "action": "invoke_tool",
            "user_id": "test-user",
            "provider": "contract",
            "tool": "echo",
            "credentials": {"api_key": "valid"},
            "tool_parameters": {"message": message},
        },
    }


def _assert_echo(events: list[dict[str, Any]], message: str) -> None:
    assert [event["type"] for event in events] == ["stream", "stream", "end"]
    assert events[0]["data"]["type"] == "text"
    assert events[0]["data"]["message"] == {"text": message}
    assert events[1]["data"]["type"] == "json"
    assert events[1]["data"]["message"] == {"json_object": {"echo": message}}
    assert events[2]["data"] == {}


@pytest.mark.parametrize(
    "message", ["Hello, 世界 🌍", "消息" * 20_000], ids=["unicode", "large-message"]
)
def test_installed_wheel_registers_and_invokes_over_stdio(
    stdio_plugin: StdioPlugin, message: str
) -> None:
    assert "provider/contract.yaml" in stdio_plugin.manifest["plugins"]["tools"]

    stdio_plugin.send(_invoke("echo", message))

    _assert_echo(stdio_plugin.receive_sessions("echo")["echo"], message)


def test_stdio_keeps_concurrent_sessions_separate(stdio_plugin: StdioPlugin) -> None:
    requests = [_invoke("first", "one"), _invoke("second", "two")]
    for request in requests:
        request["data"]["tool_parameters"]["wait_for_peer"] = True
    stdio_plugin.send(*requests)

    responses = stdio_plugin.receive_sessions("first", "second")

    _assert_echo(responses["first"], "one")
    _assert_echo(responses["second"], "two")


def test_stdio_reports_call_error_and_accepts_next_request(
    stdio_plugin: StdioPlugin,
) -> None:
    request = _invoke("missing-tool", "unused")
    request["data"]["tool"] = "missing"
    stdio_plugin.send(request)

    events = stdio_plugin.receive_sessions("missing-tool")["missing-tool"]

    assert [event["type"] for event in events] == ["error", "end"]
    assert events[0]["data"]["error_type"] == "ValueError"
    assert "Tool `missing` not found" in events[0]["data"]["message"]
    stdio_plugin.send(_invoke("recovered", "ok"))
    _assert_echo(stdio_plugin.receive_sessions("recovered")["recovered"], "ok")


def test_stdio_recovers_from_malformed_json(stdio_plugin: StdioPlugin) -> None:
    stdio_plugin.send_bytes(b"{invalid json}\n")

    error = stdio_plugin.read_message()

    assert error["event"] == "error"
    assert error["data"]["error"]
    stdio_plugin.send(_invoke("recovered", "ok"))
    _assert_echo(stdio_plugin.receive_sessions("recovered")["recovered"], "ok")


def test_stdio_process_exits_on_termination(stdio_plugin: StdioPlugin) -> None:
    assert stdio_plugin.process.poll() is None

    stdio_plugin.close()

    assert stdio_plugin.process.poll() is not None
