import logging
import os
import signal
import socket as native_socket
import time
from collections.abc import Callable, Generator
from contextlib import suppress
from threading import Lock
from typing import Any

from gevent.select import select
from pydantic import TypeAdapter

from dify_plugin.core.entities.message import InitializeMessage
from dify_plugin.core.entities.plugin.io import (
    PluginInStream,
    PluginInStreamEvent,
)
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter

logger = logging.getLogger(__name__)


class TCPReaderWriter(RequestReader, ResponseWriter):
    def __init__(
        self,
        host: str,
        port: int,
        key: str,
        reconnect_attempts: int = 3,
        reconnect_timeout: int = 5,
        on_connected: Callable | None = None,
    ) -> None:
        """Initialize the TCPStream and connect to the target, raising an
        exception if connection failed.
        """
        super().__init__()

        self.host = host
        self.port = port
        self.key = key
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_timeout = reconnect_timeout
        self.alive = False
        self._closed = True
        self.on_connected = on_connected
        self.opt_lock = Lock()
        self._state_lock = Lock()
        self._connect_lock = Lock()

        # handle SIGINT to exit the program smoothly due to the gevent limitation
        signal.signal(signal.SIGINT, lambda *_args, **_kwargs: os._exit(0))

    def launch(self) -> None:
        """Launch the connection"""
        with self._state_lock:
            self._closed = False
        self._launch()

    def _launch(self) -> None:
        with self._connect_lock:
            with self._state_lock:
                if self._closed or self.alive:
                    return

            for attempt in range(self.reconnect_attempts):
                if self._closed:
                    return

                try:
                    self._connect()
                    break
                except Exception:
                    if self._closed:
                        return
                    if attempt + 1 == self.reconnect_attempts:
                        raise

                    time.sleep(self.reconnect_timeout)

    def close(self) -> None:
        """Close the connection"""
        with self._state_lock:
            self._closed = True
            self.alive = False
            sock = getattr(self, "sock", None)

        if sock:
            with suppress(OSError):
                sock.close()

    def _disconnect(self, sock: native_socket.socket) -> None:
        with self._state_lock:
            if sock is self.sock:
                self.alive = False

        sock.close()

    def write(self, data: str) -> None:
        with self._state_lock:
            if not self.alive:
                msg = "connection is dead"
                raise Exception(msg)
            sock = self.sock

        try:
            with self.opt_lock:
                sock.sendall(data.encode())
        except Exception:
            logger.exception("Failed to write data")
            with suppress(OSError):
                self._disconnect(sock)
            raise

    def done(self) -> None:
        pass

    def _connect(self) -> None:
        """Connect to the target"""
        handshake = InitializeMessage(
            type=InitializeMessage.Type.HANDSHAKE,
            data=InitializeMessage.Key(key=self.key).model_dump(),
        ).model_dump_json()

        sock = None
        try:
            sock = native_socket.create_connection((self.host, self.port))
            sock.sendall(handshake.encode() + b"\n")
        except OSError:
            logger.exception(
                "\033[31mFailed to connect to %s:%s\033[0m",
                self.host,
                self.port,
            )
            if sock:
                with suppress(OSError):
                    sock.close()
            raise

        with self._state_lock:
            connected = not self._closed
            if connected:
                old_sock = getattr(self, "sock", None)
                self.sock = sock
                self.alive = True

        if not connected:
            sock.close()
            return
        if old_sock and old_sock is not sock:
            with suppress(OSError):
                old_sock.close()

        logger.info("\033[32mConnected to %s:%s\033[0m", self.host, self.port)
        try:
            if self.on_connected:
                self.on_connected()
        except Exception:
            with suppress(OSError):
                self._disconnect(sock)
            raise
        logger.info("Sent key to %s:%s", self.host, self.port)

    def _receive_available(self, sock: native_socket.socket) -> bytes | None:
        ready_to_read, _, _ = select([sock], [], [], 1)
        if not ready_to_read:
            return None
        return sock.recv(1048576)

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        """Read data from the target"""
        buffer = b""
        while not self._closed:
            if not self.alive:
                buffer = b""
                time.sleep(self.reconnect_timeout)
                if self._closed:
                    return
                with suppress(OSError):
                    self._launch()
                continue

            try:
                with self._state_lock:
                    sock = self.sock
                data = self._receive_available(sock)
                if data == b"":
                    msg = "Connection is closed"
                    raise ConnectionError(msg)
            except Exception:
                logger.exception(
                    "\033[31mFailed to read data from %s:%s\033[0m",
                    self.host,
                    self.port,
                )
                with suppress(OSError):
                    self._disconnect(sock)
                continue

            if data is None:
                continue

            buffer += data

            # process line by line and keep the last line if it is not complete
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                try:
                    data = TypeAdapter(dict[str, Any]).validate_json(line)
                    chunk = PluginInStream(
                        session_id=data["session_id"],
                        conversation_id=data.get("conversation_id"),
                        message_id=data.get("message_id"),
                        app_id=data.get("app_id"),
                        endpoint_id=data.get("endpoint_id"),
                        event=PluginInStreamEvent.value_of(data["event"]),
                        data=data["data"],
                        context=data.get("context"),
                        reader=self,
                        writer=self,
                    )
                    yield chunk
                    logger.info(
                        "Received event: \n%s\n session_id: \n%s\n data: \n%s",
                        chunk.event,
                        chunk.session_id,
                        chunk.data,
                    )
                except Exception:
                    logger.exception(
                        "\x1b[31mAn error occurred while parsing the data: %s\x1b[0m",
                        line,
                    )
