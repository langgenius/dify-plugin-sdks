import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class ReleasePublishedTrigger(TriggerEvent):
    """
    GitHub Release Published Event Trigger

    This trigger handles GitHub release published events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub release published event trigger with practical filtering

        Parameters:
        - prerelease_filter: Filter prereleases (exclude/only)
        - tag_pattern: Filter by tag patterns with wildcards
        - required_assets: Require specific assets to be present
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a published action
        action = payload.get("action", "")
        if action != "published":
            # This trigger only handles published events
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'published'")

        # Extract release information
        release = payload.get("release", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Prerelease filtering
        prerelease_filter = parameters.get("prerelease_filter")
        if prerelease_filter:
            is_prerelease = release.get("prerelease", False)
            if prerelease_filter == "exclude" and is_prerelease:
                raise TriggerIgnoreEventError("Ignoring prerelease")
            elif prerelease_filter == "only" and not is_prerelease:
                raise TriggerIgnoreEventError("Only prereleases are allowed")

        # Tag pattern filtering with wildcards
        tag_pattern_filter = parameters.get("tag_pattern", "")
        if tag_pattern_filter:
            allowed_patterns = [p.strip() for p in tag_pattern_filter.split(",") if p.strip()]
            if allowed_patterns:
                tag_name = release.get("tag_name", "")
                # Check if tag matches any of the patterns
                tag_matched = False
                for pattern in allowed_patterns:
                    if fnmatch.fnmatch(tag_name, pattern):
                        tag_matched = True
                        break
                if not tag_matched:
                    raise TriggerIgnoreEventError(
                        f"Tag '{tag_name}' doesn't match allowed patterns: {', '.join(allowed_patterns)}"
                    )

        # Required assets filtering
        required_assets_filter = parameters.get("required_assets", "")
        if required_assets_filter:
            required_patterns = [a.strip() for a in required_assets_filter.split(",") if a.strip()]
            if required_patterns:
                release_assets = release.get("assets", [])
                asset_names = [asset.get("name", "") for asset in release_assets]

                # Check if all required assets are present
                missing_assets = []
                for pattern in required_patterns:
                    # Check if any asset matches this pattern
                    pattern_matched = False
                    for asset_name in asset_names:
                        if fnmatch.fnmatch(asset_name, pattern):
                            pattern_matched = True
                            break
                    if not pattern_matched:
                        missing_assets.append(pattern)

                if missing_assets:
                    raise TriggerIgnoreEventError(
                        f"Release missing required assets: {', '.join(missing_assets)}"
                    )

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