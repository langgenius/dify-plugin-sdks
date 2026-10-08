from dify_plugin.entities.datasource import DatasourceMessage
from dify_plugin.entities.tool import ToolInvokeMessage


def test_tool_invoke_message_accepts_binary_link_type() -> None:
    message = ToolInvokeMessage.model_validate({
        "type": "binary_link",
        "message": {"text": "/files/tools/abc123.bin"},
    })

    assert message.type == ToolInvokeMessage.MessageType.BINARY_LINK
    assert isinstance(message.message, ToolInvokeMessage.TextMessage)
    assert message.message.text == "/files/tools/abc123.bin"


def test_datasource_message_accepts_binary_link_type() -> None:
    message = DatasourceMessage.model_validate({
        "type": "binary_link",
        "message": {"text": "/files/tools/abc123.bin"},
    })

    assert message.type == DatasourceMessage.MessageType.BINARY_LINK
    assert isinstance(message.message, DatasourceMessage.TextMessage)
    assert message.message.text == "/files/tools/abc123.bin"
