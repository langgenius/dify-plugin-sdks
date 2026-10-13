import base64
from copy import deepcopy

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from pydantic import ValidationError

from dify_plugin.entities.agent import AgentInvokeMessage
from dify_plugin.entities.datasource import DatasourceMessage
from dify_plugin.entities.invoke_message import InvokeMessage
from dify_plugin.entities.tool import ToolInvokeMessage


@pytest.mark.parametrize(
    "message_type", [ToolInvokeMessage, AgentInvokeMessage, DatasourceMessage]
)
@pytest.mark.parametrize("chunked", [False, True])
@given(blob=st.binary(max_size=32_768))
@example(blob=b"")
@example(blob=bytes(range(256)))
def test_blob_payload_roundtrips_with_existing_decode_behavior(
    message_type: type[InvokeMessage], blob: bytes, chunked: bool
) -> None:
    message = {"blob": base64.b64encode(blob).decode()}
    if chunked:
        message.update(id="file-1", sequence=0, total_length=len(blob), end=True)
    payload = {
        "type": "blob_chunk" if chunked else "blob",
        "message": message,
        "meta": {
            "mime_type": "application/octet-stream",
            "file_name"
            if message_type is DatasourceMessage
            else "filename": "报告.bin",
        },
    }
    original = deepcopy(payload)

    first = message_type.model_validate(payload)
    restored = message_type.model_validate_json(first.model_dump_json())

    assert first == restored
    assert isinstance(
        first.message, InvokeMessage.BlobMessage | InvokeMessage.BlobChunkMessage
    )
    assert first.message.blob == blob
    assert first.model_dump(mode="json") == original
    assert payload["message"]["blob"] == blob


@pytest.mark.parametrize(
    "message_type", [ToolInvokeMessage, AgentInvokeMessage, DatasourceMessage]
)
def test_blob_decode_preserves_shared_message_metadata(
    message_type: type[InvokeMessage],
) -> None:
    shared = {"blob": "dGVzdA=="}

    message = message_type.model_validate({
        "type": "blob",
        "message": shared,
        "meta": shared,
    })

    assert message.message.blob == b"test"
    assert message.model_dump(mode="json")["meta"] == {"blob": "test"}


@pytest.mark.parametrize("value", [None, 0, False, {}, []])
def test_stream_variables_reject_non_string_values(value: object) -> None:
    with pytest.raises(ValidationError, match="must be a string"):
        InvokeMessage.VariableMessage(
            variable_name="answer", variable_value=value, stream=True
        )

    message = InvokeMessage.VariableMessage(
        variable_name="answer", variable_value=value
    )
    assert message.variable_value == value


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
