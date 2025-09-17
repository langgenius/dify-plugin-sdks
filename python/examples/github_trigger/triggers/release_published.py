from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.interfaces.trigger import TriggerEvent


class ReleasePublishedTrigger(TriggerEvent):
    """
    GitHub Release Published Event Trigger

    This trigger handles GitHub release published events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub release published event trigger

        Parameters:
        - tag_filter: Filter by specific release tag (optional)
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a published action
        action = payload.get("action", "")
        if action != "published":
            # This trigger only handles published events
            return Event(variables={})

        # Extract release information
        release = payload.get("release", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply tag filter if specified
        tag_filter = parameters.get("tag_filter")
        if tag_filter is not None:
            tag_name = release.get("tag_name", "")
            if tag_name != tag_filter:
                # Skip this event if it doesn't match the tag filter
                return Event(variables={})

        # Extract assets information
        assets = []
        for asset in release.get("assets", []):
            assets.append({
                "name": asset.get("name", ""),
                "label": asset.get("label", ""),
                "content_type": asset.get("content_type", ""),
                "size": asset.get("size", 0),
                "download_count": asset.get("download_count", 0),
                "browser_download_url": asset.get("browser_download_url", ""),
                "created_at": asset.get("created_at", ""),
                "updated_at": asset.get("updated_at", ""),
            })

        # Build variables for the workflow
        variables = {
            "release": {
                "id": release.get("id"),
                "tag_name": release.get("tag_name", ""),
                "target_commitish": release.get("target_commitish", ""),
                "name": release.get("name", ""),
                "body": release.get("body", ""),
                "draft": release.get("draft", False),
                "prerelease": release.get("prerelease", False),
                "created_at": release.get("created_at", ""),
                "published_at": release.get("published_at", ""),
                "html_url": release.get("html_url", ""),
                "tarball_url": release.get("tarball_url", ""),
                "zipball_url": release.get("zipball_url", ""),
                "assets": assets,
                "author": {
                    "login": release.get("author", {}).get("login", ""),
                    "avatar_url": release.get("author", {}).get("avatar_url", ""),
                    "html_url": release.get("author", {}).get("html_url", ""),
                },
            },
            "repository": {
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "owner": {
                    "login": repository.get("owner", {}).get("login", ""),
                    "avatar_url": repository.get("owner", {}).get("avatar_url", ""),
                    "html_url": repository.get("owner", {}).get("html_url", ""),
                },
            },
            "sender": {
                "login": sender.get("login", ""),
                "avatar_url": sender.get("avatar_url", ""),
                "html_url": sender.get("html_url", ""),
                "type": sender.get("type", ""),
            },
        }

        return Event(variables=variables)