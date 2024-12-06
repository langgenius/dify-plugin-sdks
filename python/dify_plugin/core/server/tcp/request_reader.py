import logging
import socket
import time
from collections.abc import Generator
from json import loads
from typing import Callable, Optional

from gevent.select import select

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
        on_connected: Optional[Callable] = None,
    ):
        """
        Initialize the TCPStream and connect to the target, raise exception if connection failed
        """
        self.host = host
        self.port = port
        self.key = key
        self.reconnect_attempts = reconnect_attempts
        self.reconnect_timeout = reconnect_timeout
        self.alive = False
        self.on_connected = on_connected

    def launch(self):
        """
        Launch the connection
        """
        self._launch()

    def close(self):
        """
        Close the connection
        """
        if self.alive:
            self.sock.close()
            self.alive = False

    def write(self, data: str):
        if not self.alive:
            raise Exception("connection is dead")

        try:
            self.sock.sendall(data.encode())
        except Exception:
            logger.exception("Failed to write data")
            self._launch()

    def done(self):
        pass

    def _launch(self):
        """
        Connect to the target, try to reconnect if failed
        """
        attempts = 0
        while attempts < self.reconnect_attempts:
            try:
                self._connect()
                break
            except Exception as e:
                attempts += 1
                if attempts >= self.reconnect_attempts:
                    raise e

                time.sleep(self.reconnect_timeout)

    def _connect(self):
        """
        Connect to the target
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.alive = True
            handshake_message = InitializeMessage(
                type=InitializeMessage.Type.HANDSHAKE,
                data=InitializeMessage.Key(key=self.key).model_dump(),
            )
            self.sock.sendall(handshake_message.model_dump_json().encode() + b"\n")
            logger.info(f"\033[32mConnected to {self.host}:{self.port}\033[0m")
            if self.on_connected:
                self.on_connected()
            logger.info(f"Sent key to {self.host}:{self.port}")
        except OSError as e:
            logger.exception(f"\033[31mFailed to connect to {self.host}:{self.port}\033[0m")
            raise e

    def _read_stream(self) -> Generator[PluginInStream, None, None]:
        """
        Read data from the target
        """
        buffer = b""
        while self.alive:
            try:
                ready_to_read, _, _ = select([self.sock], [], [], 1)
                if not ready_to_read:
                    continue
                data = self.sock.recv(4096)
                if data == b"":
                    raise Exception("Connection is closed")
            except Exception:
                logger.exception(f"\033[31mFailed to read data from {self.host}:{self.port}\033[0m")
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
                    data = loads(line)
                    chunk = PluginInStream(
                        session_id=data["session_id"],
                        event=PluginInStreamEvent.value_of(data["event"]),
                        data=data["data"],
                        reader=self,
                        writer=self,
                    )
                    yield chunk
                    logger.info(
                        f"Received event: \n{chunk.event}\n session_id: \n{chunk.session_id}\n data: \n{chunk.data}"
                    )
                except Exception:
                    logger.exception(f"\033[31mAn error occurred while parsing the data: {line}\033[0m")
