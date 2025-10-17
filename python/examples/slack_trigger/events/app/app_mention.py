from __future__ import annotations

from dify_plugin.entities import ParameterOption
from dify_plugin.interfaces.trigger import Event

from .._catalog_event import CatalogSlackEvent


class AppMentionEvent(CatalogSlackEvent, Event):
    """Slack event handler for `app.mention`."""

    EVENT_KEY = "app_mention"

    def _fetch_parameter_options(self, parameter: str) -> list[ParameterOption]:
        # TODO: Implement fetching channel options
        return []
