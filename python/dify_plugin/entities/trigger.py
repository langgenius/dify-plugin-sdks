from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Union

from pydantic import BaseModel, Field

from dify_plugin.core.documentation.schema_doc import docs
from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.provider_config import CommonParameterType
from dify_plugin.entities.tool import ParameterAutoGenerate, ParameterTemplate


class TriggerRuntime(BaseModel):
    credentials: dict[str, Any]
    session_id: str | None

class TriggerEvent(BaseModel):
    """
    The event of the trigger
    """

    event: str = Field(..., description="The event of the trigger")

@docs(
    description="The response of the trigger",
)
class TriggerResponse(BaseModel):
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
        # TOOL_SELECTOR = CommonParameterType.TOOL_SELECTOR.value
        # ANY = CommonParameterType.ANY.value
        # MCP object and array type parameters
        OBJECT = CommonParameterType.OBJECT.value
        ARRAY = CommonParameterType.ARRAY.value
        DYNAMIC_SELECT = CommonParameterType.DYNAMIC_SELECT.value

    name: str = Field(..., description="The name of the parameter")
    label: I18nObject = Field(..., description="The label presented to the user")
    type: TriggerParameterType = Field(..., description="The type of the parameter")
    auto_generate: ParameterAutoGenerate | None = Field(
        default=None, description="The auto generate of the parameter"
    )
    template: ParameterTemplate | None = Field(default=None, description="The template of the parameter")
    scope: str | None = None
    required: bool | None = False
    default: Union[int, float, str] | None = None
    min: Union[float, int] | None = None
    max: Union[float, int] | None = None
    precision: int | None = None
    options: list[TriggerParameterOption] | None = None
    description: I18nObject | None = None
