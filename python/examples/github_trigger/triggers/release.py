import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class ReleaseTrigger(TriggerEvent):
    """
    GitHub Release Event Trigger

    This unified trigger handles all GitHub release events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub release event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, published, deleted, etc.)
        - prerelease_filter: Filter prereleases (exclude/only)
        - draft_filter: Filter draft releases (exclude/only)
        - tag_pattern: Filter by tag patterns with wildcards
        - required_assets: Require specific assets to be present
        - exclude_authors: Exclude releases from these authors
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Get the action type
        action = payload.get("action", "")

        # Apply action filter
        action_filter = parameters.get("action_filter", [])
        if action_filter and action not in action_filter:
            raise TriggerIgnoreEventError(
                f"Action '{action}' not in filter list: {action_filter}"
            )

        # Extract release information
        release = payload.get("release", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply prerelease filter
        prerelease_filter = parameters.get("prerelease_filter")
        if prerelease_filter:
            is_prerelease = release.get("prerelease", False)
            if prerelease_filter == "exclude" and is_prerelease:
                raise TriggerIgnoreEventError("Ignoring prerelease")
            elif prerelease_filter == "only" and not is_prerelease:
                raise TriggerIgnoreEventError("Only prereleases are allowed")

        # Apply draft filter
        draft_filter = parameters.get("draft_filter")
        if draft_filter:
            is_draft = release.get("draft", False)
            if draft_filter == "exclude" and is_draft:
                raise TriggerIgnoreEventError("Ignoring draft release")
            elif draft_filter == "only" and not is_draft:
                raise TriggerIgnoreEventError("Only draft releases are allowed")

        # Apply tag pattern filter
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

        # Apply required assets filter
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
                    raise TriggerIgnoreEventError(f"Release missing required assets: {', '.join(missing_assets)}")

        # Apply author exclusion filter
        exclude_authors = parameters.get("exclude_authors")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",")]
            author = release.get("author", {}).get("login", "")
            if author in excluded:
                raise TriggerIgnoreEventError(f"Author '{author}' is excluded")

        # Extract assets information
        assets = []
        for asset in release.get("assets", []):
            assets.append(
                {
                    "name": asset.get("name", ""),
                    "label": asset.get("label", ""),
                    "content_type": asset.get("content_type", ""),
                    "size": asset.get("size", 0),
                    "download_count": asset.get("download_count", 0),
                    "browser_download_url": asset.get("browser_download_url", ""),
                    "created_at": asset.get("created_at", ""),
                    "updated_at": asset.get("updated_at", ""),
                }
            )

        # Extract author information
        author = None
        if release.get("author"):
            author = {
                "login": release["author"].get("login", ""),
                "avatar_url": release["author"].get("avatar_url", ""),
                "html_url": release["author"].get("html_url", ""),
            }

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "name" in changes:
                changes_info["name"] = {"from": changes["name"].get("from", "")}
            if "body" in changes:
                changes_info["body"] = {"from": changes["body"].get("from", "")}

        # Build variables for the workflow
        variables = {
            "action": action,
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
                "author": author,
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
                "default_branch": repository.get("default_branch", ""),
            },
            "sender": {
                "login": sender.get("login", ""),
                "avatar_url": sender.get("avatar_url", ""),
                "html_url": sender.get("html_url", ""),
                "type": sender.get("type", ""),
            },
        }

        # Add changes info if present
        if changes_info:
            variables["changes"] = changes_info

        return Event(variables=variables)