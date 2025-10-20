from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GoogleDriveChangeDetectedEvent(Event):
    """Fetch Google Drive change feed entries and expose them to workflows."""

    def _on_event(self, request: Request, parameters: Mapping[str, Any], payload: Mapping[str, Any]) -> Variables:
        credentials = self.runtime.credentials or {}
        access_token = credentials.get("access_token")
        if not access_token:
            raise ValueError("Missing Google Drive OAuth access token in runtime credentials")

        spaces = self._resolve_spaces()
        include_removed = self._to_bool(parameters.get("include_removed"), default=False)
        restrict_to_my_drive = self._to_bool(parameters.get("restrict_to_my_drive"), default=False)

        changes = payload.get("changes", [])
        if not changes:
            raise EventIgnoreError("No Drive changes found in payload")

        filtered_changes = self._filter_changes(
            changes=changes,
            include_removed=include_removed,
            restrict_to_my_drive=restrict_to_my_drive,
        )

        if not filtered_changes:
            raise EventIgnoreError("No Drive changes matched the configured filters")

        variables = {
            "changes": filtered_changes,
            "spaces": spaces,
            "subscription": {
                "channel_id": self.runtime.subscription.properties.get("channel_id"),
                "resource_id": self.runtime.subscription.properties.get("resource_id"),
                "watch_expiration": self.runtime.subscription.properties.get("watch_expiration"),
                "user": self.runtime.subscription.properties.get("user"),
            },
        }

        return Variables(variables=variables)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _filter_changes(
        self,
        *,
        changes: Sequence[Mapping[str, Any]],
        include_removed: bool,
        restrict_to_my_drive: bool,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for change in changes:
            removed = bool(change.get("removed"))
            if removed and not include_removed:
                continue

            file_info = change.get("file") or {}
            if not isinstance(file_info, Mapping):
                file_info = {}

            if restrict_to_my_drive and not file_info.get("ownedByMe"):
                continue

            normalized = {
                "change_type": change.get("changeType"),
                "removed": removed,
                "file_id": change.get("fileId"),
                "file": dict(file_info),
            }
            results.append(normalized)
        return results

    def _resolve_spaces(self) -> list[str]:
        spaces = self.runtime.subscription.properties.get("spaces") or []
        if isinstance(spaces, str):
            return [part.strip() for part in spaces.split(",") if part.strip()]
        if isinstance(spaces, Sequence):
            return [str(space) for space in spaces if str(space)]
        return ["drive"]

    @staticmethod
    def _safe_int(value: Any, default: int, minimum: int, maximum: int) -> int:
        try:
            integer = int(value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, integer))

    @staticmethod
    def _to_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        return default if value == "" else bool(value)
