from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.oauth import OAuthSchema
from dify_plugin.entities.provider_config import CommonParameterType, ProviderConfig
from dify_plugin.entities.tool import ParameterAutoGenerate, ParameterTemplate
from werkzeug import Response


class TriggerRuntime(BaseModel):
    credentials: dict[str, Any]
    session_id: str | None


class TriggerEventDispatch(BaseModel):
    """
    The event dispatch result from trigger provider
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    event: str = Field(..., description="The event type dispatched by the trigger provider")
    response: Response = Field(
        ...,
        description="The HTTP Response object returned to third-party calls. For example, webhook calls, etc.",
    )


@docs(
    description="The response of the trigger",
)
class TriggerEvent(BaseModel):
    """
    The response of the trigger
    """

    variables: Mapping[str, Any] = Field(
        ..., description="The variables of the trigger, must have the same schema as defined in the YAML"
    )


@docs(
    description="The option of the trigger parameter",
)
class TriggerParameterOption(ParameterOption):
    """
    The option of the trigger parameter
    """


@docs(
    description="The type of the parameter",
)
class TriggerParameter(BaseModel):
    """
    The parameter of the trigger
    """

    class TriggerParameterType(StrEnum):
        STRING = CommonParameterType.STRING.value
        NUMBER = CommonParameterType.NUMBER.value
        BOOLEAN = CommonParameterType.BOOLEAN.value
        SELECT = CommonParameterType.SELECT.value
        FILE = CommonParameterType.FILE.value
        FILES = CommonParameterType.FILES.value
        MODEL_SELECTOR = CommonParameterType.MODEL_SELECTOR.value
        APP_SELECTOR = CommonParameterType.APP_SELECTOR.value
        OBJECT = CommonParameterType.OBJECT.value
        ARRAY = CommonParameterType.ARRAY.value
        DYNAMIC_SELECT = CommonParameterType.DYNAMIC_SELECT.value

    name: str = Field(..., description="The name of the parameter")
    label: I18nObject = Field(..., description="The label presented to the user")
    type: TriggerParameterType = Field(..., description="The type of the parameter")
    auto_generate: ParameterAutoGenerate | None = Field(default=None, description="The auto generate of the parameter")
    template: ParameterTemplate | None = Field(default=None, description="The template of the parameter")
    scope: str | None = None
    required: bool | None = False
    default: Union[int, float, str] | None = None
    min: Union[float, int] | None = None
    max: Union[float, int] | None = None
    precision: int | None = None
    options: list[TriggerParameterOption] | None = None
    description: I18nObject | None = None


@docs(
    description="The identity of the trigger provider",
)
class TriggerProviderIdentity(BaseModel):
    """
    The identity of the trigger provider
    """

    author: str = Field(..., description="The author of the trigger provider")
    name: str = Field(..., description="The name of the trigger provider")
    label: I18nObject = Field(..., description="The label of the trigger provider")
    description: I18nObject = Field(..., description="The description of the trigger provider")
    icon: str | None = Field(default=None, description="The icon of the trigger provider")
    tags: list[str] = Field(default_factory=list, description="The tags of the trigger provider")


@docs(
    description="The identity of the trigger",
)
class TriggerIdentity(BaseModel):
    """
    The identity of the trigger
    """

    author: str = Field(..., description="The author of the trigger")
    name: str = Field(..., description="The name of the trigger")
    label: I18nObject = Field(..., description="The label of the trigger")


@docs(
    description="The description of the trigger",
)
class TriggerDescription(BaseModel):
    """
    The description of the trigger
    """

    human: I18nObject = Field(..., description="Human readable description")
    llm: I18nObject = Field(..., description="LLM readable description")


@docs(
    description="The extra configuration for trigger",
)
class TriggerConfigurationExtra(BaseModel):
    """
    The extra configuration for trigger
    """

    @docs(
        name="Python",
        description="The python configuration for trigger",
    )
    class Python(BaseModel):
        source: str = Field(..., description="The source file path for the trigger implementation")

    python: Python


@docs(
    name="Trigger",
    description="The configuration of a trigger",
)
class TriggerConfiguration(BaseModel):
    """
    The configuration of a trigger
    """

    identity: TriggerIdentity = Field(..., description="The identity of the trigger")
    parameters: list[TriggerParameter] = Field(default=[], description="The parameters of the trigger")
    description: TriggerDescription = Field(..., description="The description of the trigger")
    extra: TriggerConfigurationExtra = Field(..., description="The extra configuration of the trigger")
    output_schema: Mapping[str, Any] | None = Field(
        default=None, description="The output schema that this trigger produces"
    )


@docs(
    description="The extra configuration for trigger provider",
)
class TriggerProviderConfigurationExtra(BaseModel):
    """
    The extra configuration for trigger provider
    """

    @docs(
        name="Python",
        description="The python configuration for trigger provider",
    )
    class Python(BaseModel):
        source: str = Field(..., description="The source file path for the trigger provider implementation")

    python: Python


@docs(
    name="TriggerProvider",
    description="The configuration of a trigger provider",
    outside_reference_fields={"triggers": TriggerConfiguration},
)
class TriggerProviderConfiguration(BaseModel):
    """
    The configuration of a trigger provider
    """

    identity: TriggerProviderIdentity = Field(..., description="The identity of the trigger provider")
    credentials_schema: list[ProviderConfig] = Field(
        default_factory=list,
        description="The credentials schema of the trigger provider",
    )
    oauth_schema: OAuthSchema | None = Field(
        default=None,
        description="The OAuth schema of the trigger provider if OAuth is supported",
    )
    subscription_schema: list[ProviderConfig] = Field(
        default_factory=list,
        description="The subscription schema for trigger(webhook, polling, etc.) subscription parameters",
    )
    triggers: list[TriggerConfiguration] = Field(default=[], description="The triggers of the trigger provider")
    extra: TriggerProviderConfigurationExtra = Field(..., description="The extra configuration of the trigger provider")

    @model_validator(mode="before")
    @classmethod
    def validate_credentials_schema(cls, data: dict) -> dict:
        # Handle credentials_schema conversion from dict to list format
        original_credentials_schema = data.get("credentials_schema", [])
        if isinstance(original_credentials_schema, dict):
            credentials_schema: list[dict[str, Any]] = []
            for name, param in original_credentials_schema.items():
                param["name"] = name
                credentials_schema.append(param)
            data["credentials_schema"] = credentials_schema
        elif isinstance(original_credentials_schema, list):
            data["credentials_schema"] = original_credentials_schema
        else:
            raise ValueError("credentials_schema should be a list or dict")
        return data

    @model_validator(mode="before")
    @classmethod
    def validate_subscription_schema(cls, data: dict) -> dict:
        # Handle subscription_schema conversion from dict to list format
        original_subscription_schema = data.get("subscription_schema", [])
        if isinstance(original_subscription_schema, dict):
            subscription_schema: list[dict[str, Any]] = []
            for name, param in original_subscription_schema.items():
                param["name"] = name
                subscription_schema.append(param)
            data["subscription_schema"] = subscription_schema
        elif isinstance(original_subscription_schema, list):
            # Already in list format, no conversion needed
            data["subscription_schema"] = original_subscription_schema

        return data

    @field_validator("triggers", mode="before")
    @classmethod
    def validate_triggers(cls, value) -> list[TriggerConfiguration]:
        if not isinstance(value, list):
            raise ValueError("triggers should be a list")

        triggers: list[TriggerConfiguration] = []

        for trigger in value:
            # read from yaml
            if not isinstance(trigger, str):
                raise ValueError("trigger path should be a string")
            try:
                file = load_yaml_file(trigger)
                triggers.append(
                    TriggerConfiguration(
                        identity=TriggerIdentity(**file["identity"]),
                        parameters=[TriggerParameter(**param) for param in file.get("parameters", []) or []],
                        description=TriggerDescription(**file["description"]),
                        extra=TriggerConfigurationExtra(**file.get("extra", {})),
                        output_schema=file.get("output_schema", None),
                    )
                )
            except Exception as e:
                raise ValueError(f"Error loading trigger configuration: {e!s}") from e

        return triggers


@docs(
    description="Result of a successful trigger subscription operation",
)
class Subscription(BaseModel):
    """
    Result of a successful trigger subscription operation.

    Contains all information needed to manage the subscription lifecycle.
    """

    expire_at: int = Field(
        ..., description="The timestamp when the subscription will expire, this for refresh the subscription"
    )

    metadata: dict[str, Any] = Field(
        ..., description="Metadata about the subscription in the external service, defined in subscription_schema"
    )


@docs(
    description="Result of a trigger unsubscription operation",
)
class Unsubscription(BaseModel):
    """
    Result of a trigger unsubscription operation.

    Provides detailed information about the unsubscription attempt,
    including success status and error details if failed.
    """

    success: bool = Field(..., description="Whether the unsubscription was successful")

    message: str | None = Field(
        None,
        description="Human-readable message about the operation result. "
        "Success message for successful operations, "
        "detailed error information for failures.",
    )
