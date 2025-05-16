from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from dify_plugin.core.entities.plugin.request import (
    AgentActions,
    EndpointActions,
    ModelActions,
    PluginInvokeType,
    ToolActions,
)

T = TypeVar("T", bound=BaseModel)


class PluginInvokeRequest(BaseModel, Generic[T]):
    invoke_id: str
    type: PluginInvokeType
    action: AgentActions | ToolActions | ModelActions | EndpointActions
    request: T


class ResponseType(StrEnum):
    INFO = "info"
    ERROR = "error"
    PLUGIN_RESPONSE = "plugin_response"
    PLUGIN_READY = "plugin_ready"
    PLUGIN_INVOKE_END = "plugin_invoke_end"


class PluginGenericResponse(BaseModel):
    invoke_id: str
    type: ResponseType

    response: Mapping[str, Any]
