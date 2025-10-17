from typing import Any

from dify_plugin.entities import ModelInvokeCompletionChunk
from dify_plugin.entities.trigger import TriggerEntity
from dify_plugin.interfaces.trigger import TriggerSubscription


class SlackTriggerSubscription(TriggerSubscription):
    """Implementation of Slack Events API webhook subscription."""

    def subscribe(
        self,
        trigger_entity: TriggerEntity,
        credentials: dict[str, Any],
        subscription: dict[str, Any],
    ) -> dict[str, Any]:
        """Process Slack webhook events."""
        return subscription

    def unsubscribe(
        self,
        trigger_entity: TriggerEntity,
        credentials: dict[str, Any],
        subscription: dict[str, Any],
    ) -> str | None:
        """Clean up Slack webhook subscription."""
        return "unsubscribed"

    def _generator_response(self) -> ModelInvokeCompletionChunk:
        """Generate streaming response."""
        pass
