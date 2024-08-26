from json import loads
import socket
import time
from typing import Callable, Generator, Optional

from gevent.select import select

from dify_plugin.core.runtime.entities.plugin.io import PluginInStream
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.__base.stream_reader import PluginInputStreamReader

import logging

logger = logging.getLogger(__name__)


class TCPReaderWriter(PluginInputStreamReader, ResponseWriter):
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
        except Exception as e:
            logger.error(f"Failed to write data: {e}")
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
            self.sock.sendall(self.key.encode() + b"\n")
            if self.on_connected:
                self.on_connected()
            logger.info(f"Connected to {self.host}:{self.port}")
        except socket.error as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}, {e}")
            raise e

    def read(self) -> Generator[PluginInStream, None, None]:
        """
        Read data from the target
        """
        buffer = ""
        while self.alive:
            try:
                ready_to_read, _, _ = select([self.sock], [], [], 1)
                if not ready_to_read:
                    continue
                data = self.sock.recv(4096).decode()
                if data == "":
                    raise Exception("Connection is closed")
            except Exception as e:
                logger.error(f"Failed to read data from {self.host}:{self.port}, {e}")
                self.alive = False
                time.sleep(self.reconnect_timeout)
                self._launch()
                continue

            if not data:
                continue

            buffer += data

            # process line by line and keep the last line if it is not complete
            lines = buffer.split("\n")
            if len(lines) == 0:
                continue

            if lines[-1] != "":
                buffer = lines[-1]
            else:
                buffer = ""

            lines = lines[:-1]
            for line in lines:
                try:
                    data = loads(line)
                    yield PluginInStream(
                        session_id=data["session_id"],
                        event=PluginInStream.Event.value_of(data["event"]),
                        data=data["data"],
                        writer=self,
                    )
                except Exception:
                    logger.error(f"An error occurred while parsing the data: {line}")