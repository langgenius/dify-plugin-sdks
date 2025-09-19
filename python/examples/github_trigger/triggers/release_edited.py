from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class ReleaseEditedTrigger(TriggerEvent):
    """
    GitHub Release Release Edited Event Trigger

    This trigger handles GitHub release edited events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub release edited event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is the expected action
        action = payload.get("action", "")
        if action != "edited":
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'edited'")

        # Return the relevant payload fields directly
        return Event(variables={
            "release": payload.get("release"),
            "changes": payload.get("changes"),
            "repository": payload.get("repository"),
            "sender": payload.get("sender"),
        })
