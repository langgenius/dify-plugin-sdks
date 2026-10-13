import signal
from collections.abc import Generator
from copy import deepcopy

import pytest

from dify_plugin.entities.invoke_message import InvokeMessage
from dify_plugin.entities.provider_config import LogMetadata
from dify_plugin.entities.tool import ToolInvokeMessage, ToolSelector
from dify_plugin.file.constants import DIFY_FILE_IDENTITY, DIFY_TOOL_SELECTOR_IDENTITY
from dify_plugin.file.file import File
from dify_plugin.interfaces.tool import Tool


class ParameterTool(Tool):
    received: dict | None = None
    consumed = 0
    closed = False

    def _invoke(self, tool_parameters: dict) -> Generator[ToolInvokeMessage]:
        self.received = tool_parameters
        try:
            yield self.create_text_message(self.runtime.user_id or "anonymous")
            self.consumed += 1
            if tool_parameters.get("fail"):
                msg = "tool failed"
                raise ValueError(msg)
            yield self.create_variable_message("complete", True)
        finally:
            self.closed = True


@pytest.fixture
def tool() -> Generator[ParameterTool]:
    original_sigint = signal.getsignal(signal.SIGINT)
    instance = ParameterTool.from_credentials({"api_key": "valid"}, user_id="user")
    try:
        yield instance
    finally:
        instance.session.reader.close()
        instance.session.writer.close()
        instance.session._executor.shutdown(wait=True)
        signal.signal(signal.SIGINT, original_sigint)


@pytest.mark.parametrize("default", [False, True])
def test_public_invoke_converts_files_and_selectors_without_fetching(
    tool: ParameterTool, monkeypatch: pytest.MonkeyPatch, default: bool
) -> None:
    def reject_download(_file: File) -> bytes:
        pytest.fail("parameter conversion downloaded a file")

    monkeypatch.setattr(File, "blob", property(reject_download))
    file = {
        "dify_model_identity": DIFY_FILE_IDENTITY,
        "url": "https://files.invalid/example.txt",
        "type": "document",
        "filename": "example.txt",
        "mime_type": "text/plain",
        "extension": ".txt",
        "size": 4,
    }
    selector = {
        "dify_model_identity": DIFY_TOOL_SELECTOR_IDENTITY,
        "provider_id": "provider",
        "tool_name": "echo",
        "tool_description": "Echo a message",
        "tool_configuration": {"prefix": "hello"},
        "tool_parameters": {
            "enabled": {
                "name": "enabled",
                "type": "boolean",
                "required": False,
                "description": "Enable the option",
                "default": default,
            }
        },
    }
    ordinary = {"nested": file}
    mixed = [file, "ordinary"]
    parameters = {
        "file": file,
        "files": [file, file],
        "tool": selector,
        "tools": [selector, selector],
        "ordinary": ordinary,
        "mixed": mixed,
        "empty": [],
        "number": 0,
        "unknown": {"dify_model_identity": "unrecognized"},
    }
    expected = deepcopy(parameters)
    messages = list(tool.invoke(parameters))

    assert tool.received is not None
    received = tool.received
    assert isinstance(received["file"], File)
    assert received["file"].model_dump() == expected["file"]
    assert [item.model_dump() for item in received["files"]] == expected["files"]
    assert isinstance(received["tool"], ToolSelector)
    assert received["tool"].tool_configuration == {"prefix": "hello"}
    assert (
        received["tool"].model_dump(mode="json")["tool_parameters"]["enabled"][
            "default"
        ]
        is default
    )
    assert all(isinstance(item, ToolSelector) for item in received["tools"])
    assert len(received["tools"]) == 2
    assert received["ordinary"] == expected["ordinary"]
    assert received["mixed"] == expected["mixed"]
    assert received["empty"] == []
    assert received["number"] == 0
    assert received["unknown"] == {"dify_model_identity": "unrecognized"}
    assert messages[0].message.text == "user"
    assert messages[1].message.variable_value is True
    assert tool.runtime.credentials == {"api_key": "valid"}
    assert tool.closed


