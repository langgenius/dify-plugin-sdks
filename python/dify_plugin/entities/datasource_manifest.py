from enum import Enum, StrEnum
from typing import Any, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities import (
    I18nObject,
    ParameterAutoGenerate,
    ParameterOption,
    ParameterTemplate,
)
from dify_plugin.entities.oauth import OAuthSchema
from dify_plugin.entities.provider_config import CommonParameterType, ProviderConfig


@docs(
    description="The label of the datasource",
)
class DatasourceLabelEnum(Enum):
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
    OTHER = "other"


@docs(
    name="DatasourceProviderType",
    description="Type of datasource provider",
)
class DatasourceProviderType(StrEnum):
    """
    Enum class for datasource provider
    """

    ONLINE_DOCUMENT = "online_document"
    WEBSITE_CRAWL = "website_crawl"
    ONLINE_DRIVE = "online_drive"


@docs(
    name="DatasourceParameter",
    description="Parameter of datasource entity",
)
class DatasourceParameter(BaseModel):
    """
    Overrides type
    """

    class DatasourceParameterType(StrEnum):
        STRING = CommonParameterType.STRING.value
        NUMBER = CommonParameterType.NUMBER.value
        BOOLEAN = CommonParameterType.BOOLEAN.value
        SELECT = CommonParameterType.SELECT.value
        SECRET_INPUT = CommonParameterType.SECRET_INPUT.value
        FILE = CommonParameterType.FILE.value
        FILES = CommonParameterType.FILES.value

    name: str = Field(..., description="The name of the parameter")
    label: I18nObject = Field(..., description="The label presented to the user")
    placeholder: I18nObject | None = Field(default=None, description="The placeholder presented to the user")
    scope: str | None = None
    auto_generate: ParameterAutoGenerate | None = None
    template: ParameterTemplate | None = None
    required: bool = False
    default: Union[float, int, str] | None = None
    min: Union[float, int] | None = None
    max: Union[float, int] | None = None
    precision: int | None = None
    options: list[ParameterOption] = Field(default_factory=list)
    type: DatasourceParameterType = Field(..., description="The type of the parameter")
    description: I18nObject = Field(..., description="The description of the parameter")


@docs(
    name="DatasourceIdentity",
    description="Identity of datasource entity",
)
class DatasourceIdentity(BaseModel):
    author: str = Field(..., description="The author of the datasource")
    name: str = Field(..., description="The name of the datasource")
    label: I18nObject = Field(..., description="The label of the datasource")
    icon: str | None = None


@docs(
    name="DatasourceEntityExtra",
    description="The extra of the datasource entity",
)
class DatasourceEntityExtra(BaseModel):
    class Python(BaseModel):
        source: str

    python: Python


@docs(
    name="Datasource",
    description="Datasource entity",
)
class DatasourceEntity(BaseModel):
    identity: DatasourceIdentity
    parameters: list[DatasourceParameter] = Field(default_factory=list)
    description: I18nObject = Field(..., description="The label of the datasource")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="Output schema definition")
    extra: DatasourceEntityExtra

    @field_validator("parameters", mode="before")
    @classmethod
    def set_parameters(cls, v, validation_info: ValidationInfo) -> list[DatasourceParameter]:
        return v or []


@docs(
    description="Identity of datasource provider",
)
class DatasourceProviderIdentity(BaseModel):
    author: str = Field(..., description="The author of the datasource")
    name: str = Field(..., description="The name of the datasource")
    description: I18nObject = Field(..., description="The description of the datasource")
    icon: str = Field(..., description="The icon of the datasource")
    label: I18nObject = Field(..., description="The label of the datasource")
    tags: list[DatasourceLabelEnum] | None = Field(
        default=[],
        description="The tags of the datasource",
    )


@docs(
    name="DatasourceProviderExtra",
    description="The extra of the datasource provider",
)
class DatasourceProviderConfigurationExtra(BaseModel):
    class Python(BaseModel):
        source: str

    python: Python


@docs(
    name="DatasourceProvider",
    description="Manifest of datasource providers",
    outside_reference_fields={"datasources": DatasourceEntity},
)
class DatasourceProviderManifest(BaseModel):
    """
    Datasource provider entity
    """

    identity: DatasourceProviderIdentity = Field(..., description="The identity of the datasource provider")
    credentials_schema: list[ProviderConfig] = Field(
        default_factory=list, description="The credentials schema of the datasource provider"
    )
    oauth_schema: OAuthSchema | None = Field(
        default=None, description="The OAuth schema of the datasource provider if OAuth is supported"
    )
    provider_type: DatasourceProviderType = Field(..., description="The type of the datasource provider")
    datasources: list[DatasourceEntity] = Field(
        default_factory=list, description="The datasources of the datasource provider"
    )
    extra: DatasourceProviderConfigurationExtra = Field(..., description="The extra of the datasource provider")

    @field_validator("datasources", mode="before")
    @classmethod
    def validate_datasources(cls, value) -> list[DatasourceEntity]:
        if not isinstance(value, list):
            raise ValueError("datasources should be a list")

        datasources: list[DatasourceEntity] = []

        for datasource in value:
            if not isinstance(datasource, str):
                raise ValueError("datasource path should be a string")
            try:
                file = load_yaml_file(datasource)
                datasources.append(DatasourceEntity(**file))
            except Exception as e:
                raise ValueError(f"Error loading datasource configuration: {e!s}") from e

        return datasources
