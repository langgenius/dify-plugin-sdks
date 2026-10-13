import json
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

import pytest

from dify_plugin.core.entities.invocation import InvokeType
from dify_plugin.core.runtime import BackwardsInvocation, Session
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter


@dataclass
class RecordedInvocation:
    requests: list[tuple[InvokeType, type, dict[str, Any]]] = field(
        default_factory=list
    )
    yielded: int = 0
    closed: bool = False


type RecordInvocation = Callable[
    [BackwardsInvocation, list[dict[str, Any] | Exception]], RecordedInvocation
]


@pytest.fixture
def session() -> Generator[Session]:
    reader = StdioRequestReader()
    with ThreadPoolExecutor() as executor:
        try:
            yield Session(
                "invocation", executor, reader, StdioResponseWriter(), app_id="app"
            )
        finally:
            reader.close()


@pytest.fixture
def record_invocation(monkeypatch: pytest.MonkeyPatch) -> RecordInvocation:
    def record(
        invocation: BackwardsInvocation, responses: list[dict[str, Any] | Exception]
    ) -> RecordedInvocation:
        recorded = RecordedInvocation()
        writer = StdioResponseWriter()

        def invoke(
            invoke_type: InvokeType, data_type: type, data: dict
        ) -> Generator[object, None, None]:
            envelope = json.loads(
                writer.session_message_text(
                    "session", writer.stream_invoke_object(data)
                )
            )
            recorded.requests.append((invoke_type, data_type, envelope["data"]["data"]))
            try:
                for response in responses:
                    if isinstance(response, Exception):
                        raise response
                    recorded.yielded += 1
                    yield data_type(**response)
            finally:
                recorded.closed = True

        monkeypatch.setattr(invocation, "_backwards_invoke", invoke)
        return recorded

    return record