@pytest.mark.parametrize(
    ("parameter", "error"),
    [
        (
            {
                "dify_model_identity": DIFY_FILE_IDENTITY,
                "url": "https://files.invalid/x",
                "type": "invalid",
            },
            "not a valid FileType",
        ),
        ({"dify_model_identity": DIFY_TOOL_SELECTOR_IDENTITY}, "Field required"),
        ([{"dify_model_identity": DIFY_TOOL_SELECTOR_IDENTITY}], "Field required"),
    ],
)
def test_invalid_tagged_parameters_fail_before_plugin_execution(
    tool: ParameterTool, parameter: object, error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        list(tool.invoke({"input": parameter}))
    assert tool.received is None


@pytest.mark.parametrize("outcome", ["complete", "close", "error"])
def test_invoke_preserves_lazy_iteration_errors_and_cleanup(
    tool: ParameterTool, outcome: str
) -> None:
    stream = tool.invoke({"fail": outcome == "error"})
    assert tool.received is None
    assert tool.consumed == 0
    assert next(stream).message.text == "user"
    assert not tool.closed
    if outcome == "close":
        stream.close()
        assert tool.consumed == 0
    elif outcome == "error":
        with pytest.raises(ValueError, match="tool failed"):
            next(stream)
    else:
        assert next(stream).message.variable_name == "complete"
        with pytest.raises(StopIteration):
            next(stream)
    assert tool.closed


def test_message_helpers_preserve_payload_and_type(tool: ParameterTool) -> None:
    resource = InvokeMessage.RetrieverResourceMessage.RetrieverResource(
        document_id="document", content="evidence", score=0.75, doc_metadata={"page": 2}
    )
    messages = [
        tool.create_text_message("你好"),
        tool.create_json_message({"count": 0}),
        tool.create_json_message([{"item": 1}]),
        tool.create_image_message("https://files.invalid/image.png"),
        tool.create_link_message("https://example.invalid/"),
        tool.create_blob_message(
            b"\x00\xff", {"mime_type": "application/octet-stream"}
        ),
        tool.create_variable_message("result", {"ok": False}),
        tool.create_stream_variable_message("answer", "part one"),
        tool.create_retriever_resource_message([resource], "evidence"),
    ]
    assert all(isinstance(message, ToolInvokeMessage) for message in messages)
    payloads = [message.model_dump(mode="json") for message in messages]
    assert [payload["type"] for payload in payloads] == [
        "text",
        "json",
        "json",
        "image",
        "link",
        "blob",
        "variable",
        "variable",
        "retriever_resources",
    ]
    assert [payload["message"] for payload in payloads[:6]] == [
        {"text": "你好"},
        {"json_object": {"count": 0}},
        {"json_object": [{"item": 1}]},
        {"text": "https://files.invalid/image.png"},
        {"text": "https://example.invalid/"},
        {"blob": "AP8="},
    ]
    assert messages[5].meta == {"mime_type": "application/octet-stream"}
    assert payloads[6]["message"] == {
        "variable_name": "result",
        "variable_value": {"ok": False},
        "stream": False,
    }
    assert payloads[7]["message"] == {
        "variable_name": "answer",
        "variable_value": "part one",
        "stream": True,
    }
    assert messages[8].message.retriever_resources == [resource]
    assert messages[8].message.context == "evidence"


def test_log_lifecycle_keeps_parent_identity_and_start_data(
    tool: ParameterTool,
) -> None:
    parent = tool.create_log_message(
        "round", {}, InvokeMessage.LogMessage.LogStatus.START
    )
    child = tool.create_log_message(
        "model",
        {"prompt": "hello"},
        InvokeMessage.LogMessage.LogStatus.START,
        parent=parent,
        metadata={LogMetadata.PROVIDER: "provider"},
    )
    finished = tool.finish_log_message(child)
    failed = tool.finish_log_message(
        child,
        status=InvokeMessage.LogMessage.LogStatus.ERROR,
        error="model failed",
        data={"retryable": True},
        metadata={LogMetadata.TOTAL_TOKENS: 10},
    )
    assert child.message.parent_id == parent.message.id
    assert finished.message.id == failed.message.id == child.message.id
    assert finished.message.label == failed.message.label == "model"
    assert finished.message.parent_id == failed.message.parent_id == parent.message.id
    assert finished.message.data == child.message.data == {"prompt": "hello"}
    assert finished.message.metadata == {LogMetadata.PROVIDER: "provider"}
    assert finished.message.status == InvokeMessage.LogMessage.LogStatus.SUCCESS
    assert failed.message.error == "model failed"
    assert failed.message.status == InvokeMessage.LogMessage.LogStatus.ERROR
    assert failed.message.data == {"retryable": True}
    assert failed.message.metadata == {LogMetadata.TOTAL_TOKENS: 10}
    assert child.message.status == InvokeMessage.LogMessage.LogStatus.START
    with pytest.raises(TypeError, match="Log message payload is required"):
        tool.finish_log_message(tool.create_text_message("not a log"))


@pytest.mark.parametrize("invalid_second_file", [False, True])
def test_parameter_conversion_supports_reuse_and_retry_after_invalid_file(
    tool: ParameterTool, invalid_second_file: bool
) -> None:
    file = {
        "dify_model_identity": DIFY_FILE_IDENTITY,
        "url": "https://files.invalid/report.txt",
        "type": "document",
        "filename": "report.txt",
        "mime_type": "text/plain",
        "extension": ".txt",
        "size": 4,
    }
    parameters = {
        "first": file,
        "second": file | {"type": "invalid"} if invalid_second_file else file,
    }
    if invalid_second_file:
        with pytest.raises(ValueError, match="not a valid FileType"):
            list(tool.invoke(parameters))
        assert tool.received is None
        parameters["second"] = file

    first = list(tool.invoke(parameters))
    second = list(tool.invoke(parameters))

    assert first == second
    assert tool.received is not None
    for name in ("first", "second"):
        assert isinstance(tool.received[name], File)
        assert tool.received[name].model_dump() == file
