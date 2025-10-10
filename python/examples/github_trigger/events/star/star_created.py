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

    def _check_starred_by(self, sender: Mapping[str, Any], starred_by_param: str | None) -> None:
        """Check if star was added by allowed users"""
        if not starred_by_param:
            return

        allowed_users = [user.strip() for user in starred_by_param.split(",") if user.strip()]
        if not allowed_users:
            return

        sender_login = sender.get("login")
        if sender_login not in allowed_users:
            raise EventIgnoreError()

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub star created webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        sender = payload.get("sender")
        if not sender:
            raise ValueError("No sender data in payload")

        # Apply filters
        self._check_starred_by(sender, parameters.get("starred_by"))

        return Variables(variables={**payload})
