from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class LabelEditedTrigger(TriggerEvent):
    """
    GitHub LabelEdited Event Trigger

    This trigger handles GitHub label edited events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub label edited event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Return the relevant payload fields directly
        return Event(variables={
            "label": payload.get("label"),
            "changes": payload.get("changes"),
            "repository": payload.get("repository"),
            "sender": payload.get("sender"),
        })
