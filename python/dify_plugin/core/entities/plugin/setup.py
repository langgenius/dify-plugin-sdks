import datetime
from enum import Enum

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, Field, field_validator

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
            enabled: bool | None = Field(default=False)

        @docs(
            description="Permission of model",
        )
        class Model(BaseModel):
            enabled: bool | None = Field(default=False, description="Whether to enable invocation of model")
            llm: bool | None = Field(default=False, description="Whether to enable invocation of llm")
            text_embedding: bool | None = Field(
                default=False, description="Whether to enable invocation of text embedding"
            )
            rerank: bool | None = Field(default=False, description="Whether to enable invocation of rerank")
            tts: bool | None = Field(default=False, description="Whether to enable invocation of tts")
            speech2text: bool | None = Field(default=False, description="Whether to enable invocation of speech2text")
            moderation: bool | None = Field(default=False, description="Whether to enable invocation of moderation")

        @docs(
            description="Permission of node",
        )
        class Node(BaseModel):
            enabled: bool | None = Field(default=False, description="Whether to enable invocation of node")

        @docs(
            description="Permission of endpoint",
        )
        class Endpoint(BaseModel):
            enabled: bool | None = Field(default=False, description="Whether to enable registration of endpoint")

        @docs(
            description="Permission of app",
        )
        class App(BaseModel):
            enabled: bool | None = Field(default=False, description="Whether to enable invocation of app")

        @docs(
            description="Permission of storage",
        )
        class Storage(BaseModel):
            enabled: bool | None = Field(default=False, description="Whether to enable uses of storage")
            size: int = Field(ge=1024, le=1073741824, default=1048576, description="Size of storage")

        tool: Tool | None = Field(default=None, description="Permission of tool")
        model: Model | None = Field(default=None, description="Permission of model")
        node: Node | None = Field(default=None, description="Permission of node")
        endpoint: Endpoint | None = Field(default=None, description="Permission of endpoint")
        app: App | None = Field(default=None, description="Permission of app")
        storage: Storage | None = Field(default=None, description="Permission of storage")

    permission: Permission | None = Field(default=None, description="Permission of plugin")


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
        datasources: list[str] = Field(
            default_factory=list,
            description="manifest paths of datasource providers in yaml format"
            " refers to [DatasourceProvider](#datasourceprovider)",
        )
        triggers: list[str] = Field(
            default_factory=list,
            description="manifest paths of trigger providers in yaml format, "
            "refers to [TriggerProvider](#triggerprovider)",
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

        version: str = Field(
            ...,
            description="The version of the manifest specification, designed for backward compatibility,"
            "when installing an older plugin to a newer Dify, it's hard to ensure breaking changes never happen,"
            " but at least, Dify can detect it by this field, it knows which version of the manifest is supported.",
        )
        arch: list[PluginArch]
        runner: PluginRunner
        minimum_dify_version: str | None = Field(
            None,
            description="The minimum version of Dify, designed for forward compatibility."
            "When installing a newer plugin to an older Dify, many new features may not be available,"
            "but showing the minimum Dify version helps users understand how to upgrade.",
        )

        @field_validator("minimum_dify_version")
        @classmethod
        def validate_minimum_dify_version(cls, v: str | None) -> str | None:
            if v is None:
                return v
            try:
                Version(v)
                return v
            except InvalidVersion as e:
                raise ValueError(f"Invalid version format: {v}") from e

    version: str = Field(...)
    type: PluginType
    author: str | None = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(..., pattern=r"^[a-z0-9_-]{1,128}$")
    repo: str | None = Field(None, description="The repository URL of the plugin")
    description: I18nObject
    icon: str
    icon_dark: str | None = Field(None, description="The dark mode icon of the plugin")
    label: I18nObject
    created_at: datetime.datetime
    resource: PluginResourceRequirements
    plugins: Plugins
    meta: Meta

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        try:
            Version(v)
            return v
        except InvalidVersion as e:
            raise ValueError(f"Invalid version format: {v}") from e


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
