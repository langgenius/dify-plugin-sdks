from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileCommentAddedEvent(CatalogSlackEvent):
    """Slack event handler for `file.comment.added`."""

    EVENT_KEY = "file_comment_added"
