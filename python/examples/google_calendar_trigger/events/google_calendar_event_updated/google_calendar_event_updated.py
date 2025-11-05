from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables

from ._base import GoogleCalendarEventBase


class GoogleCalendarEventUpdatedEvent(GoogleCalendarEventBase):
    """Emit Google Calendar events that were updated since the last sync."""

    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        self._validate_request(request)

        events = self._collect_events(payload, "updated")
        self._ensure_events_or_raise(events)

        calendar_id = self._resolve_calendar_id(payload, parameters)
        enriched = self._enrich_events(calendar_id=calendar_id, events=events, include_deleted=False)

        return self._build_variables(payload=payload, calendar_id=calendar_id, events=enriched)
