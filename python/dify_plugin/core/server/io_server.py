import contextlib
import logging
import os
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from threading import Thread
from typing import Optional

from dify_plugin.config.config import DifyPluginEnv
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
        default_writer: Optional[ResponseWriter],
    ) -> None:
        self.config = config
        self.default_writer = default_writer
        self.executer = ThreadPoolExecutor(max_workers=self.config.MAX_WORKER)
        self.request_reader = request_reader

    def close(self, *args):
        self.request_reader.close()

    @abstractmethod
    def _execute_request(
        self,
        session_id: str,
        data: dict,
        reader: RequestReader,
        writer: ResponseWriter,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        app_id: Optional[str] = None,
        endpoint_id: Optional[str] = None,
    ):
        """
        accept requests and execute them, should be implemented outside
        """

    def _setup_instruction_listener(self):
        """
        start listen to stdin and dispatch task to executor
        """

        def filter(data: PluginInStream) -> bool:  # noqa: A001
            return data.event == PluginInStreamEvent.Request

        for data in self.request_reader.read(filter).read():
            self.executer.submit(
                self._execute_request_in_thread,
                data.session_id,
                data.data,
                data.reader,
                data.writer,
                data.conversation_id,
                data.message_id,
                data.app_id,
                data.endpoint_id,
            )

    def _execute_request_in_thread(
        self,
        session_id: str,
        data: dict,
        reader: RequestReader,
        writer: ResponseWriter,
        conversation_id: Optional[str] = None,
        message_id: Optional[str] = None,
        app_id: Optional[str] = None,
        endpoint_id: Optional[str] = None,
    ):
        """
        wrapper for _execute_request
        """
        # wait for the task to finish
        try:
            self._execute_request(
                session_id,
                data,
                reader,
                writer,
                conversation_id,
                message_id,
                app_id,
                endpoint_id,
            )
        except Exception as e:
            args = {}
            if isinstance(e, InvokeError):
                args["description"] = e.description

            if isinstance(reader, (TCPReaderWriter, ServerlessRequestReader)):
                logger.exception(
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

        writer.session_message(session_id=session_id, data=writer.stream_end_object())
        writer.done()

    def _heartbeat(self):
        """
        send heartbeat to stdout
        """
        assert self.default_writer

        while True:
            # timer
            with contextlib.suppress(Exception):
                self.default_writer.heartbeat()
            time.sleep(self.config.HEARTBEAT_INTERVAL)

    def _parent_alive_check(self):
        """
        check if the parent process is alive
        """
        while True:
            time.sleep(0.5)
            parent_process_id = os.getppid()
            if parent_process_id == 1:
                os._exit(-1)

    def _run(self):
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

    def run(self):
        """
        start plugin server
        """
        self._run()
