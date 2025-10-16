from __future__ import annotations

from .._catalog_event import CatalogSlackEvent


class FileCommentDeletedEvent(CatalogSlackEvent):
    """Slack event handler for `file.comment.deleted`."""

    EVENT_KEY = "file_comment_deleted"
