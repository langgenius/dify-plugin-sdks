import socket
import sys
import threading
from collections.abc import Generator
from queue import Empty, Queue

import gevent.socket
from flask import Flask, Response, request
from gevent.pywsgi import WSGIServer
from pydantic import TypeAdapter
from werkzeug.serving import BaseWSGIServer, make_server

from dify_plugin.core.entities.plugin.io import (
    PluginInStream,
    PluginInStreamBase,
)
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.serverless.response_writer import ServerlessResponseWriter


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
        self.app.route("/invoke", methods=["POST"])(self.handler)
        self.app.route("/health", methods=["GET"])(self.health)
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

    def handler(self) -> tuple[Response, int] | tuple[str, int]:
        try:
            queue: Queue[str | None] = Queue()
            data = TypeAdapter(PluginInStreamBase).validate_python(request.get_json())
            writer = ServerlessResponseWriter(queue)
            plugin_in = PluginInStream(
                event=data.event,
                session_id=data.session_id,
                conversation_id=data.conversation_id,
                message_id=data.message_id,
                app_id=data.app_id,
                endpoint_id=data.endpoint_id,
                data=data.data,
                context=data.context,
                reader=self,
                writer=writer,
            )
            self.request_queue.put(plugin_in)
        except Exception as e:
            return str(e), 500

        def generate() -> Generator[str, None, None]:
            try:
                while True:
                    try:
                        response = queue.get(
                            timeout=self.max_single_connection_lifetime
                        )
                    except Empty:
                        writer.close()
                        yield writer.session_message_text(
                            data.session_id,
                            writer.stream_error_object({
                                "error_type": "TimeoutError",
                                "message": (
                                    "Plugin request timed out waiting for a response"
                                ),
                                "args": {},
                            }),
                        )
                        yield writer.session_message_text(
                            data.session_id, writer.stream_end_object()
                        )
                        return

                    if response is None:
                        return

                    yield response
            finally:
                writer.close()

        response = Response(generate())
        response.call_on_close(writer.close)
        return response, 200

    def health(self) -> tuple[str, int]:
        return "OK", 200

    def _run(self) -> None:
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
