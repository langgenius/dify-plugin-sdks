from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from dify_plugin.core.entities.plugin.request import (
    AgentActions,
    EndpointActions,
    ModelActions,
    PluginInvokeType,
    ToolActions,
)


class PluginInvokeRequest[T: BaseModel](BaseModel):
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
