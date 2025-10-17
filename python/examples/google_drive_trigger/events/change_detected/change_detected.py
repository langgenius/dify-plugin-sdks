from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import requests
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class GoogleDriveChangeDetectedEvent(Event):
    """Fetch Google Drive change feed entries and expose them to workflows."""

    _CHANGES_ENDPOINT = "https://www.googleapis.com/drive/v3/changes"

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        headers = self._get_headers(request)
        body = self._get_body(request)

        credentials = self.runtime.credentials or {}
        access_token = credentials.get("access_token")
        if not access_token:
            raise ValueError("Missing Google Drive OAuth access token in runtime credentials")

        spaces = self._resolve_spaces()
        page_token = self._resolve_page_token()
        max_changes = self._safe_int(parameters.get("max_changes"), default=100, minimum=1, maximum=1000)
        include_removed = self._to_bool(parameters.get("include_removed"), default=False)
        restrict_to_my_drive = self._to_bool(parameters.get("restrict_to_my_drive"), default=False)
        include_items_from_all_drives = self._to_bool(
            parameters.get("include_items_from_all_drives"), default=True
        )
        supports_all_drives = self._to_bool(parameters.get("supports_all_drives"), default=True)

        changes, next_page_token, new_start_page_token = self._fetch_changes(
            access_token=access_token,
            page_token=page_token,
            spaces=spaces,
            max_changes=max_changes,
            include_removed=include_removed,
            restrict_to_my_drive=restrict_to_my_drive,
            include_items_from_all_drives=include_items_from_all_drives,
            supports_all_drives=supports_all_drives,
        )

        filtered_changes = self._filter_changes(
            changes=changes,
            include_removed=include_removed,
            restrict_to_my_drive=restrict_to_my_drive,
        )

        if not filtered_changes:
            raise EventIgnoreError("No Drive changes matched the configured filters")

        persisted_token = new_start_page_token or next_page_token or page_token
        if persisted_token:
            self._persist_page_token(persisted_token)

        variables = {
            "changes": filtered_changes,
            "current_page_token": page_token,
            "next_page_token": next_page_token,
            "new_start_page_token": new_start_page_token,
            "headers": headers,
            "body": body,
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

    def _fetch_changes(
        self,
        *,
        access_token: str,
        page_token: str,
        spaces: Sequence[str],
        max_changes: int,
        include_removed: bool,
        restrict_to_my_drive: bool,
        include_items_from_all_drives: bool,
        supports_all_drives: bool,
    ) -> tuple[list[dict[str, Any]], str | None, str | None]:
        headers = {"Authorization": f"Bearer {access_token}"}
        params: dict[str, Any] = {
            "pageToken": page_token,
            "pageSize": max_changes,
            "spaces": ",".join(spaces),
            "includeRemoved": str(include_removed).lower(),
            "restrictToMyDrive": str(restrict_to_my_drive).lower(),
            "includeItemsFromAllDrives": str(include_items_from_all_drives).lower(),
            "supportsAllDrives": str(supports_all_drives).lower(),
            "fields": "changes(changeType,removed,fileId,file(name,id,mimeType,owners,parents,driveId,teamDriveId,trashed,ownedByMe,modifiedTime,createdTime,webViewLink,iconLink,lastModifyingUser,capabilities)),newStartPageToken,nextPageToken",
        }

        try:
            response = requests.get(self._CHANGES_ENDPOINT, headers=headers, params=params, timeout=10)
        except requests.RequestException as exc:
            raise ValueError(f"Failed to fetch Google Drive changes: {exc}") from exc

        payload = response.json() if response.content else {}
        if response.status_code != 200:
            raise ValueError(f"Google Drive changes API error: {payload}")

        raw_changes = payload.get("changes") or []
        changes: list[dict[str, Any]] = []
        if isinstance(raw_changes, Sequence):
            for change in raw_changes:
                if isinstance(change, Mapping):
                    changes.append(dict(change))

        next_page_token = payload.get("nextPageToken")
        new_start_page_token = payload.get("newStartPageToken")
        return changes, next_page_token, new_start_page_token

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

    def _get_headers(self, request: Request) -> dict[str, Any]:
        headers = request.environ.get("google_drive.trigger.headers")
        if isinstance(headers, Mapping):
            return dict(headers)
        return {}

    def _get_body(self, request: Request) -> dict[str, Any]:
        body = request.environ.get("google_drive.trigger.body")
        if isinstance(body, Mapping):
            return dict(body)
        return {}

    def _resolve_spaces(self) -> list[str]:
        spaces = self.runtime.subscription.properties.get("spaces") or []
        if isinstance(spaces, str):
            return [part.strip() for part in spaces.split(",") if part.strip()]
        if isinstance(spaces, Sequence):
            return [str(space) for space in spaces if str(space)]
        return ["drive"]

    def _resolve_page_token(self) -> str:
        storage = getattr(self.runtime.session, "storage", None)
        if storage:
            try:
                stored = storage.get(self._storage_key())
                if stored:
                    return stored.decode("utf-8")
            except Exception:
                pass

        token = self.runtime.subscription.properties.get("start_page_token")
        if not token:
            raise ValueError("Subscription does not include a startPageToken")
        return str(token)

    def _persist_page_token(self, token: str) -> None:
        storage = getattr(self.runtime.session, "storage", None)
        if not storage:
            return
        try:
            storage.set(self._storage_key(), str(token).encode("utf-8"))
        except Exception:
            pass

    def _storage_key(self) -> str:
        channel = self.runtime.subscription.properties.get("channel_id") or "channel"
        endpoint = self.runtime.subscription.endpoint
        return f"google-drive-trigger:last-page-token:{channel}:{endpoint}"

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
