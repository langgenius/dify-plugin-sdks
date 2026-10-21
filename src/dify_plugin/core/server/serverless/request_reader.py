import logging
import socket
import sys
import threading
import time
from collections.abc import Generator
from queue import Empty, Queue

import gevent.socket
from flask import Flask, request
from gevent.pywsgi import WSGIServer
from werkzeug.serving import BaseWSGIServer, make_server

from dify_plugin.core.entities.plugin.io import (
    PluginInStream,
    PluginInStreamEvent,
)
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.serverless.response_writer import ServerlessResponseWriter

logger = logging.getLogger(__name__)


class ServerlessRequestReader(RequestReader):
    def __init__(
        self,
        host: str = "0.0.0.0",  # ruff:ignore[hardcoded-bind-all-interfaces]
        port: int = 8080,
        worker_class: str = "gevent",
        workers: int = 5,
        worker_connections: int = 1000,
        threads: int = 5,
        max_single_connection_lifetime: int = 300,
    ) -> None:
        """
        Initialize the ServerlessStream and wait for jobs
        """
        super().__init__()
        self.app = Flask(__name__)
        self.host = host
        self.port = port
        self.workers = workers
        self.worker_class = worker_class
        self.threads = threads
        self.worker_connections = worker_connections
        self.max_single_connection_lifetime = max_single_connection_lifetime
        self.request_queue = Queue[PluginInStream | None]()
        self._shutdown = threading.Event()
        self._http_server: BaseWSGIServer | None = None

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        """
        Read request from http server
        """
        while (message := self.request_queue.get()) is not None:
            yield message

    def close(self) -> None:
        super().close()
        self.request_queue.put(None)
        self._shutdown.set()
        with self.lock:
            server, self._http_server = self._http_server, None
        if server is not None:
            server.shutdown()

    def handler(self) -> tuple[Generator[str, None, None], int] | tuple[str, int]:
        try:
            queue: Queue[str | None] = Queue()
            data = request.get_json()
            writer = ServerlessResponseWriter(queue)
            plugin_in = PluginInStream(
                event=PluginInStreamEvent.value_of(data["event"]),
                session_id=data["session_id"],
                conversation_id=data.get("conversation_id"),
                message_id=data.get("message_id"),
                app_id=data.get("app_id"),
                endpoint_id=data.get("endpoint_id"),
                data=data["data"],
                context=data.get("context"),
                reader=self,
                writer=writer,
            )
            self.request_queue.put(plugin_in)
        except Exception:
            logger.exception("Failed to accept serverless request")
            return "Internal Server Error", 500

        def generate() -> Generator[str, None, None]:
            try:
                yield ""
                refresh_time = time.time()
                while True:
                    try:
                        response = queue.get(timeout=1)
                    except Empty:
                        if (
                            time.time() - refresh_time
                            > self.max_single_connection_lifetime
                        ):
                            return
                        continue

                    if response is None:
                        return

                    refresh_time = time.time()
                    yield response
            finally:
                writer.close()

        response = generate()
        # Arm cleanup before Flask receives the response iterator.
        next(response)
        return response, 200

    def health(self) -> tuple[str, int]:
        return "OK", 200

    def _run(self) -> None:
        self.app.route("/invoke", methods=["POST"])(self.handler)
        self.app.route("/health", methods=["GET"])(self.health)

        if socket.socket is gevent.socket.socket:
            server = WSGIServer((self.host, self.port), self.app)
            sys.stdout.write(
                "* Serving Flask app "
                "'dify_plugin.core.server.serverless.request_reader'\n"
            )
            sys.stdout.write(
                f"* Running on http://{self.host}:{self.port} (Press CTRL+C to quit)\n"
            )
            sys.stdout.write("* Server Worker: gevent.wsgi.WSGIServer\n")
            sys.stdout.flush()
            try:
                with self.lock:
                    if self._closed:
                        return
                    server.start()
                self._shutdown.wait()
            finally:
                server.stop()
        else:
            server = make_server(self.host, self.port, self.app, threaded=True)
            with self.lock:
                if self._closed:
                    server.server_close()
                    return
                self._http_server = server
            server.serve_forever()

    def launch(self) -> None:
        """
        Launch server
        """
        threading.Thread(target=self._run).start()
