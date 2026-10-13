from collections.abc import Generator
from pathlib import Path

import pytest
from werkzeug import Response

from dify_plugin.plugin import Plugin

from .plugin_fixtures import CapturingWriter, contract_plugin, contract_source, invoke

__all__ = ["contract_plugin", "contract_source"]

ENDPOINT_REQUEST = {
    "type": "endpoint",
    "action": "invoke_endpoint",
    "raw_http_request": b"POST /echo/item HTTP/1.1\r\nHost: localhost\r\n\r\n".hex(),
    "settings": {},
}


@pytest.mark.parametrize("outcome", ["complete", "provider-error", "disconnect"])
def test_endpoint_closes_stream_and_response_when_request_ends(
    contract_plugin: Plugin,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
) -> None:
    resource = (tmp_path / "response.bin").open("w+b")
    resource.write(b"firstsecond")
    resource.seek(0)
    closed: list[str] = []

    def chunks() -> Generator[bytes]:
        try:
            yield resource.read(5)
            if outcome == "provider-error":
                msg = "upstream response interrupted"
                raise OSError(msg)
            yield resource.read()
        finally:
            closed.append("iterator")

    response = Response(chunks(), content_type="application/octet-stream")
    response.call_on_close(resource.close)
    response.call_on_close(lambda: closed.append("response"))
    endpoint = next(contract_plugin.registration.endpoints.iter_rules()).endpoint
    monkeypatch.setattr(endpoint, "_invoke", lambda *_args: response)
    writer = CapturingWriter()

    if outcome == "disconnect":
        write = writer.write

        def disconnect(data: str) -> None:
            if len(writer.output) == 2:
                msg = "daemon disconnected after first body chunk"
                raise BrokenPipeError(msg)
            write(data)

        monkeypatch.setattr(writer, "write", disconnect)

    try:
        if outcome == "disconnect":
            with pytest.raises(BrokenPipeError, match="daemon disconnected"):
                contract_plugin._execute_request_in_thread(
                    "session-1",
                    ENDPOINT_REQUEST,
                    contract_plugin.request_reader,
                    writer,
                )
        else:
            contract_plugin._execute_request_in_thread(
                "session-1", ENDPOINT_REQUEST, contract_plugin.request_reader, writer
            )

        messages = [message["data"] for message in writer.messages()]
        assert messages[0]["data"]["status"] == 200
        assert messages[1]["data"]["result"] == b"first".hex()
        assert writer.done_count == 1
        if outcome == "complete":
            assert [message["type"] for message in messages] == [
                "stream",
                "stream",
                "stream",
                "end",
            ]
            assert messages[2]["data"]["result"] == b"second".hex()
        elif outcome == "provider-error":
            assert [message["type"] for message in messages] == [
                "stream",
                "stream",
                "error",
                "end",
            ]
            assert messages[2]["data"]["error_type"] == "OSError"
            assert messages[2]["data"]["message"] == "upstream response interrupted"
        else:
            assert [message["type"] for message in messages] == ["stream", "stream"]

        # Werkzeug Response.close owns both iterator cleanup and close callbacks.
        assert closed == ["iterator", "response"]
        assert resource.closed
    finally:
        response.close()
        resource.close()


def test_endpoint_closes_file_iterable_after_sending_its_body(
    contract_plugin: Plugin, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "response.txt"
    path.write_bytes(b"first\nsecond\n")
    resource = path.open("rb")
    response = Response(resource, content_type="text/plain")
    endpoint = next(contract_plugin.registration.endpoints.iter_rules()).endpoint
    monkeypatch.setattr(endpoint, "_invoke", lambda *_args: response)

    try:
        messages = invoke(contract_plugin, ENDPOINT_REQUEST)

        assert len(messages) == 1
        assert messages[0]["type"] == "stream"
        assert messages[0]["data"]["status"] == 200
        assert bytes.fromhex(messages[0]["data"]["result"]) == path.read_bytes()
        assert resource.closed
    finally:
        response.close()
