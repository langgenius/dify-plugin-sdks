from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from dify_plugin.core.runtime import Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.entities.tool import ToolInvokeMessage, ToolProviderType


def test_session_context_tool_credentials():
    """
    Test the SessionContext tool credentials with mocked backwards invoke
    """

    def mock_backwards_invoke(invoke_type, data_type, data):
        mock_response = ToolInvokeMessage(
            type=ToolInvokeMessage.MessageType.TEXT,
            message=ToolInvokeMessage.TextMessage(text=data.get("credential_id", "no_credential_id")),
            meta={"mock": True},
        )
        yield mock_response

    session = Session(
        session_id="test",
        executor=ThreadPoolExecutor(max_workers=1),
        reader=StdioRequestReader(),
        writer=StdioResponseWriter(),
        context={
            "credentials": {
                "tool_credentials": {
                    "test": "credential_id_test",
                }
            }
        },
    )
    with patch.object(session.tool, "_backwards_invoke", side_effect=mock_backwards_invoke):
        invoker_specialized_result = list(
            session.tool.invoke(
                provider_type=ToolProviderType.BUILT_IN,
                provider="test",
                tool_name="test",
                parameters={"test": "test"},
                credential_id="special_credential_id",
            )
        )

        no_credential_id_result = list(
            session.tool.invoke(
                provider_type=ToolProviderType.BUILT_IN,
                provider="test",
                tool_name="test",
                parameters={"test": "test"},
            )
        )

        no_context_result = list(
            session.tool.invoke(
                provider_type=ToolProviderType.BUILT_IN,
                provider="no_context_tool",
                tool_name="no_context_tool",
                parameters={"test": "test"},
            )
        )

        assert len(invoker_specialized_result) == 1
        assert isinstance(invoker_specialized_result[0].message, ToolInvokeMessage.TextMessage)
        assert invoker_specialized_result[0].message.text == "special_credential_id"

        assert len(no_credential_id_result) == 1
        assert isinstance(no_credential_id_result[0].message, ToolInvokeMessage.TextMessage)
        assert no_credential_id_result[0].message.text == "credential_id_test"

        assert len(no_context_result) == 1
        assert isinstance(no_context_result[0].message, ToolInvokeMessage.TextMessage)
        assert no_context_result[0].message.text == "no_credential_id"
