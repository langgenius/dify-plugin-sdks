import base64
import logging
import uuid
from collections.abc import Generator
from typing import Any, Optional

from pydantic import RootModel
from yarl import URL

from dify_plugin.config.config import DifyPluginEnv, InstallMethod
from dify_plugin.config.logger_format import plugin_logger_handler
from dify_plugin.core.entities.message import InitializeMessage
from dify_plugin.core.entities.plugin.request import (
    AgentActions,
    EndpointActions,
    ModelActions,
    PluginInvokeType,
    ToolActions,
)
from dify_plugin.core.plugin_executor import PluginExecutor
from dify_plugin.core.plugin_registration import PluginRegistration
from dify_plugin.core.runtime import Session
from dify_plugin.core.server.__base.request_reader import RequestReader
from dify_plugin.core.server.__base.response_writer import ResponseWriter
from dify_plugin.core.server.io_server import IOServer
from dify_plugin.core.server.router import Router
from dify_plugin.core.server.serverless.request_reader import ServerlessRequestReader
from dify_plugin.core.server.stdio.request_reader import StdioRequestReader
from dify_plugin.core.server.stdio.response_writer import StdioResponseWriter
from dify_plugin.core.server.tcp.request_reader import TCPReaderWriter
from dify_plugin.entities.tool import ToolInvokeMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.addHandler(plugin_logger_handler)


