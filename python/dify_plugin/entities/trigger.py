from collections.abc import Mapping
from enum import Enum, StrEnum
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from werkzeug import Response

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.core.runtime import Session
from dify_plugin.core.utils.yaml_loader import load_yaml_file
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.oauth import OAuthSchema
from dify_plugin.entities.provider_config import CommonParameterType, CredentialType, ProviderConfig
from dify_plugin.entities.tool import ParameterAutoGenerate, ParameterTemplate


class TriggerSubscriptionConstructorRuntime:
    session: Session
    credentials: Mapping[str, Any] | None
    credential_type: CredentialType

    def __init__(
        self,
        session: Session,
        credential_type: CredentialType,
        credentials: Mapping[str, Any] | None = None,
    ):
        self.session = session
        self.credentials = credentials
        self.credential_type = credential_type


class EventDispatch(BaseModel):
    """
    The dispatch result from a trigger when processing an incoming webhook.

    Contains the list of Event names that should be invoked and the HTTP response
    to return to the webhook caller.

    Supports dispatching single or multiple Events from a single webhook call.
    When multiple Events are specified, each Event will transform the webhook
    and trigger its corresponding workflow.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_id: str = Field(default="", description="The user who triggered the event (e.g. google user ID)")
    events: list[str] = Field(default_factory=list, description="List of Event names that should be invoked.")
    response: Response = Field(
        ...,
        description="The HTTP Response object returned to third-party calls. For example, webhook calls, etc.",
    )

    payload: Mapping[str, Any] = Field(
        default_factory=dict,
        description="Decoded payload from the webhook request, which will be delivered into `_on_event` method.",
    )


@docs(
    description="The structured output variables from an event",
)
class Variables(BaseModel):
    """
    The structured output variables from an event after processing.

    Contains the extracted and transformed variables that will be passed to workflows.
    The structure of variables must match the output_schema defined in the event's YAML configuration.
    """

    variables: Mapping[str, Any] = Field(
        ...,
        description="The output variables of the event, same with the schema defined in `output_schema` in the YAML",
    )


@docs(
    description="The option of the event parameter",
)
class EventParameterOption(ParameterOption):
    """
    The option of the event parameter
    """


@docs(
    description="The type of the parameter",
)
class EventParameter(BaseModel):
    """
    The parameter of the event
    """

    class EventParameterType(StrEnum):
        STRING = CommonParameterType.STRING.value
        NUMBER = CommonParameterType.NUMBER.value
        BOOLEAN = CommonParameterType.BOOLEAN.value
        SELECT = CommonParameterType.SELECT.value
        CHECKBOX = CommonParameterType.CHECKBOX.value
        FILE = CommonParameterType.FILE.value
        FILES = CommonParameterType.FILES.value
        MODEL_SELECTOR = CommonParameterType.MODEL_SELECTOR.value
        APP_SELECTOR = CommonParameterType.APP_SELECTOR.value
        OBJECT = CommonParameterType.OBJECT.value
        ARRAY = CommonParameterType.ARRAY.value
        DYNAMIC_SELECT = CommonParameterType.DYNAMIC_SELECT.value

    name: str = Field(..., description="The name of the parameter")
    label: I18nObject = Field(..., description="The label presented to the user")
    type: EventParameterType = Field(..., description="The type of the parameter")
    auto_generate: ParameterAutoGenerate | None = Field(default=None, description="The auto generate of the parameter")
    template: ParameterTemplate | None = Field(default=None, description="The template of the parameter")
    scope: str | None = None
    required: bool | None = False
    multiple: bool | None = Field(
        default=False,
        description="Whether the parameter is multiple select, only valid for select or dynamic-select type",
    )
    default: Union[int, float, str, list] | None = None
    min: Union[float, int] | None = None
    max: Union[float, int] | None = None
    precision: int | None = None
    options: list[EventParameterOption] | None = None
    description: I18nObject | None = None


class EventLabelEnum(Enum):
    WEBHOOKS = "webhooks"


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
    icon_dark: str | None = Field(default=None, description="The dark mode icon of the trigger provider")
    tags: list[EventLabelEnum] = Field(default_factory=list, description="The tags of the trigger provider")


@docs(
    description="The identity of an event",
)
class EventIdentity(BaseModel):
    """
    The identity of an event
    """

    author: str = Field(..., description="The author of the event")
    name: str = Field(..., description="The name of the event")
    label: I18nObject = Field(..., description="The label of the event")


@docs(
    description="The description of an event",
)
class EventDescription(BaseModel):
    """
    The description of an event
    """

    human: I18nObject = Field(..., description="Human readable description")
    llm: I18nObject = Field(..., description="LLM readable description")


@docs(
    description="The extra configuration for an event",
)
class EventConfigurationExtra(BaseModel):
    """
    The extra configuration for an event
    """

    @docs(
        name="Python",
        description="The python configuration for event",
    )
    class Python(BaseModel):
        source: str = Field(..., description="The source file path for the event implementation")

    python: Python


@docs(
    description="The configuration of an event",
)
class EventConfiguration(BaseModel):
    """
    The configuration of an event
    """

    identity: EventIdentity = Field(..., description="The identity of the event")
    parameters: list[EventParameter] = Field(default_factory=list, description="The parameters of the event")
    description: I18nObject = Field(..., description="The description of the event")
    extra: EventConfigurationExtra = Field(..., description="The extra configuration of the event")
    output_schema: Mapping[str, Any] | None = Field(
        default=None, description="The output schema that this event produces"
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
    description="The subscription constructor configuration of the trigger provider",
)
class TriggerSubscriptionConstructorConfigurationExtra(BaseModel):
    """Additional configuration for trigger subscription constructor."""

    @docs(
        name="Python",
        description="The python configuration for trigger subscription constructor",
    )
    class Python(BaseModel):
        source: str = Field(..., description="The source file path for the constructor implementation")

    python: Python


@docs(
    name="TriggerSubscriptionConstructor",
    description="Configuration for a trigger subscription constructor",
)
class TriggerSubscriptionConstructorConfiguration(BaseModel):
    """Configuration for a trigger subscription constructor implementation."""

    parameters: list[EventParameter] = Field(
        default_factory=list,
        description="The user input parameters required to create a subscription",
    )
    credentials_schema: list[ProviderConfig] = Field(
        default_factory=list,
        description="The credentials schema required by the subscription constructor",
    )
    oauth_schema: OAuthSchema | None = Field(
        default=None,
        description="The OAuth schema of the subscription constructor if OAuth is supported",
    )
    extra: TriggerSubscriptionConstructorConfigurationExtra | None = Field(
        default=None,
        description="Extra metadata for locating the constructor implementation",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_credentials_schema(cls, data: Any) -> dict[str, Any]:
        if data is None:
            return {}

        if isinstance(data, cls):
            return data.model_dump()

        if not isinstance(data, dict):
            raise ValueError("subscription_constructor should be defined as a mapping")

        normalised = dict(data)
        original_credentials_schema = normalised.get("credentials_schema", [])
        if isinstance(original_credentials_schema, dict):
            credentials_schema: list[dict[str, Any]] = []
            for name, param in original_credentials_schema.items():
                param["name"] = name
                credentials_schema.append(param)
            normalised["credentials_schema"] = credentials_schema
        elif isinstance(original_credentials_schema, list):
            normalised["credentials_schema"] = original_credentials_schema
        else:
            raise ValueError("credentials_schema should be a list or dict")

        return normalised


@docs(
    name="TriggerProvider",
    description="The configuration of a trigger provider",
    outside_reference_fields={"events": EventConfiguration},
)
class TriggerProviderConfiguration(BaseModel):
    """
    The configuration of a trigger provider
    """

    identity: TriggerProviderIdentity = Field(..., description="The identity of the trigger provider")
    subscription_schema: list[ProviderConfig] = Field(
        default_factory=list,
        description="The credentials schema of the trigger provider",
    )
    subscription_constructor: TriggerSubscriptionConstructorConfiguration | None = Field(
        default=None,
        description="The configuration of the trigger subscription constructor",
    )
    events: list[EventConfiguration] = Field(default=[], description="The Events of the trigger")
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

    @field_validator("events", mode="before")
    @classmethod
    def validate_events(cls, value) -> list[EventConfiguration]:
        if not isinstance(value, list):
            raise ValueError("events should be a list")

        events: list[EventConfiguration] = []

        for event in value:
            # read from yaml
            if not isinstance(event, str):
                raise ValueError("event path should be a string")
            try:
                file = load_yaml_file(event)
                events.append(
                    EventConfiguration(
                        identity=EventIdentity(**file["identity"]),
                        parameters=[EventParameter(**param) for param in file.get("parameters", []) or []],
                        description=I18nObject(**file["description"]),
                        extra=EventConfigurationExtra(**file.get("extra", {})),
                        output_schema=file.get("output_schema", None),
                    )
                )
            except Exception as e:
                raise ValueError(f"Error loading event configuration: {e!s}") from e

        return events


@docs(
    description="Result of a successful trigger subscription operation",
)
class Subscription(BaseModel):
    """
    Result of a successful trigger subscription operation.

    Contains all information needed to manage the subscription lifecycle.
    """

    expires_at: int = Field(
        default=-1,
        description=(
            "The timestamp when the subscription will expire, used for refreshing the subscription. "
            "Set to -1 if the subscription does not expire"
        ),
    )

    endpoint: str = Field(..., description="The webhook endpoint URL allocated by Dify for receiving events")

    parameters: Mapping[str, Any] | None = Field(
        default=None,
        description=(
            "The parameters of the subscription, only available when the subscription "
            "is created by the trigger subscription constructor"
        ),
    )
    properties: Mapping[str, Any] = Field(
        default_factory=dict,
        description=(
            "The necessary information for this subscription, e.g., external_id, events, repository, etc. "
            "These properties are defined in `subscription_schema` in the provider's YAML"
        ),
    )


@docs(
    description="Result of a trigger unsubscription operation",
)
class UnsubscribeResult(BaseModel):
    """
    Result of a trigger unsubscribe operation.

    Provides detailed information about the unsubscribe attempt,
    including success status and error details if failed.
    """

    success: bool = Field(..., description="Whether the unsubscribe was successful")

    message: str | None = Field(
        None,
        description="Human-readable message about the operation result. "
        "Success message for successful operations, "
        "detailed error information for failures.",
    )
