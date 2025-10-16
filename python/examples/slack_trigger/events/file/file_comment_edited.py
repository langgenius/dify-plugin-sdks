from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileCommentEditedEvent(CatalogSlackEvent):
    """Slack event handler for `file.comment.edited`."""

    EVENT_KEY = "file_comment_edited"
