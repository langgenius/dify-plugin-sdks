from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class ReactionRemovedEvent(CatalogSlackEvent):
    """Slack event handler for `reaction.removed`."""

    EVENT_KEY = "reaction_removed"
