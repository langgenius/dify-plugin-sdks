import threading
import time
from collections.abc import Generator
from queue import Empty, Queue

from flask import Flask, request

from dify_plugin.core.entities.plugin.io import (
    PluginInStream,
    PluginInStreamEvent,
)
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.serverless.response_writer import ServerlessResponseWriter


class ServerlessRequestReader(RequestReader):
    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8080,
        worker_class: str = "gevent",
        workers: int = 5,
        worker_connections: int = 1000,
        threads: int = 5,
        max_single_connection_lifetime: int = 300,
    ):
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
        self.request_queue = Queue[PluginInStream]()

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        """
        Read request from http server
        """
        while True:
            yield self.request_queue.get()

    def handler(self):
        try:
            queue = Queue[str]()
            data = request.get_json()
            event = PluginInStreamEvent.value_of(data["event"])
            plugin_in = PluginInStream(
                event=event,
                session_id=data["session_id"],
                conversation_id=data.get("conversation_id"),
                message_id=data.get("message_id"),
                app_id=data.get("app_id"),
                endpoint_id=data.get("endpoint_id"),
                data=data["data"],
                reader=self,
                writer=ServerlessResponseWriter(queue),
            )
            # put request to queue
            self.request_queue.put(plugin_in)

            # wait for response
            def generate():
                refresh_time = time.time()
                while True:
                    try:
                        response = queue.get(timeout=1)
                    except Empty:
                        if time.time() - refresh_time > self.max_single_connection_lifetime:
                            # reach max single connection lifetime
                            break
                        continue

                    if response is None:
                        break

                    # refresh refresh_time
                    refresh_time = time.time()
                    yield response

            return generate(), 200
        except Exception as e:
            return str(e), 500

    def health(self):
        return "OK", 200

    def _run(self):
        self.app.route("/invoke", methods=["POST"])(self.handler)
        self.app.route("/health", methods=["GET"])(self.health)

        import socket

        import gevent.socket

        if socket.socket is gevent.socket.socket:
            from gevent.pywsgi import WSGIServer

            server = WSGIServer((self.host, self.port), self.app)
            print("* Serving Flask app 'dify_plugin.core.server.serverless.request_reader'")
            print(f"* Running on http://{self.host}:{self.port} (Press CTRL+C to quit)")
            print("* Server Worker: gevent.wsgi.WSGIServer", flush=True)
            server.serve_forever()
        else:
            self.app.run(host=self.host, port=self.port, threaded=True)

    def launch(self):
        """
        Launch server
        """
        threading.Thread(target=self._run).start()