class Plugin(IOServer, Router):
    def __init__(self, config: DifyPluginEnv) -> None:
        """
        Initialize plugin
        """
        # load plugin configuration
        self.registration = PluginRegistration(config)

        if InstallMethod.Local == config.INSTALL_METHOD:
            request_reader, response_writer = self._launch_local_stream(config)
        elif InstallMethod.Remote == config.INSTALL_METHOD:
            request_reader, response_writer = self._launch_remote_stream(config)
        elif InstallMethod.Serverless == config.INSTALL_METHOD:
            request_reader, response_writer = self._launch_serverless_stream(config)
        else:
            raise ValueError("Invalid install method")

        # set default response writer
        self.default_response_writer = response_writer

        # initialize plugin executor
        self.plugin_executer = PluginExecutor(config, self.registration)

        IOServer.__init__(self, config, request_reader, response_writer)
        Router.__init__(self, request_reader, response_writer)

        # register io routes
        self._register_request_routes()

    def _launch_local_stream(self, config: DifyPluginEnv) -> tuple[RequestReader, Optional[ResponseWriter]]:
        """
        Launch local stream
        """
        reader = StdioRequestReader()
        writer = StdioResponseWriter()
        writer.write(self.registration.configuration.model_dump_json() + "\n\n")

        self._log_configuration()
        return reader, writer

    def _launch_remote_stream(self, config: DifyPluginEnv) -> tuple[RequestReader, Optional[ResponseWriter]]:
        """
        Launch remote stream
        """
        if not config.REMOTE_INSTALL_KEY:
            raise ValueError("Missing remote install key")

        install_host, install_port = self._get_remote_install_host_and_port(config)
        logging.debug(f"Remote installing to {install_host}:{install_port}")

        tcp_stream = TCPReaderWriter(
            install_host,
            install_port,
            config.REMOTE_INSTALL_KEY,
            on_connected=lambda: self._initialize_tcp_stream(tcp_stream),
        )

        tcp_stream.launch()

        return tcp_stream, tcp_stream

    def _initialize_tcp_stream(
        self,
        tcp_stream: TCPReaderWriter,
    ):
        class List(RootModel):
            root: list[Any]

        tcp_stream.write(
            InitializeMessage(
                type=InitializeMessage.Type.MANIFEST_DECLARATION,
                data=self.registration.configuration.model_dump(),
            ).model_dump_json()
            + "\n\n"
        )

        if self.registration.tools_configuration:
            tcp_stream.write(
                InitializeMessage(
                    type=InitializeMessage.Type.TOOL_DECLARATION,
                    data=List(root=self.registration.tools_configuration).model_dump(),
                ).model_dump_json()
                + "\n\n"
            )

        if self.registration.models_configuration:
            tcp_stream.write(
                InitializeMessage(
                    type=InitializeMessage.Type.MODEL_DECLARATION,
                    data=List(root=self.registration.models_configuration).model_dump(),
                ).model_dump_json()
                + "\n\n"
            )

        if self.registration.endpoints_configuration:
            tcp_stream.write(
                InitializeMessage(
                    type=InitializeMessage.Type.ENDPOINT_DECLARATION,
                    data=List(root=self.registration.endpoints_configuration).model_dump(),
                ).model_dump_json()
                + "\n\n"
            )

        if self.registration.agent_strategies_configuration:
            tcp_stream.write(
                InitializeMessage(
                    type=InitializeMessage.Type.AGENT_STRATEGY_DECLARATION,
                    data=List(root=self.registration.agent_strategies_configuration).model_dump(),
                ).model_dump_json()
                + "\n\n"
            )

        for file in self.registration.files:
            # divide the file into chunks
            chunks = [file.data[i : i + 8192] for i in range(0, len(file.data), 8192)]
            for sequence, chunk in enumerate(chunks):
                tcp_stream.write(
                    InitializeMessage(
                        type=InitializeMessage.Type.ASSET_CHUNK,
                        data=InitializeMessage.AssetChunk(
                            filename=file.filename,
                            data=base64.b64encode(chunk).decode(),
                            end=sequence == len(chunks) - 1,
                        ).model_dump(),
                    ).model_dump_json()
                    + "\n\n"
                )

        tcp_stream.write(
            InitializeMessage(
                type=InitializeMessage.Type.END,
                data={},
            ).model_dump_json()
            + "\n\n"
        )

        self._log_configuration()

    def _launch_serverless_stream(self, config: DifyPluginEnv) -> tuple[RequestReader, Optional[ResponseWriter]]:
        """
        Launch Serverless stream
        """
        serverless = ServerlessRequestReader(
            config.SERVERLESS_HOST,
            config.SERVERLESS_PORT,
            config.SERVERLESS_WORKER_CLASS,
            config.SERVERLESS_WORKERS,
            config.SERVERLESS_THREADS,
            config.MAX_REQUEST_TIMEOUT,
        )
        serverless.launch()

        return serverless, None

    def _log_configuration(self):
        """
        Log plugin configuration
        """
        for tool in self.registration.tools_configuration:
            logger.info(f"Installed tool: {tool.identity.name}")
        for model in self.registration.models_configuration:
            logger.info(f"Installed model: {model.provider}")
        for endpoint in self.registration.endpoints_configuration:
            logger.info(f"Installed endpoint: {[e.path for e in endpoint.endpoints]}")
        for agent in self.registration.agent_strategies_configuration:
            logger.info(f"Installed agent: {agent.identity.name}")

    def _register_request_routes(self):
        """
        Register routes
        """
        self.register_route(
            self.plugin_executer.invoke_tool,
            lambda data: data.get("type") == PluginInvokeType.Tool.value
            and data.get("action") == ToolActions.InvokeTool.value,
        )

        self.register_route(
            self.plugin_executer.validate_tool_provider_credentials,
            lambda data: data.get("type") == PluginInvokeType.Tool.value
            and data.get("action") == ToolActions.ValidateCredentials.value,
        )

        self.register_route(
            self.plugin_executer.invoke_agent_strategy,
            lambda data: data.get("type") == PluginInvokeType.Agent.value
            and data.get("action") == AgentActions.InvokeAgentStrategy.value,
        )

        self.register_route(
            self.plugin_executer.invoke_llm,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.InvokeLLM.value,
        )

        self.register_route(
            self.plugin_executer.get_llm_num_tokens,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.GetLLMNumTokens.value,
        )

        self.register_route(
            self.plugin_executer.invoke_text_embedding,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.InvokeTextEmbedding.value,
        )

        self.register_route(
            self.plugin_executer.get_text_embedding_num_tokens,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.GetTextEmbeddingNumTokens.value,
        )

        self.register_route(
            self.plugin_executer.invoke_rerank,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.InvokeRerank.value,
        )

        self.register_route(
            self.plugin_executer.invoke_tts,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.InvokeTTS.value,
        )

        self.register_route(
            self.plugin_executer.get_tts_model_voices,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.GetTTSVoices.value,
        )

        self.register_route(
            self.plugin_executer.invoke_speech_to_text,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.InvokeSpeech2Text.value,
        )

        self.register_route(
            self.plugin_executer.invoke_moderation,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.InvokeModeration.value,
        )

        self.register_route(
            self.plugin_executer.validate_model_provider_credentials,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.ValidateProviderCredentials.value,
        )

        self.register_route(
            self.plugin_executer.validate_model_credentials,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.ValidateModelCredentials.value,
        )

        self.register_route(
            self.plugin_executer.invoke_endpoint,
            lambda data: data.get("type") == PluginInvokeType.Endpoint.value
            and data.get("action") == EndpointActions.InvokeEndpoint.value,
        )

        self.register_route(
            self.plugin_executer.get_ai_model_schemas,
            lambda data: data.get("type") == PluginInvokeType.Model.value
            and data.get("action") == ModelActions.GetAIModelSchemas.value,
        )

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
        accept requests and execute
        :param session_id: session id, unique for each request
        :param data: request data
        """

        session = Session(
            session_id=session_id,
            executor=self.executer,
            reader=reader,
            writer=writer,
            install_method=self.config.INSTALL_METHOD,
            dify_plugin_daemon_url=self.config.DIFY_PLUGIN_DAEMON_URL,
            conversation_id=conversation_id,
            message_id=message_id,
            app_id=app_id,
            endpoint_id=endpoint_id,
        )
        response = self.dispatch(session, data)
        if response:
            if isinstance(response, Generator):
                for message in response:
                    if isinstance(message, ToolInvokeMessage) and isinstance(
                        message.message, ToolInvokeMessage.BlobMessage
                    ):
                        # convert blob to file chunks
                        id_ = uuid.uuid4().hex
                        blob = message.message.blob
                        message.message.blob = id_.encode("utf-8")
                        # split the blob into chunks
                        chunks = [blob[i : i + 8192] for i in range(0, len(blob), 8192)]
                        for sequence, chunk in enumerate(chunks):
                            writer.session_message(
                                session_id=session_id,
                                data=writer.stream_object(
                                    data=ToolInvokeMessage(
                                        type=ToolInvokeMessage.MessageType.BLOB_CHUNK,
                                        message=ToolInvokeMessage.BlobChunkMessage(
                                            id=id_,
                                            sequence=sequence,
                                            total_length=len(blob),
                                            blob=chunk,
                                            end=False,
                                        ),
                                        meta=message.meta,
                                    ),
                                ),
                            )

                        # end the file stream
                        writer.session_message(
                            session_id=session_id,
                            data=writer.stream_object(
                                data=ToolInvokeMessage(
                                    type=ToolInvokeMessage.MessageType.BLOB_CHUNK,
                                    message=ToolInvokeMessage.BlobChunkMessage(
                                        id=id_,
                                        sequence=len(chunks),
                                        total_length=len(blob),
                                        blob=b"",
                                        end=True,
                                    ),
                                    meta=message.meta,
                                )
                            ),
                        )
                    else:
                        writer.session_message(
                            session_id=session_id,
                            data=writer.stream_object(data=message),
                        )
            else:
                writer.session_message(
                    session_id=session_id,
                    data=writer.stream_object(data=response),
                )

    @staticmethod
    def _get_remote_install_host_and_port(config: DifyPluginEnv) -> tuple[str, int]:
        """
        Get host and port for remote installation
        :param config: Dify plugin env config
        :return: host and port
        """
        install_url = config.REMOTE_INSTALL_URL
        if install_url is not None:
            if ":" in install_url:
                url = URL(install_url)
                if url.host and url.port:
                    # for the url with protocol prefix
                    host = url.host
                    port = url.port
                else:
                    # for "host:port" format
                    split = install_url.split(":")
                    host = split[0]
                    port = int(split[1])
            else:
                raise ValueError(
                    f'Invalid remote install URL {install_url}, which should be in the format of "host:port"'
                )
        else:
            host = config.REMOTE_INSTALL_HOST
            port = config.REMOTE_INSTALL_PORT

        return host, port
