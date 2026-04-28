from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class StarCreatedEvent(Event):
    """
    GitHub Star Created Event

    This event transforms GitHub star created webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _on_event(
        self,
        request: Request,
        parameters: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> Variables:
        """
        Transform GitHub star created webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            msg = "No payload received"
            raise ValueError(msg)

        star_action = payload.get("action")
        events = parameters.get("events", [])
        if star_action not in events:
            msg = f"Not interested in this star action {star_action}"
            raise EventIgnoreError(msg)

        sender = payload.get("sender")
        if not sender:
            msg = "No sender data in payload"
            raise ValueError(msg)
        return Variables(variables={**payload})
