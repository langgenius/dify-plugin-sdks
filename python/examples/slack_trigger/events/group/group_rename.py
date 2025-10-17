from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class GroupRenameEvent(CatalogSlackEvent):
    """Slack event handler for `group.rename`."""

    EVENT_KEY = "group_rename"
