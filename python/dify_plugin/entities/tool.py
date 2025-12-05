from collections.abc import Mapping
from enum import Enum, StrEnum
from typing import Any, Union

from pydantic import (
    BaseModel,
    Field,
    field_validator,
    model_validator,
)

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.invoke_message import InvokeMessage
from dify_plugin.entities.model.message import PromptMessageTool
from dify_plugin.entities.oauth import OAuthSchema
from dify_plugin.entities.provider_config import (
    CommonParameterType,
    CredentialType,
    ProviderConfig,
)


class ToolRuntime(BaseModel):
    credentials: dict[str, Any]
    credential_type: CredentialType = CredentialType.API_KEY
    user_id: str | None
    session_id: str | None


class ToolInvokeMessage(InvokeMessage):
    pass


@docs(
    description="The identity of the tool",
)
class ToolIdentity(BaseModel):
    author: str = Field(..., description="The author of the tool")
    name: str = Field(..., description="The name of the tool")
    label: I18nObject = Field(..., description="The label of the tool")


@docs(
    description="The option of the tool parameter",
)
class ToolParameterOption(ParameterOption):
    pass


@docs(
    description="The auto generate of the parameter",
)
class ParameterAutoGenerate(BaseModel):
    class Type(StrEnum):
        PROMPT_INSTRUCTION = "prompt_instruction"

    type: Type


@docs(
    description="The template of the parameter",
)
class ParameterTemplate(BaseModel):
    enabled: bool = Field(..., description="Whether the parameter is jinja enabled")


@docs(
    description="The type of the parameter",
)
class ToolParameter(BaseModel):
    class ToolParameterType(str, Enum):
        STRING = CommonParameterType.STRING.value
        NUMBER = CommonParameterType.NUMBER.value
        BOOLEAN = CommonParameterType.BOOLEAN.value
        SELECT = CommonParameterType.SELECT.value
        SECRET_INPUT = CommonParameterType.SECRET_INPUT.value
        FILE = CommonParameterType.FILE.value
        FILES = CommonParameterType.FILES.value
        MODEL_SELECTOR = CommonParameterType.MODEL_SELECTOR.value
        APP_SELECTOR = CommonParameterType.APP_SELECTOR.value
        CHECKBOX = CommonParameterType.CHECKBOX.value
        # TOOL_SELECTOR = CommonParameterType.TOOL_SELECTOR.value
        ANY = CommonParameterType.ANY.value
        # MCP object and array type parameters
        OBJECT = CommonParameterType.OBJECT.value
        ARRAY = CommonParameterType.ARRAY.value
        DYNAMIC_SELECT = CommonParameterType.DYNAMIC_SELECT.value

    class ToolParameterForm(Enum):
        SCHEMA = "schema"  # should be set while adding tool
        FORM = "form"  # should be set before invoking tool
        LLM = "llm"  # will be set by LLM

    name: str = Field(..., description="The name of the parameter")
    label: I18nObject = Field(..., description="The label presented to the user")
    human_description: I18nObject = Field(..., description="The description presented to the user")
    type: ToolParameterType = Field(..., description="The type of the parameter")
    auto_generate: ParameterAutoGenerate | None = Field(default=None, description="The auto generate of the parameter")
    template: ParameterTemplate | None = Field(default=None, description="The template of the parameter")
    scope: str | None = None
    form: ToolParameterForm = Field(..., description="The form of the parameter, schema/form/llm")
    llm_description: str | None = None
    required: bool | None = False
    default: Union[int, float, str] | None = None
    min: Union[float, int] | None = None
    max: Union[float, int] | None = None
    precision: int | None = None
    options: list[ToolParameterOption] | None = None
    # MCP object and array type parameters use this field to store the schema
    input_schema: Mapping[str, Any] | None = None


@docs(
    description="The description of the tool",
)
class ToolDescription(BaseModel):
    human: I18nObject = Field(..., description="The description presented to the user")
    llm: str = Field(..., description="The description presented to the LLM")


@docs(
    name="ToolExtra",
    description="The extra of the tool",
)
class ToolConfigurationExtra(BaseModel):
    class Python(BaseModel):
        source: str

    python: Python


@docs(
    name="Tool",
    description="The manifest of the tool",
)
class ToolConfiguration(BaseModel):
    identity: ToolIdentity
    parameters: list[ToolParameter] = Field(default=[], description="The parameters of the tool")
    description: ToolDescription
    extra: ToolConfigurationExtra
    has_runtime_parameters: bool = Field(default=False, description="Whether the tool has runtime parameters")
    output_schema: Mapping[str, Any] | None = None


@docs(
    description="The label of the tool",
)
class ToolLabelEnum(Enum):
    SEARCH = "search"
    IMAGE = "image"
    VIDEOS = "videos"
    WEATHER = "weather"
    FINANCE = "finance"
    DESIGN = "design"
    TRAVEL = "travel"
    SOCIAL = "social"
    NEWS = "news"
    MEDICAL = "medical"
    PRODUCTIVITY = "productivity"
    EDUCATION = "education"
    BUSINESS = "business"
    ENTERTAINMENT = "entertainment"
    UTILITIES = "utilities"
    RAG = "rag"
    OTHER = "other"


