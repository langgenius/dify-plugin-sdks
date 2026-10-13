import logging
import os
import pathlib
import select
import shutil
import signal
import subprocess  # ruff:ignore[suspicious-subprocess-import]
import tempfile
import threading
import time
import uuid
from collections.abc import Generator
from queue import Queue
from threading import Lock, Semaphore
from types import TracebackType
from typing import Self, TypeVar

from pydantic import BaseModel, ValidationError

from dify_plugin.config.integration_config import IntegrationConfig
from dify_plugin.core.entities.plugin.request import (
    PluginAccessAction,
    PluginInvokeType,
)
from dify_plugin.integration.entities import (
    PluginGenericResponse,
    PluginInvokeRequest,
    ResponseType,
)
from dify_plugin.integration.exc import PluginStoppedError

T = TypeVar("T")

logger = logging.getLogger(__name__)


class PluginRunner:
    """A class that runs a plugin locally.

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

    def __init__(
        self,
        config: IntegrationConfig,
        plugin_package_path: str,
        extra_args: list[str] | None = None,
    ) -> None:
        self.config = config
        self.plugin_package_path = plugin_package_path
        self.extra_args = extra_args or []
        self.resources_need_to_be_cleaned: list[str] = []
        self.stdout_pipe_read = self.stdout_pipe_write = -1
        self.stderr_pipe_read = self.stderr_pipe_write = -1
        self.stdin_pipe_read = self.stdin_pipe_write = -1
        self.stdin_write_lock = Lock()
        self.stop_flag = False
        self.stop_flag_lock = Lock()
        self.q: dict[str, Queue[PluginGenericResponse | Exception | None]] = {}
        self.q_lock = Lock()
        self.ready_semaphore = Semaphore(0)
        self._close_complete = threading.Event()
        self.process: subprocess.Popen[bytes] | None = None
        self.stdout_reader: threading.Thread | None = None
        self._stderr_reader: threading.Thread | None = None
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._reader_error: Exception | None = None

        # Every startup failure must release the process and temporary package.
        try:  # ruff:ignore[too-many-statements-in-try-clause]
            self.stdout_pipe_read, self.stdout_pipe_write = os.pipe()
            self.stderr_pipe_read, self.stderr_pipe_write = os.pipe()
            self.stdin_pipe_read, self.stdin_pipe_write = os.pipe()
            logger.info("Running plugin from %s", plugin_package_path)
            if pathlib.Path(plugin_package_path).is_dir():
                logger.info("plugin source directory detected, building plugin")
                self._temporary_directory = tempfile.TemporaryDirectory()
                self.resources_need_to_be_cleaned.append(self._temporary_directory.name)
                output_path = str(
                    pathlib.Path(self._temporary_directory.name) / "plugin.difypkg"
                )
                self._build_plugin(plugin_package_path, output_path)
                self.plugin_package_path = output_path
                logger.info("Plugin built in %s", self.plugin_package_path)

            self.process = subprocess.Popen(  # ruff:ignore[subprocess-without-shell-equals-true]
                [
                    self.config.dify_cli_path,
                    "plugin",
                    "run",
                    self.plugin_package_path,
                    "--response-format",
                    "json",
                    *self.extra_args,
                ],
                stdin=self.stdin_pipe_read,
                stdout=self.stdout_pipe_write,
                stderr=self.stderr_pipe_write,
            )
            logger.info("Plugin process created with pid %s", self.process.pid)
            self.stdout_reader = threading.Thread(
                target=self._message_reader, args=(self.stdout_pipe_read,)
            )
            self._stderr_reader = threading.Thread(target=self._drain_stderr)
            self.stdout_reader.start()
            self._stderr_reader.start()

            if not self.ready_semaphore.acquire(timeout=30):
                msg = "Plugin failed to start within 30 seconds"
                raise TimeoutError(msg)
            logger.info("Plugin ready")
        except BaseException:
            self._close()
            raise

    def _build_plugin(self, package_path: str, output_path: str) -> None:
        # build plugin
        output = subprocess.check_output(  # ruff:ignore[subprocess-without-shell-equals-true]
            [
                self.config.dify_cli_path,
                "plugin",
                "package",
                package_path,
                "-o",
                output_path,
            ],
        )
        logger.info(output.decode("utf-8"))

    def _close(self) -> None:
        with self.stop_flag_lock, self.q_lock:
            first_close = not self.stop_flag
            self.stop_flag = True
            if first_close:
                for queue in self.q.values():
                    queue.put(self._reader_error or PluginStoppedError())

        if not first_close:
            # The owner may be joining this reader while it finishes.
            if threading.current_thread() in {self.stdout_reader, self._stderr_reader}:
                return
            self._close_complete.wait()
            return

        try:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.send_signal(signal.SIGTERM)
                self.process.wait()

            for thread in (self.stdout_reader, self._stderr_reader):
                if (
                    thread is not None
                    and thread.ident is not None
                    and thread is not threading.current_thread()
                ):
                    thread.join()

            for pipe in (
                self.stdout_pipe_read,
                self.stdout_pipe_write,
                self.stderr_pipe_read,
                self.stderr_pipe_write,
                self.stdin_pipe_read,
                self.stdin_pipe_write,
            ):
                if pipe != -1:
                    os.close(pipe)
            for resource in self.resources_need_to_be_cleaned:
                shutil.rmtree(resource)
            if self._temporary_directory is not None:
                self._temporary_directory.cleanup()
        finally:
            self._close_complete.set()

    def _read_async(self, fd: int) -> bytes:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if not ready:
            if self.process is not None and self.process.poll() is not None:
                raise PluginStoppedError
            return b""
        data = os.read(fd, 65536)
        if not data:
            raise PluginStoppedError
        return data

    def _drain_stderr(self) -> None:
        try:
            while True:
                # Keep CLI logs outside subclass stdout parsing hooks.
                PluginRunner._read_async(self, self.stderr_pipe_read)
        except (PluginStoppedError, OSError):
            return

    def _message_reader(self, pipe: int) -> None:
        buffer = b""
        try:  # ruff:ignore[too-many-statements-in-try-clause]
            while True:
                data = self._read_async(pipe)
                if not data:
                    time.sleep(0.01)
                    continue
                lines = (buffer + data).split(b"\n")
                buffer = lines.pop()
                for raw_line in lines:
                    line = raw_line.strip()
                    if line:
                        self._publish_message(line.decode("utf-8"))
        except PluginStoppedError:
            pass
        except Exception as error:
            self._reader_error = error
        finally:
            self._close()

    def _publish_message(self, message: str) -> None:
        # parse the message
        try:
            parsed_message = PluginGenericResponse.model_validate_json(message)
        except ValidationError:
            logger.warning("Failed to parse message: %s", message)
            return

        if not parsed_message.invoke_id:
            if parsed_message.type == ResponseType.PLUGIN_READY:
                logger.info("Plugin is ready")
                self.ready_semaphore.release()
            elif parsed_message.type == ResponseType.ERROR:
                logger.error("Plugin error: %s", parsed_message.response)
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

    def _write_to_pipe(self, data: bytes) -> None:
        with self.stdin_write_lock:
            remaining = memoryview(data)
            while remaining:
                written = os.write(self.stdin_pipe_write, remaining[:4096])
                remaining = remaining[written:]

    def invoke(
        self,
        access_type: PluginInvokeType,
        access_action: PluginAccessAction,
        payload: BaseModel,
        response_type: type[R],
    ) -> Generator[R, None, None]:
        with self.stop_flag_lock:
            if self.stop_flag:
                raise PluginStoppedError

        invoke_id = uuid.uuid4().hex
        request = PluginInvokeRequest(
            invoke_id=invoke_id,
            type=access_type,
            action=access_action,
            request=payload,
        )

        q = Queue[PluginGenericResponse | Exception | None]()
        with self.q_lock:
            if self.stop_flag:
                raise PluginStoppedError
            self.q[invoke_id] = q

        try:
            # send invoke request to the plugin
            self._write_to_pipe(request.model_dump_json().encode("utf-8") + b"\n")

            # wait for events
            while (message := q.get()) is not None:
                if isinstance(message, Exception):
                    raise message
                if message.invoke_id == invoke_id:
                    if message.type == ResponseType.PLUGIN_RESPONSE:
                        yield response_type.model_validate(message.response)
                    elif message.type == ResponseType.ERROR:
                        raise ValueError(message.response)
                    else:
                        msg = "Invalid response type"
                        raise ValueError(msg)
                else:
                    msg = "Invalid invoke id"
                    raise ValueError(msg)
        finally:
            with self.q_lock:
                self.q.pop(invoke_id, None)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._close()
