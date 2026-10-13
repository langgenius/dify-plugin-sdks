from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class ContractEvent(Event):
    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        if parameters.get("ignore"):
            msg = "event filtered"
            raise EventIgnoreError(msg)
        return Variables(
            variables={
                "payload": payload,
                "parameters": parameters,
                "body": request.get_data(as_text=True),
            }
        )

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        return [ParameterOption(value="echo", label=I18nObject(en_us=parameter))]
