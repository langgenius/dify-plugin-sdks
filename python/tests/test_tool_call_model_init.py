import pytest

from dify_plugin.entities.model.message import AssistantPromptMessage


def test_tool_call_model_init_with_explicit_none_fields():
    response_tool_call = {
        "function": {
            "name": None,
            "arguments": None,
        },
        "id": None,
        "type": None,
    }

    try:
        function = AssistantPromptMessage.ToolCall.ToolCallFunction(
            name=response_tool_call.get("function", {}).get("name", ""),
            arguments=response_tool_call.get("function", {}).get("arguments", ""),
        )

        tool_call = AssistantPromptMessage.ToolCall(
            id=response_tool_call.get("id", ""),
            type=response_tool_call.get("type", ""),
            function=function,
        )

    except Exception as ex:
        pytest.fail(f"failed to initialize tool call: {ex!s}")
    else:
        assert tool_call.id == ""
        assert tool_call.type == ""
        assert tool_call.function.name == ""
        assert tool_call.function.arguments == ""

    response_function_call = {"name": None, "arguments": None, "id": None}

    try:
        function = AssistantPromptMessage.ToolCall.ToolCallFunction(
            name=response_function_call.get("name", ""),
            arguments=response_function_call.get("arguments", ""),
        )

        tool_call = AssistantPromptMessage.ToolCall(
            id=response_function_call.get("id", ""),
            type="function",
            function=function,
        )

    except Exception as ex:
        pytest.fail(f"failed to initialize tool call: {ex!s}")
    else:
        assert tool_call.id == ""
        assert tool_call.function.name == ""
        assert tool_call.function.arguments == ""
