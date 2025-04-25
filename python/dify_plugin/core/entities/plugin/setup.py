import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from dify_plugin.entities import I18nObject


class PluginArch(Enum):
    AMD64 = "amd64"
    ARM64 = "arm64"


class PluginLanguage(Enum):
    PYTHON = "python"


class PluginType(Enum):
    Plugin = "plugin"


class PluginResourceRequirements(BaseModel):
    memory: int

    class Permission(BaseModel):
        class Tool(BaseModel):
            enabled: Optional[bool] = Field(default=False)

        class Model(BaseModel):
            enabled: Optional[bool] = Field(default=False)
            llm: Optional[bool] = Field(default=False)
            text_embedding: Optional[bool] = Field(default=False)
            rerank: Optional[bool] = Field(default=False)
            tts: Optional[bool] = Field(default=False)
            speech2text: Optional[bool] = Field(default=False)
            moderation: Optional[bool] = Field(default=False)

        class Node(BaseModel):
            enabled: Optional[bool] = Field(default=False)

        class Endpoint(BaseModel):
            enabled: Optional[bool] = Field(default=False)

        class App(BaseModel):
            enabled: Optional[bool] = Field(default=False)

        class Storage(BaseModel):
            enabled: Optional[bool] = Field(default=False)
            size: int = Field(ge=1024, le=1073741824, default=1048576)

        tool: Optional[Tool] = Field(default=None)
        model: Optional[Model] = Field(default=None)
        node: Optional[Node] = Field(default=None)
        endpoint: Optional[Endpoint] = Field(default=None)
        app: Optional[App] = Field(default=None)
        storage: Optional[Storage] = Field(default=None)

    permission: Optional[Permission] = Field(default=None)


class PluginConfiguration(BaseModel):
    class Plugins(BaseModel):
        tools: list[str] = Field(default_factory=list)
        models: list[str] = Field(default_factory=list)
        endpoints: list[str] = Field(default_factory=list)
        agent_strategies: list[str] = Field(default_factory=list)

    class Meta(BaseModel):
        class PluginRunner(BaseModel):
            language: PluginLanguage
            version: str
            entrypoint: str

        version: str
        arch: list[PluginArch]
        runner: PluginRunner
        minimum_dify_version: Optional[str] = Field(..., pattern=r"^\d{1,4}(\.\d{1,4}){1,3}(-\w{1,16})?$")

    version: str = Field(..., pattern=r"^\d{1,4}(\.\d{1,4}){1,3}(-\w{1,16})?$")
    type: PluginType
    author: Optional[str] = Field(..., pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    name: str = Field(..., pattern=r"^[a-z0-9_-]{1,128}$")
    description: I18nObject
    icon: str
    label: I18nObject
    created_at: datetime.datetime
    resource: PluginResourceRequirements
    plugins: Plugins
    meta: Meta


class PluginProviderType(Enum):
    Tool = "tool"
    Model = "model"
    Endpoint = "endpoint"


class PluginAsset(BaseModel):
    filename: str
    data: bytes
