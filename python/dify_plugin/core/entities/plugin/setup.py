import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.entities import I18nObject


@docs(
    description="Architecture of plugin",
)
class PluginArch(Enum):
    AMD64 = "amd64"
    ARM64 = "arm64"


@docs(
    description="Programming language of plugin",
)
class PluginLanguage(Enum):
    PYTHON = "python"


@docs(
    description="Type of plugin",
)
class PluginType(Enum):
    Plugin = "plugin"


@docs(
    description="Resource requirements of plugin",
)
class PluginResourceRequirements(BaseModel):
    memory: int

    @docs(
        description="Permission of plugin",
    )
    class Permission(BaseModel):
        @docs(
            description="Permission of tool",
        )
        class Tool(BaseModel):
            enabled: Optional[bool] = Field(default=False)

        @docs(
            description="Permission of model",
        )
        class Model(BaseModel):
            enabled: Optional[bool] = Field(default=False, description="Whether to enable invocation of model")
            llm: Optional[bool] = Field(default=False, description="Whether to enable invocation of llm")
            text_embedding: Optional[bool] = Field(
                default=False, description="Whether to enable invocation of text embedding"
            )
            rerank: Optional[bool] = Field(default=False, description="Whether to enable invocation of rerank")
            tts: Optional[bool] = Field(default=False, description="Whether to enable invocation of tts")
            speech2text: Optional[bool] = Field(
                default=False, description="Whether to enable invocation of speech2text"
            )
            moderation: Optional[bool] = Field(default=False, description="Whether to enable invocation of moderation")

        @docs(
            description="Permission of node",
        )
        class Node(BaseModel):
            enabled: Optional[bool] = Field(default=False, description="Whether to enable invocation of node")

        @docs(
            description="Permission of endpoint",
        )
        class Endpoint(BaseModel):
            enabled: Optional[bool] = Field(default=False, description="Whether to enable registration of endpoint")

        @docs(
            description="Permission of app",
        )
        class App(BaseModel):
            enabled: Optional[bool] = Field(default=False, description="Whether to enable invocation of app")

        @docs(
            description="Permission of storage",
        )
        class Storage(BaseModel):
            enabled: Optional[bool] = Field(default=False, description="Whether to enable uses of storage")
            size: int = Field(ge=1024, le=1073741824, default=1048576, description="Size of storage")

        tool: Optional[Tool] = Field(default=None, description="Permission of tool")
        model: Optional[Model] = Field(default=None, description="Permission of model")
        node: Optional[Node] = Field(default=None, description="Permission of node")
        endpoint: Optional[Endpoint] = Field(default=None, description="Permission of endpoint")
        app: Optional[App] = Field(default=None, description="Permission of app")
        storage: Optional[Storage] = Field(default=None, description="Permission of storage")

    permission: Optional[Permission] = Field(default=None, description="Permission of plugin")


@docs(
    name="Manifest",
    description="The Manifest of the plugin",
    top=True,
)
class PluginConfiguration(BaseModel):
    @docs(
        description="Extensions of plugin",
    )
    class Plugins(BaseModel):
        tools: list[str] = Field(
            default_factory=list,
            description="manifest paths of tool providers in yaml format, refers to [ToolProvider](#toolprovider)",
        )
        models: list[str] = Field(
            default_factory=list,
            description="manifest paths of model providers in yaml format, refers to [ModelProvider](#modelprovider)",
        )
        endpoints: list[str] = Field(
            default_factory=list,
            description="manifest paths of endpoint groups in yaml format, refers to [EndpointGroup](#endpointgroup)",
        )
        agent_strategies: list[str] = Field(
            default_factory=list,
            description="manifest paths of agent strategy providers in yaml format,"
            "refers to [AgentStrategyProvider](#agentstrategyprovider)",
        )

    @docs(
        description="Meta information of plugin",
    )
    class Meta(BaseModel):
        @docs(
            description="Runner of plugin",
        )
        class PluginRunner(BaseModel):
            language: PluginLanguage
            version: str
            entrypoint: str

        version: str
        arch: list[PluginArch]
        runner: PluginRunner
        minimum_dify_version: Optional[str] = Field(None, pattern=r"^\d{1,4}(\.\d{1,4}){1,3}(-\w{1,16})?$")

    version: str = Field(..., pattern=r"^\d{1,4}(\.\d{1,4}){1,3}(-\w{1,16})?$")
    type: PluginType
    author: Optional[str] = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(..., pattern=r"^[a-z0-9_-]{1,128}$")
    repo: Optional[str] = Field(None, description="The repository URL of the plugin")
    description: I18nObject
    icon: str
    label: I18nObject
    created_at: datetime.datetime
    resource: PluginResourceRequirements
    plugins: Plugins
    meta: Meta


@docs(
    description="Type of plugin provider",
)
class PluginProviderType(Enum):
    Tool = "tool"
    Model = "model"
    Endpoint = "endpoint"


class PluginAsset(BaseModel):
    filename: str
    data: bytes
