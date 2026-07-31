import json

from pydantic import BaseModel

from dify_plugin.core.entities.plugin.request import (
    AgentActions,
    DatasourceActions,
    DynamicParameterActions,
    EndpointActions,
    ModelActions,
    OAuthActions,
    PluginInvokeType,
    ToolActions,
    TriggerActions,
)
from dify_plugin.integration.entities import PluginInvokeRequest


class EmptyRequest(BaseModel):
    pass


def test_plugin_invoke_request_supports_every_action() -> None:
    actions_by_type = {
        PluginInvokeType.Agent: AgentActions,
        PluginInvokeType.Tool: ToolActions,
        PluginInvokeType.Model: ModelActions,
        PluginInvokeType.Endpoint: EndpointActions,
        PluginInvokeType.Trigger: TriggerActions,
        PluginInvokeType.OAuth: OAuthActions,
        PluginInvokeType.Datasource: DatasourceActions,
        PluginInvokeType.DynamicParameter: DynamicParameterActions,
    }

    assert set(actions_by_type) == set(PluginInvokeType)
    for invoke_type, actions in actions_by_type.items():
        for action in actions:
            request = json.loads(
                PluginInvokeRequest(
                    invoke_id="test",
                    type=invoke_type,
                    action=action,
                    request=EmptyRequest(),
                ).model_dump_json()
            )
            assert request["type"] == invoke_type.value
            assert request["action"] == action.value
