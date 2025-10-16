from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ReactionAddedEvent(CatalogSlackEvent):
    """Slack event handler for `reaction.added`."""

    EVENT_KEY = "reaction_added"
