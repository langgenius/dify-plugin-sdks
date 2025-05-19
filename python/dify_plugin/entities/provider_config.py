from enum import Enum
from typing import Optional, Union

from pydantic import BaseModel, Field

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.entities import I18nObject


class LogMetadata(str, Enum):
    STARTED_AT = "started_at"
    FINISHED_AT = "finished_at"
    ELAPSED_TIME = "elapsed_time"
    TOTAL_PRICE = "total_price"
    TOTAL_TOKENS = "total_tokens"
    PROVIDER = "provider"
    CURRENCY = "currency"


@docs(
    description="The type of the parameter",
)
class CommonParameterType(Enum):
    SECRET_INPUT = "secret-input"
    TEXT_INPUT = "text-input"
    SELECT = "select"
    STRING = "string"
    NUMBER = "number"
    FILE = "file"
    FILES = "files"
    BOOLEAN = "boolean"
    APP_SELECTOR = "app-selector"
    MODEL_SELECTOR = "model-selector"
    # TOOL_SELECTOR = "tool-selector"
    TOOLS_SELECTOR = "array[tools]"
    ANY = "any"


@docs(
    description="The scope of the app selector",
)
class AppSelectorScope(Enum):
    ALL = "all"
    CHAT = "chat"
    WORKFLOW = "workflow"
    COMPLETION = "completion"


@docs(
    description="The scope of the model config",
)
class ModelConfigScope(Enum):
    LLM = "llm"
    TEXT_EMBEDDING = "text-embedding"
    RERANK = "rerank"
    TTS = "tts"
    SPEECH2TEXT = "speech2text"
    MODERATION = "moderation"
    VISION = "vision"


@docs(
    description="The scope of the tool selector",
)
class ToolSelectorScope(Enum):
    ALL = "all"
    PLUGIN = "plugin"
    API = "api"
    WORKFLOW = "workflow"


@docs(
    description="The option of the credentials",
)
class ConfigOption(BaseModel):
    value: str = Field(..., description="The value of the option")
    label: I18nObject = Field(..., description="The label of the option")


@docs(
    description="A common config schema",
)
class ProviderConfig(BaseModel):
    class Config(Enum):
        SECRET_INPUT = CommonParameterType.SECRET_INPUT.value
        TEXT_INPUT = CommonParameterType.TEXT_INPUT.value
        SELECT = CommonParameterType.SELECT.value
        BOOLEAN = CommonParameterType.BOOLEAN.value
        MODEL_SELECTOR = CommonParameterType.MODEL_SELECTOR.value
        APP_SELECTOR = CommonParameterType.APP_SELECTOR.value
        # TOOL_SELECTOR = CommonParameterType.TOOL_SELECTOR.value
        TOOLS_SELECTOR = CommonParameterType.TOOLS_SELECTOR.value

        @classmethod
        def value_of(cls, value: str) -> "ProviderConfig.Config":
            """
            Get value of given mode.

            :param value: mode value
            :return: mode
            """
            for mode in cls:
                if mode.value == value:
                    return mode
            raise ValueError(f"invalid mode value {value}")

    name: str = Field(..., description="The name of the credentials")
    type: Config = Field(..., description="The type of the credentials")
    scope: str | None = None
    required: bool = False
    default: Optional[Union[int, float, str]] = None
    options: Optional[list[ConfigOption]] = None
    label: I18nObject
    help: Optional[I18nObject] = None
    url: Optional[str] = None
    placeholder: Optional[I18nObject] = None
