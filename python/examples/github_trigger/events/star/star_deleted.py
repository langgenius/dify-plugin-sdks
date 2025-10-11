from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities import I18nObject, ParameterOption
from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class StarDeletedEvent(Event):
    """
    GitHub Star Deleted Event

    This event transforms GitHub star deleted webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub star deleted webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        sender = payload.get("sender")
        if not sender:
            raise ValueError("No sender data in payload")

        return Variables(variables={**payload})

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        """Fetch parameter options"""
        return [
            ParameterOption(
                value="test",
                label=I18nObject(en_US="test"),
                icon="https://avatars.githubusercontent.com/u/29746822?v=4",
            ),
        ]
