from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class WorkflowRunRequestedTrigger(TriggerEvent):
    """
    GitHub WorkflowRunRequested Event Trigger

    This trigger handles GitHub workflow run requested events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub workflow run requested event trigger
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Return the relevant payload fields directly
        return Event(variables={
            "workflow_run": payload.get("workflow_run"),
            "workflow": payload.get("workflow"),
            "repository": payload.get("repository"),
            "sender": payload.get("sender"),
        })
