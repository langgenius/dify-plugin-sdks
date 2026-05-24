import errno
import logging
import os
import signal
import socket
import time
from collections.abc import Callable, Generator
from select import select
from threading import Lock
from typing import Any

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
        self.on_connected = on_connected
        self.opt_lock = Lock()

        signal.signal(signal.SIGINT, lambda *_args, **_kwargs: os._exit(0))

    def launch(self) -> None:
        """Launch the connection"""
        self._launch()

    def close(self) -> None:
        """Close the connection"""
        if self.alive:
            with self.opt_lock:
                self.sock.close()
            self.alive = False

    def _write_to_sock(self, data: bytes) -> None:
        """Write data to the socket"""
        with self.opt_lock:
            self.sock.sendall(data)

    def _recv_from_sock(self, size: int) -> bytes:
        """Receive data from the socket"""
        return self.sock.recv(size)

    def write(self, data: str) -> None:
        if not self.alive:
            msg = "connection is dead"
            raise Exception(msg)

        try:
            self._write_to_sock(data.encode())
        except Exception:
            logger.exception("Failed to write data")
            self._launch()

    def done(self) -> None:
        pass

    def _launch(self) -> None:
        """Connect to the target, try to reconnect if failed"""
        attempts = 0
        while attempts < self.reconnect_attempts:
            try:
                self._connect()
                break
            except Exception:
                attempts += 1
                if attempts >= self.reconnect_attempts:
                    raise

                time.sleep(self.reconnect_timeout)

    def _connect(self) -> None:
        """Connect to the target"""
        try:
            self.sock = socket.create_connection((self.host, self.port))
            self.alive = True
            handshake_message = InitializeMessage(
                type=InitializeMessage.Type.HANDSHAKE,
                data=InitializeMessage.Key(key=self.key).model_dump(),
            )
            self.sock.sendall(handshake_message.model_dump_json().encode() + b"\n")
            logger.info("\033[32mConnected to %s:%s\033[0m", self.host, self.port)
            if self.on_connected:
                self.on_connected()
            logger.info("Sent key to %s:%s", self.host, self.port)
        except OSError:
            logger.exception(
                "\033[31mFailed to connect to %s:%s\033[0m",
                self.host,
                self.port,
            )
            raise

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        """Read data from the target"""
        buffer = b""
        while self.alive:
            try:
                ready_to_read, _, _ = select([self.sock], [], [], 1)
                if not ready_to_read:
                    continue
                try:
                    data = self._recv_from_sock(1048576)
                except BlockingIOError as e:
                    if e.errno != errno.EAGAIN:
                        raise
                    continue
                if data == b"":
                    msg = "Connection is closed"
                    raise Exception(msg)
            except Exception:
                logger.exception(
                    "\033[31mFailed to read data from %s:%s\033[0m",
                    self.host,
                    self.port,
                )
                self.alive = False
                time.sleep(self.reconnect_timeout)
                self._launch()
                continue

            if not data:
                continue

            buffer += data

            # process line by line and keep the last line if it is not complete
            lines = buffer.split(b"\n")
            if len(lines) == 0:
                continue

            buffer = lines[-1]

            lines = lines[:-1]
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
