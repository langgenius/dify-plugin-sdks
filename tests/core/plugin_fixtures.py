import json
import shutil
import sys
from collections.abc import Generator
from pathlib import Path

import pytest

from dify_plugin import plugin as plugin_module
from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.entities.plugin.io import PluginInStream
from dify_plugin.core.server.io_server import RequestReader, ResponseWriter
from dify_plugin.plugin import Plugin

CONTRACT_SOURCE = Path(__file__).parents[1] / "fixtures/plugins/contract_plugin"


class MemoryReader(RequestReader):
    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        yield from ()


class CapturingWriter(ResponseWriter):
    def __init__(self) -> None:
        self.output: list[str] = []
        self.done_count = 0

    def write(self, data: str) -> None:
        self.output.append(data)

    def done(self) -> None:
        self.done_count += 1

    def messages(self) -> list[dict]:
        return [json.loads(line) for line in "".join(self.output).splitlines() if line]


@pytest.fixture
def contract_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Path, None, None]:
    source = tmp_path / "plugin"
    shutil.copytree(
        CONTRACT_SOURCE, source, ignore=shutil.ignore_patterns("__pycache__")
    )
    monkeypatch.chdir(source)
    monkeypatch.syspath_prepend(str(source))
    packages = {p.name for p in source.iterdir() if p.is_dir() and p.name != "_assets"}
    original_modules = {
        name: module
        for name, module in sys.modules.copy().items()
        if name.partition(".")[0] in packages
    }
    for name in original_modules:
        del sys.modules[name]
    try:
        yield source
    finally:
        for name in tuple(sys.modules):
            if name.partition(".")[0] in packages:
                del sys.modules[name]
        sys.modules.update(original_modules)


@pytest.fixture
def contract_plugin(
    contract_source: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[Plugin, None, None]:
    del contract_source
    monkeypatch.setattr(plugin_module, "StdioRequestReader", MemoryReader)
    monkeypatch.setattr(plugin_module, "StdioResponseWriter", CapturingWriter)
    plugin = Plugin(DifyPluginEnv(INSTALL_METHOD="local"))
    try:
        yield plugin
    finally:
        plugin.close()
        plugin.executer.shutdown(wait=True)


def invoke(plugin: Plugin, request: dict, **context: object) -> list[dict]:
    writer = CapturingWriter()
    plugin._execute_request_in_thread(
        "session-1", request, plugin.request_reader, writer, **context
    )
    messages = writer.messages()
    assert writer.done_count == 1
    assert all(message["session_id"] == "session-1" for message in messages)
    assert all(message["event"] == "session" for message in messages)
    assert messages[-1]["data"] == {"type": "end", "data": {}}
    assert sum(message["data"]["type"] == "end" for message in messages) == 1
    return [message["data"] for message in messages[:-1]]
