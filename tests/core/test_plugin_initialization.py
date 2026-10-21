import base64
from collections.abc import Callable
from pathlib import Path

import pytest

from dify_plugin import plugin as plugin_module
from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.setup import PluginAsset
from dify_plugin.plugin import Plugin

from .plugin_fixtures import (
    CapturingWriter,
    MemoryReader,
    contract_plugin,
    contract_source,
)

__all__ = ["contract_plugin", "contract_source"]


def test_local_initialization_writes_manifest_first(contract_plugin: Plugin) -> None:
    writer = contract_plugin.default_response_writer
    assert isinstance(writer, CapturingWriter)
    messages = writer.messages()
    assert len(messages) == 1
    assert messages[0]["name"] == "contract_plugin"
    assert messages[0]["plugins"]["tools"] == ["provider/contract.yaml"]
    assert messages[0]["plugins"]["triggers"] == ["triggers/events.yaml"]
    assert writer.output[0].endswith("\n\n")


def test_remote_initialization_sends_all_declarations_before_assets(
    contract_plugin: Plugin,
) -> None:
    stream = CapturingWriter()
    contract_plugin._initialize_tcp_stream(stream)
    messages = stream.messages()

    assert [message["type"] for message in messages[:7]] == [
        "manifest_declaration",
        "tool_declaration",
        "model_declaration",
        "endpoint_declaration",
        "agent_strategy_declaration",
        "datasource_declaration",
        "trigger_declaration",
    ]
    assert messages[0]["data"]["name"] == "contract_plugin"
    assert messages[1]["data"][0]["identity"]["name"] == "contract"
    assert messages[1]["data"][0]["tools"][0]["has_runtime_parameters"] is True
    assert messages[2]["data"][0]["provider"] == "contract_models"
    assert messages[3]["data"][0]["endpoints"][0]["path"] == "/echo/<item>"
    assert messages[4]["data"][0]["identity"]["name"] == "contract_agents"
    assert {provider["identity"]["name"] for provider in messages[5]["data"]} == {
        "website",
        "documents",
        "drive",
    }
    assert messages[6]["data"][0]["identity"]["name"] == "events"
    assert all(message["type"] == "asset_chunk" for message in messages[7:-1])
    assert messages[-1] == {"type": "end", "data": {}}
    assert all(frame.endswith("\n\n") for frame in stream.output)


@pytest.mark.parametrize("size", [0, 8191, 8192, 8193, 16384])
def test_remote_asset_chunks_preserve_each_file(
    contract_plugin: Plugin, size: int
) -> None:
    content = b"\x00\xff" * (size // 2) + b"x" * (size % 2)
    contract_plugin.registration.files = [
        PluginAsset(filename="test.bin", data=content)
    ]
    stream = CapturingWriter()

    contract_plugin._initialize_tcp_stream(stream)

    chunks = [
        message["data"]
        for message in stream.messages()
        if message["type"] == "asset_chunk"
    ]
    assert len(chunks) == (size + 8191) // 8192
    assert all(chunk["filename"] == "test.bin" for chunk in chunks)
    assert all(chunk["data"] for chunk in chunks)
    assert [chunk["end"] for chunk in chunks] == (
        [False] * (len(chunks) - 1) + [True] if chunks else []
    )
    assert b"".join(base64.b64decode(chunk["data"]) for chunk in chunks) == content


def test_remote_initialization_omits_undeclared_extensions(
    contract_plugin: Plugin,
) -> None:
    registration = contract_plugin.registration
    registration.tools_configuration.clear()
    registration.models_configuration.clear()
    registration.endpoints_configuration.clear()
    registration.agent_strategies_configuration.clear()
    registration.datasource_configuration.clear()
    registration.triggers_configuration.clear()
    registration.files.clear()
    stream = CapturingWriter()

    contract_plugin._initialize_tcp_stream(stream)

    assert [message["type"] for message in stream.messages()] == [
        "manifest_declaration",
        "end",
    ]


def test_remote_constructor_launches_transport_with_registration_callback(
    contract_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del contract_source
    connections = []

    class RemoteStream(MemoryReader, CapturingWriter):
        def __init__(
            self, host: str, port: int, key: str, on_connected: Callable
        ) -> None:
            MemoryReader.__init__(self)
            CapturingWriter.__init__(self)
            self.on_connected = on_connected
            connections.append((host, port, key))

        def launch(self) -> None:
            self.on_connected()

    monkeypatch.setattr(plugin_module, "TCPReaderWriter", RemoteStream)
    plugin = Plugin(
        DifyPluginEnv(
            INSTALL_METHOD="remote",
            REMOTE_INSTALL_URL="tcp://127.0.0.1:6500",
            REMOTE_INSTALL_KEY="test-key",
        )
    )
    try:
        assert connections == [("127.0.0.1", 6500, "test-key")]
        assert plugin.request_reader is plugin.default_response_writer
        messages = plugin.default_response_writer.messages()
        assert messages[0]["type"] == "manifest_declaration"
        assert messages[-1]["type"] == "end"
    finally:
        plugin.close()
        plugin.executer.shutdown(wait=True)


def test_remote_constructor_requires_install_key(contract_source: Path) -> None:
    del contract_source
    with pytest.raises(ValueError, match="Missing remote install key"):
        Plugin(DifyPluginEnv(INSTALL_METHOD="remote", REMOTE_INSTALL_KEY=None))


def test_serverless_constructor_passes_worker_configuration(
    contract_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    del contract_source
    options = {}
    launches = []

    class ServerlessStream(MemoryReader):
        def __init__(self, **kwargs: object) -> None:
            super().__init__()
            options.update(kwargs)

        def launch(self) -> None:
            launches.append(True)

    monkeypatch.setattr(plugin_module, "ServerlessRequestReader", ServerlessStream)
    plugin = Plugin(
        DifyPluginEnv(
            INSTALL_METHOD="serverless",
            SERVERLESS_HOST="127.0.0.1",
            SERVERLESS_PORT=9000,
            SERVERLESS_WORKERS=2,
            SERVERLESS_THREADS=3,
            SERVERLESS_WORKER_CONNECTIONS=20,
            MAX_REQUEST_TIMEOUT=30,
        )
    )
    try:
        assert launches == [True]
        assert options == {
            "host": "127.0.0.1",
            "port": 9000,
            "worker_class": "gevent",
            "workers": 2,
            "threads": 3,
            "worker_connections": 20,
            "max_single_connection_lifetime": 30,
        }
        assert plugin.default_response_writer is None
    finally:
        plugin.close()
        plugin.executer.shutdown(wait=True)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (None, ("configured-host", 7000)),
        ("host:6500", ("host", 6500)),
        ("tcp://host:6500", ("host", 6500)),
        ("http://host", ("host", 80)),
        ("tcp://[::1]:6500", ("::1", 6500)),
    ],
)
def test_remote_address_formats(url: str | None, expected: tuple[str, int]) -> None:
    config = DifyPluginEnv(
        REMOTE_INSTALL_URL=url,
        REMOTE_INSTALL_HOST="configured-host",
        REMOTE_INSTALL_PORT=7000,
    )
    assert Plugin._get_remote_install_host_and_port(config) == expected


@pytest.mark.parametrize("url", ["host", "host:not-a-port"])
def test_remote_address_rejects_invalid_port_configuration(url: str) -> None:
    with pytest.raises(ValueError, match=r"Invalid remote install URL|invalid literal"):
        Plugin._get_remote_install_host_and_port(DifyPluginEnv(REMOTE_INSTALL_URL=url))
