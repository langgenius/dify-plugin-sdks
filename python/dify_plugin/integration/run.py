import logging
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Generator
from queue import Queue
from threading import Lock, Semaphore
from typing import TypeVar

from gevent.os import tp_read
from pydantic import BaseModel, ValidationError

from dify_plugin.config.integration_config import IntegrationConfig
from dify_plugin.core.entities.plugin.request import (
    PluginAccessAction,
    PluginInvokeType,
)
from dify_plugin.integration.entities import PluginGenericResponse, PluginInvokeRequest, ResponseType
from dify_plugin.integration.exc import PluginStoppedError

T = TypeVar("T")

logger = logging.getLogger(__name__)


class PluginRunner:
    """
    A class that runs a plugin locally.

    Usage:
    ```python
    with PluginRunner(
        config=IntegrationConfig(),
        plugin_package_path="./langgenius-agent_0.0.14.difypkg",
    ) as runner:
        for result in runner.invoke(
            PluginInvokeType.Agent,
            AgentActions.InvokeAgentStrategy,
            payload=request.AgentInvokeRequest(
                user_id="hello",
                agent_strategy_provider="agent",
                agent_strategy="function_calling",
                agent_strategy_params=agent_strategy_params,
            ),
            response_type=AgentInvokeMessage,
        ):
            assert result
    ```
    """

    R = TypeVar("R", bound=BaseModel)

    def __init__(self, config: IntegrationConfig, plugin_package_path: str, extra_args: list[str] | None = None):
        self.config = config
        self.plugin_package_path = plugin_package_path
        self.extra_args = extra_args or []
        self.resources_need_to_be_cleaned = []

        # create pipe to communicate with the plugin
        self.stdout_pipe_read, self.stdout_pipe_write = os.pipe()
        self.stderr_pipe_read, self.stderr_pipe_write = os.pipe()
        self.stdin_pipe_read, self.stdin_pipe_write = os.pipe()

        # stdin write lock
        self.stdin_write_lock = Lock()

        # setup stop flag
        self.stop_flag = False
        self.stop_flag_lock = Lock()

        logger.info(f"Running plugin from {plugin_package_path}")

        # check if plugin is a directory
        if os.path.isdir(plugin_package_path):
            logger.info("plugin source directory detected, building plugin")
            with tempfile.TemporaryDirectory(delete=False) as temp_dir:
                output_path = os.path.join(temp_dir, "plugin.difypkg")
                self._build_plugin(plugin_package_path, output_path)
                self.plugin_package_path = output_path
                logger.info(f"Plugin built in {self.plugin_package_path}")
                self.resources_need_to_be_cleaned.append(temp_dir)

        self.process = subprocess.Popen(  # noqa: S603
            [
                self.config.dify_cli_path,
                "plugin",
                "run",
                self.plugin_package_path,
                "--response-format",
                "json",
                *self.extra_args,
            ],
            stdout=self.stdout_pipe_write,
            stderr=self.stderr_pipe_write,
            stdin=self.stdin_pipe_read,
        )

        logger.info(f"Plugin process created with pid {self.process.pid}")

        # wait for plugin to be ready
        self.ready_semaphore = Semaphore(0)

        # create a thread to read the stdout and stderr
        self.stdout_reader = threading.Thread(target=self._message_reader, args=(self.stdout_pipe_read,))
        try:
            self.stdout_reader.start()
        except Exception as e:
            raise e

        self.q = dict[str, Queue[PluginGenericResponse | None]]()
        self.q_lock = Lock()

        # wait for the plugin to be ready
        self.ready_semaphore.acquire()

        logger.info("Plugin ready")

    def _build_plugin(self, package_path: str, output_path: str):
        # build plugin
        output = subprocess.check_output(  # noqa: S603
            [self.config.dify_cli_path, "plugin", "package", package_path, "-o", output_path],
        )
        logger.info(output.decode("utf-8"))

    def _close(self):
        with self.stop_flag_lock:
            if self.stop_flag:
                return

            # stop the plugin
            self.stop_flag = True

        # send signal SIGTERM to the plugin, so it can exit gracefully
        # do collect garbage like removing temporary files
        os.kill(self.process.pid, signal.SIGTERM)

        # wait for the plugin to exit
        self.process.wait()

        # close the pipes
        os.close(self.stdout_pipe_write)
        os.close(self.stderr_pipe_write)
        os.close(self.stdin_pipe_read)

    def _read_async(self, fd: int) -> bytes:
        # read data from stdin using tp_read in 64KB chunks.
        # the OS buffer for stdin is usually 64KB, so using a larger value doesn't make sense.
        b = tp_read(fd, 65536)
        if not b:
            raise PluginStoppedError()
        return b

    def _message_reader(self, pipe: int):
        # create a scanner to read the message line by line
        """Read messages line by line from the pipe."""
        buffer = b""
        try:
            while True:
                try:
                    data = self._read_async(pipe)
                except PluginStoppedError:
                    break

                if not data:
                    continue

                buffer += data

                # if no b"\n" is in data, skip to the next iteration
                if data.find(b"\n") == -1:
                    continue

                # process line by line and keep the last line if it is not complete
                lines = buffer.split(b"\n")
                buffer = lines[-1]

                lines = lines[:-1]
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    self._publish_message(line.decode("utf-8"))
        finally:
            self._close()

    def _publish_message(self, message: str):
        # parse the message
        try:
            parsed_message = PluginGenericResponse.model_validate_json(message)
        except ValidationError:
            return

        if not parsed_message.invoke_id:
            if parsed_message.type == ResponseType.PLUGIN_READY:
                self.ready_semaphore.release()
            elif parsed_message.type == ResponseType.ERROR:
                raise ValueError(parsed_message.response)
            elif parsed_message.type == ResponseType.INFO:
                logger.info(parsed_message.response)
            return

        with self.q_lock:
            if parsed_message.invoke_id not in self.q:
                return
            if parsed_message.type == ResponseType.PLUGIN_INVOKE_END:
                self.q[parsed_message.invoke_id].put(None)
            else:
                self.q[parsed_message.invoke_id].put(parsed_message)

    def _write_to_pipe(self, data: bytes):
        # split the data into chunks of 4096 bytes
        chunks = [data[i : i + 4096] for i in range(0, len(data), 4096)]
        with (
            self.stdin_write_lock
        ):  # a lock is needed to avoid race condition when facing multiple threads writing to the pipe.
            for chunk in chunks:
                os.write(self.stdin_pipe_write, chunk)

    def invoke(
        self,
        access_type: PluginInvokeType,
        access_action: PluginAccessAction,
        payload: BaseModel,
        response_type: type[R],
    ) -> Generator[R, None, None]:
        with self.stop_flag_lock:
            if self.stop_flag:
                raise PluginStoppedError()

        invoke_id = uuid.uuid4().hex
        request = PluginInvokeRequest(
            invoke_id=invoke_id,
            type=access_type,
            action=access_action,
            request=payload,
        )

        q = Queue[PluginGenericResponse | None]()
        with self.q_lock:
            self.q[invoke_id] = q

        try:
            # send invoke request to the plugin
            self._write_to_pipe(request.model_dump_json().encode("utf-8") + b"\n")

            # wait for events
            while message := q.get():
                if message.invoke_id == invoke_id:
                    if message.type == ResponseType.PLUGIN_RESPONSE:
                        yield response_type.model_validate(message.response)
                    elif message.type == ResponseType.ERROR:
                        raise ValueError(message.response)
                    else:
                        raise ValueError("Invalid response type")
                else:
                    raise ValueError("Invalid invoke id")
        finally:
            with self.q_lock:
                del self.q[invoke_id]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._close()

        for resource in self.resources_need_to_be_cleaned:
            shutil.rmtree(resource)
