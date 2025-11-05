from __future__ import annotations

import urllib.parse
from collections.abc import Mapping, Sequence
from typing import Any

import requests
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GoogleCalendarEventBase(Event):
    """Shared helpers for Google Calendar trigger events."""

    _CAL_BASE = "https://www.googleapis.com/calendar/v3"

    def _collect_events(self, payload: Mapping[str, Any], key: str) -> list[dict[str, Any]]:
        raw_items = payload.get(key)
        if not isinstance(raw_items, Sequence):
            return []

        collected: list[dict[str, Any]] = []
        for item in raw_items:
            if isinstance(item, Mapping):
                collected.append(dict(item))
        return collected

    def _resolve_calendar_id(self, payload: Mapping[str, Any], parameters: Mapping[str, Any]) -> str:
        subscription_parameters: Mapping[str, Any] = {}
        if getattr(self.runtime, "subscription", None):
            subscription_parameters = self.runtime.subscription.parameters or {}

        calendar_id = payload.get("calendarId") or parameters.get("calendar_id") or subscription_parameters.get("calendar_id") or "primary"
        return str(calendar_id)

    def _get_access_token(self) -> str:
        credentials: Mapping[str, Any] = {}
        if getattr(self.runtime, "credentials", None):
            credentials = self.runtime.credentials or {}
        token = credentials.get("access_token")
        if not token:
            raise ValueError("Missing Google Calendar OAuth access token in runtime credentials")
        return str(token)

    def _enrich_events(
        self,
        *,
        calendar_id: str,
        events: list[dict[str, Any]],
        include_deleted: bool,
    ) -> list[dict[str, Any]]:
        if not events:
            return events

        access_token = self._get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        encoded_calendar = urllib.parse.quote(calendar_id, safe="@._-")

        enriched: list[dict[str, Any]] = []
        for event in events:
            event_id = str(event.get("id") or "").strip()
            if not event_id:
                continue
            encoded_event = urllib.parse.quote(event_id, safe="@._-")
            params = {"showDeleted": "true"} if include_deleted else None
            try:
                resp = requests.get(
                    f"{self._CAL_BASE}/calendars/{encoded_calendar}/events/{encoded_event}",
                    headers=headers,
                    params=params,
                    timeout=10,
                )
            except requests.RequestException:
                enriched.append(event)
                continue

            if resp.status_code == 200:
                try:
                    enriched.append(resp.json() or {})
                except Exception:
                    enriched.append(event)
            elif resp.status_code == 404 and include_deleted:
                enriched.append(event)
            else:
                enriched.append(event)

        # Fallback to original list if enrichment resulted in empty collection
        return enriched or events

    def _build_variables(
        self,
        *,
        payload: Mapping[str, Any],
        calendar_id: str,
        events: list[dict[str, Any]],
    ) -> Variables:
        if not events:
            raise EventIgnoreError()

        variables = {
            "calendar_id": calendar_id,
            "resource_state": payload.get("resourceState"),
            "resource_id": payload.get("resourceId"),
            "channel_id": payload.get("channelId"),
            "next_sync_token": payload.get("nextSyncToken"),
            "events": events,
        }
        include_cancelled = payload.get("includeCancelled")
        if include_cancelled is not None:
            variables["include_cancelled"] = include_cancelled

        return Variables(variables=variables)

    def _ensure_events_or_raise(self, events: list[dict[str, Any]]) -> None:
        if not events:
            raise EventIgnoreError()

    def _validate_request(self, request: Request) -> None:
        # Placeholder for future validation hooks (mirrors Gmail event structure).
        _ = request
        return
