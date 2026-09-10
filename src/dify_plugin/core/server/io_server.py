import contextlib
import logging
import os
import time
import traceback
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from threading import Thread

from dify_plugin.config.config import DifyPluginEnv
from dify_plugin.core.cancellation import (
    CancellationRegistry,
    RequestCancelledError,
    _Entry,
    run_cancellable,
)
from dify_plugin.core.entities.plugin.io import PluginInStream, PluginInStreamEvent
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.serverless.request_reader import ServerlessRequestReader
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter
from dify_plugin.errors.model import InvokeError

logger = logging.getLogger(__name__)


class IOServer(ABC):
    request_reader: RequestReader

    def __init__(
        self,
        config: DifyPluginEnv,
        request_reader: RequestReader,
        default_writer: ResponseWriter | None,
    ) -> None:
        self.config = config
        self.default_writer = default_writer
        self.executer = ThreadPoolExecutor(max_workers=self.config.MAX_WORKER)
        self.request_reader = request_reader
        self.cancellations = CancellationRegistry()

    def close(self, *args: object) -> None:
        del args
        self.request_reader.close()
        self.cancellations.clear()

    @abstractmethod
    def _execute_request(
        self,
        session_id: str,
        data: dict,
        reader: RequestReader,
        writer: ResponseWriter,
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: dict | None = None,
    ) -> None:
        """
        accept requests and execute them, should be implemented outside
        """

    def _setup_instruction_listener(self) -> None:
        """
        start listen to stdin and dispatch task to executor
        """

        def filter(data: PluginInStream) -> bool:  # ruff:ignore[builtin-variable-shadowing]
            return data.event in {
                PluginInStreamEvent.Request,
                PluginInStreamEvent.Cancel,
            }

        # Requests and cancels share one reader so they stay in wire order: a cancel can
        # never overtake the request it names into the registry.
        for data in self.request_reader.read(filter).read():
            if data.event == PluginInStreamEvent.Cancel:
                self.cancellations.cancel(data.session_id)
                continue

            entry = self.cancellations.register(data.session_id)
            try:
                self.executer.submit(
                    self._execute_request_in_thread,
                    entry,
                    data.session_id,
                    data.data,
                    data.reader,
                    data.writer,
                    data.conversation_id,
                    data.message_id,
                    data.app_id,
                    data.endpoint_id,
                    data.context,
                )
            except BaseException:
                self.cancellations.discard(entry)
                raise

    def _execute_request_in_thread(
        self,
        entry: "_Entry | None",
        session_id: str,
        data: dict,
        reader: RequestReader,
        writer: ResponseWriter,
        conversation_id: str | None = None,
        message_id: str | None = None,
        app_id: str | None = None,
        endpoint_id: str | None = None,
        context: dict | None = None,
    ) -> None:
        """
        wrapper for _execute_request
        """
        # wait for the task to finish
        try:
            run_cancellable(
                entry,
                self._execute_request,
                session_id,
                data,
                reader,
                writer,
                conversation_id,
                message_id,
                app_id,
                endpoint_id,
                context,
            )
        except Exception as e:
            self._write_request_error(session_id, reader, writer, e)
        except BaseException as e:
            # A greenlet kill and a gevent.Timeout are not Exceptions. Without this
            # arm they escape into a Future nobody reads, so the caller sees neither an
            # error nor an end frame and waits out its whole execution timeout instead.
            self._write_request_error(session_id, reader, writer, e)
            raise
        finally:
            # Settle before the closing frames so a late cancel cannot reach them.
            self.cancellations.discard(entry)
            writer.session_message(
                session_id=session_id, data=writer.stream_end_object()
            )
            writer.done()

    def _write_request_error(
        self,
        session_id: str,
        reader: RequestReader,
        writer: ResponseWriter,
        e: BaseException,
    ) -> None:
        """
        report a failed request to the caller as one error frame
        """
        args: dict[str, str] = {"traceback": traceback.format_exc()}
        if isinstance(e, InvokeError):
            args["description"] = e.description

        if isinstance(e, RequestCancelledError):
            # An expected control event, not a failure worth a traceback.
            logger.debug("Request %s was cancelled by the caller", session_id)
        elif isinstance(reader, (TCPReaderWriter, ServerlessRequestReader)):
            logger.error(
                "Unexpected error occurred when executing request",
                exc_info=e,
            )

        writer.session_message(
            session_id=session_id,
            data=writer.stream_error_object(
                data={
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "args": args,
                }
            ),
        )

    def _heartbeat(self) -> None:
        """
        send heartbeat to stdout
        """
        if self.default_writer is None:
            msg = "Default writer is required for heartbeat"
            raise RuntimeError(msg)

        while True:
            # timer
            with contextlib.suppress(Exception):
                self.default_writer.heartbeat()
            time.sleep(self.config.HEARTBEAT_INTERVAL)

    def _parent_alive_check(self) -> None:
        """
        check if the parent process is alive
        """
        while True:
            time.sleep(0.5)
            parent_process_id = os.getppid()
            if parent_process_id == 1:
                os._exit(-1)

    def _run(self) -> None:
        th1 = Thread(target=self._setup_instruction_listener)
        th2 = Thread(target=self.request_reader.event_loop)
        th3 = None

        if self.default_writer:
            th3 = Thread(target=self._heartbeat)

        if isinstance(self.request_reader, StdioRequestReader):
            Thread(target=self._parent_alive_check).start()

        th1.start()
        th2.start()

        if th3 is not None:
            th3.start()

        th1.join()
        th2.join()

        if th3 is not None:
            th3.join()

    def run(self) -> None:
        """
        start plugin server
        """
        self._run()
