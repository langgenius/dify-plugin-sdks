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

BUILTIN_DEFINITIONS = {
    "file": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "file name"},
            "size": {"type": "number", "description": "file size"},
            "type": {"type": "string", "description": "file type"},
            "extension": {"type": "string", "description": "file extension"},
            "mime_type": {"type": "string", "description": "file mime type"},
            "transfer_method": {"type": "string", "description": "file transfer method"},
            "url": {"type": "string", "description": "file url"},
            "related_id": {"type": "string", "description": "file related id"},
        },
        "required": ["name"],
    },
    "website_crawl": {
        "type": "object",
        "properties": {
            "source_url": {"type": "string", "description": "The URL of the crawled website"},
            "content": {"type": "string", "description": "The content of the crawled website"},
            "title": {"type": "string", "description": "The title of the crawled website"},
            "description": {"type": "string", "description": "The description of the crawled website"},
        },
        "required": ["source_url", "content"],
    },
    "online_document": {
        "type": "object",
        "properties": {
            "workspace_id": {"type": "string", "description": "The ID of the workspace where the document is stored"},
            "page_id": {"type": "string", "description": "The ID of the page in the document"},
            "content": {"type": "string", "description": "The content of the online document"},
        },
        "required": ["content"],
    },
    "pagination": {
        "type": "object",
        "properties": {
            "page": {"type": "integer", "description": "Current page number"},
            "per_page": {"type": "integer", "description": "Items per page"},
            "total": {"type": "integer", "description": "Total number of items"},
            "has_more": {"type": "boolean", "description": "Whether there are more items"},
        },
    },
    "error": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Error code"},
            "message": {"type": "string", "description": "Error message"},
            "details": {"type": "object", "description": "Additional error details"},
        },
        "required": ["code", "message"],
    },
}


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
            # read from yaml
            if not isinstance(datasource, str):
                raise ValueError("datasource path should be a string")
            try:
                file = load_yaml_file(datasource)
                if "output_schema" in file:
                    file["output_schema"] = _resolve_schema_refs(file["output_schema"], BUILTIN_DEFINITIONS)
                datasources.append(DatasourceEntity(**file))
            except Exception as e:
                raise ValueError(f"Error loading datasource configuration: {e!s}") from e

        return datasources


def _resolve_schema_refs(schema: dict[str, Any], definitions: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively resolve $ref references in a JSON schema

    Args:
        schema: The schema object that may contain $ref references
        definitions: Available type definitions to resolve references against

    Returns:
        Schema with all $ref references resolved
    """
    if isinstance(schema, dict):
        if "$ref" in schema:
            # Resolve the reference
            ref = schema["$ref"]
            if ref.startswith("#/$defs/"):
                type_name = ref.replace("#/$defs/", "")
                if type_name in definitions:
                    # Return the resolved definition (recursively resolve it too)
                    return _resolve_schema_refs(definitions[type_name], definitions)
                else:
                    raise ValueError(f"Reference '{ref}' not found in definitions")
            else:
                raise ValueError(f"Unsupported reference format: {ref}")
        else:
            # Recursively resolve references in nested objects
            resolved = {}
            for key, value in schema.items():
                resolved[key] = _resolve_schema_refs(value, definitions)
            return resolved
    elif isinstance(schema, list):
        # Recursively resolve references in arrays
        return [_resolve_schema_refs(item, definitions) for item in schema]
    else:
        # Return primitive values as-is
        return schema
