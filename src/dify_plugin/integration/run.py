import logging
import pathlib
import subprocess  # ruff:ignore[suspicious-subprocess-import]
import tempfile
import threading
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
        self.stdin_write_lock = Lock()
        self.stop_flag = False
        self.q: dict[str, Queue[PluginGenericResponse | Exception | None]] = {}
        self.q_lock = Lock()
        self.ready_semaphore = Semaphore(0)
        self._close_complete = threading.Event()
        self.process: subprocess.Popen[bytes] | None = None
        self.stdout_reader: threading.Thread | None = None
        self._temporary_directory: tempfile.TemporaryDirectory[str] | None = None
        self._reader_error: Exception | None = None

        # Every startup failure must release the process and temporary package.
        try:  # ruff:ignore[too-many-statements-in-try-clause]
            if pathlib.Path(plugin_package_path).is_dir():
                self._temporary_directory = tempfile.TemporaryDirectory()
                output_path = str(
                    pathlib.Path(self._temporary_directory.name) / "plugin.difypkg"
                )
                self._build_plugin(plugin_package_path, output_path)
                self.plugin_package_path = output_path

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
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                # CLI startup errors and logs use the same JSON format on stderr.
                stderr=subprocess.STDOUT,
            )
            self.stdout_reader = threading.Thread(target=self._message_reader)
            self.stdout_reader.start()

            if not self.ready_semaphore.acquire(timeout=30):
                msg = "Plugin failed to start within 30 seconds"
                raise TimeoutError(msg)
            if self._reader_error is not None:
                raise self._reader_error
            if self.stop_flag:
                raise PluginStoppedError
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
        with self.q_lock:
            first_close = not self.stop_flag
            self.stop_flag = True
            if first_close:
                for queue in self.q.values():
                    queue.put(self._reader_error or PluginStoppedError())
                self.ready_semaphore.release()

        if not first_close:
            # The owner may be joining this reader while it finishes.
            if self.stdout_reader is threading.current_thread():
                return
            self._close_complete.wait()

        try:
            if first_close and self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)

            if (
                self.stdout_reader is not None
                and self.stdout_reader.ident is not None
                and self.stdout_reader is not threading.current_thread()
            ):
                self.stdout_reader.join(timeout=5)

            if first_close:
                if self.process is not None:
                    for pipe in (self.process.stdin, self.process.stdout):
                        if pipe is not None:
                            pipe.close()
                if self._temporary_directory is not None:
                    self._temporary_directory.cleanup()
        finally:
            if first_close:
                self._close_complete.set()

    def _message_reader(self) -> None:
        try:
            if self.process is None or self.process.stdout is None:
                raise PluginStoppedError
            for raw_line in self.process.stdout:
                line = raw_line.strip()
                if line:
                    self._publish_message(line.decode("utf-8"))
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
            if self.stop_flag or self.process is None or self.process.stdin is None:
                raise PluginStoppedError
            try:
                self.process.stdin.write(data)
                self.process.stdin.flush()
            except (BrokenPipeError, ValueError) as error:
                raise PluginStoppedError from error

    def invoke(
        self,
        access_type: PluginInvokeType,
        access_action: PluginAccessAction,
        payload: BaseModel,
        response_type: type[R],
    ) -> Generator[R, None, None]:
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