@docs(
    description="The identity of the tool provider",
)
class ToolProviderIdentity(BaseModel):
    author: str = Field(..., description="The author of the tool")
    name: str = Field(..., description="The name of the tool")
    description: I18nObject = Field(..., description="The description of the tool")
    icon: str = Field(..., description="The icon of the tool")
    icon_dark: str | None = Field(None, description="The dark mode icon of the tool")
    label: I18nObject = Field(..., description="The label of the tool")
    tags: list[ToolLabelEnum] = Field(
        default=[],
        description="The tags of the tool",
    )


@docs(
    name="ToolProviderExtra",
    description="The extra of the tool provider",
)
class ToolProviderConfigurationExtra(BaseModel):
    class Python(BaseModel):
        source: str

    python: Python


@docs(
    name="ToolProvider",
    description="The Manifest of the tool provider",
    outside_reference_fields={"tools": ToolConfiguration},
)
class ToolProviderConfiguration(BaseModel):
    identity: ToolProviderIdentity
    credentials_schema: list[ProviderConfig] = Field(
        default_factory=list,
        alias="credentials_for_provider",
        description="The credentials schema of the tool provider",
    )
    oauth_schema: OAuthSchema | None = Field(
        default=None,
        description="The OAuth schema of the tool provider if OAuth is supported",
    )
    tools: list[ToolConfiguration] = Field(default=[], description="The tools of the tool provider")
    extra: ToolProviderConfigurationExtra

    @model_validator(mode="before")
    @classmethod
    def validate_credentials_schema(cls, data: dict) -> dict:
        original_credentials_for_provider: dict[str, dict] = data.get("credentials_for_provider", {})

        credentials_for_provider: list[dict[str, Any]] = []
        for name, credential in original_credentials_for_provider.items():
            credential["name"] = name
            credentials_for_provider.append(credential)

        data["credentials_for_provider"] = credentials_for_provider
        return data

    @field_validator("tools", mode="before")
    @classmethod
    def validate_tools(cls, value) -> list[ToolConfiguration]:
        if not isinstance(value, list):
            raise ValueError("tools should be a list")

        tools: list[ToolConfiguration] = []

        for tool in value:
            # read from yaml
            if not isinstance(tool, str):
                raise ValueError("tool path should be a string")
            try:
                file = load_yaml_file(tool)
                tools.append(
                    ToolConfiguration(
                        identity=ToolIdentity(**file["identity"]),
                        parameters=[ToolParameter(**param) for param in file.get("parameters", []) or []],
                        description=ToolDescription(**file["description"]),
                        extra=ToolConfigurationExtra(**file.get("extra", {})),
                        output_schema=file.get("output_schema", None),
                    )
                )
            except Exception as e:
                raise ValueError(f"Error loading tool configuration: {e!s}") from e

        return tools


class ToolProviderType(Enum):
    """
    Enum class for tool provider
    """

    BUILT_IN = "builtin"
    WORKFLOW = "workflow"
    API = "api"
    APP = "app"
    DATASET_RETRIEVAL = "dataset-retrieval"
    MCP = "mcp"

    @classmethod
    def value_of(cls, value: str) -> "ToolProviderType":
        """
        Get value of given mode.

        :param value: mode value
        :return: mode
        """
        for mode in cls:
            if mode.value == value:
                return mode
        raise ValueError(f"invalid mode value {value}")


class ToolSelector(BaseModel):
    class Parameter(BaseModel):
        name: str = Field(..., description="The name of the parameter")
        type: ToolParameter.ToolParameterType = Field(..., description="The type of the parameter")
        required: bool = Field(..., description="Whether the parameter is required")
        description: str = Field(..., description="The description of the parameter")
        default: Union[int, float, str] | None = None
        options: list[ToolParameterOption] | None = None

    provider_id: str = Field(..., description="The id of the provider")
    tool_name: str = Field(..., description="The name of the tool")
    tool_description: str = Field(..., description="The description of the tool")
    tool_configuration: Mapping[str, Any] = Field(..., description="Configuration, type form")
    tool_parameters: Mapping[str, Parameter] = Field(..., description="Parameters, type llm")

    def to_prompt_message(self) -> PromptMessageTool:
        """
        Convert tool selector to prompt message tool, based on openai function calling schema.
        """
        tool = PromptMessageTool(
            name=self.tool_name,
            description=self.tool_description,
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )

        for name, parameter in self.tool_parameters.items():
            tool.parameters[name] = {
                "type": parameter.type.value,
                "description": parameter.description,
            }

            if parameter.required:
                tool.parameters["required"].append(name)

            if parameter.options:
                tool.parameters[name]["enum"] = [option.value for option in parameter.options]

        return tool
