from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from threading import Event

from pytest_httpserver import HTTPServer as BaseHTTPServer


class HTTPServer(BaseHTTPServer):
    def thread_target(self) -> None:
        # The default poll adds up to 0.5 seconds to every fixture teardown.
        assert self.server is not None
        self.server.serve_forever(poll_interval=0.01)


@dataclass
class Response:
    status: int = 200
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    chunks: tuple[bytes, ...] | None = None
    delay: float = 0

    def stream(self, stopped: Event) -> Iterator[bytes]:
        # Send headers before delaying the body, as a real streaming service does.
        yield b""
        for chunk in self.chunks if self.chunks is not None else (self.body,):
            if stopped.wait(self.delay):
                return
            yield chunk


@dataclass
class Request:
    method: str
    path: str
    headers: Mapping[str, str]
    body: bytes


@dataclass
class TestHTTPServer:
    __test__ = False

    url: str
    requests: list[Request] = field(default_factory=list)


type HTTPServerFactory = Callable[..., TestHTTPServer]
