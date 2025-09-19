import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PackageTrigger(TriggerEvent):
    """
    GitHub Package Event Trigger

    This unified trigger handles all GitHub package events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub package event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (published, updated)
        - package_type_filter: Filter by package type (npm, maven, docker, etc.)
        - package_name_filter: Filter by package names (supports wildcards)
        - version_pattern: Filter by version pattern (supports wildcards)
        - exclude_prereleases: Exclude pre-release versions
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

        # Extract package information
        package = payload.get("package", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Apply package type filter
        package_type_filter = parameters.get("package_type_filter")
        if package_type_filter:
            package_type = package.get("package_type", "")
            if package_type != package_type_filter:
                raise TriggerIgnoreEventError(
                    f"Package type '{package_type}' doesn't match required type '{package_type_filter}'"
                )

        # Apply package name filter
        package_name_filter = parameters.get("package_name_filter")
        if package_name_filter:
            name_patterns = [n.strip() for n in package_name_filter.split(",") if n.strip()]
            package_name = package.get("name", "")
            name_matched = False
            for pattern in name_patterns:
                if fnmatch.fnmatch(package_name, pattern):
                    name_matched = True
                    break
            if not name_matched:
                raise TriggerIgnoreEventError(
                    f"Package name '{package_name}' doesn't match patterns: {name_patterns}"
                )

        # Apply version pattern filter
        version_pattern = parameters.get("version_pattern")
        if version_pattern:
            version_info = package.get("package_version", {})
            version_string = version_info.get("version", "")
            if not fnmatch.fnmatch(version_string, version_pattern):
                raise TriggerIgnoreEventError(
                    f"Version '{version_string}' doesn't match pattern: {version_pattern}"
                )

        # Apply exclude prereleases filter
        exclude_prereleases = parameters.get("exclude_prereleases", False)
        if exclude_prereleases:
            version_info = package.get("package_version", {})
            release_info = version_info.get("release", {})
            is_prerelease = release_info.get("prerelease", False)
            if is_prerelease:
                raise TriggerIgnoreEventError("Excluding pre-release version")

        # Extract package version information
        version_info = package.get("package_version", {})
        release_info = version_info.get("release", {})
        package_files = []
        for file_info in version_info.get("package_files", []):
            package_files.append({
                "download_url": file_info.get("download_url", ""),
                "id": file_info.get("id"),
                "name": file_info.get("name", ""),
                "sha256": file_info.get("sha256", ""),
                "sha1": file_info.get("sha1", ""),
                "md5": file_info.get("md5", ""),
                "content_type": file_info.get("content_type", ""),
                "state": file_info.get("state", ""),
                "size": file_info.get("size", 0),
                "created_at": file_info.get("created_at", ""),
                "updated_at": file_info.get("updated_at", ""),
            })

        # Build variables for the workflow
        variables = {
            "action": action,
            "package": {
                "id": package.get("id"),
                "name": package.get("name", ""),
                "package_type": package.get("package_type", ""),
                "owner": {
                    "login": package.get("owner", {}).get("login", ""),
                    "id": package.get("owner", {}).get("id"),
                    "avatar_url": package.get("owner", {}).get("avatar_url", ""),
                    "html_url": package.get("owner", {}).get("html_url", ""),
                },
                "version": {
                    "id": version_info.get("id"),
                    "version": version_info.get("version", ""),
                    "summary": version_info.get("summary", ""),
                    "description": version_info.get("description", ""),
                    "body": version_info.get("body", ""),
                    "body_html": version_info.get("body_html", ""),
                    "release": {
                        "url": release_info.get("url", ""),
                        "html_url": release_info.get("html_url", ""),
                        "id": release_info.get("id"),
                        "tag_name": release_info.get("tag_name", ""),
                        "target_commitish": release_info.get("target_commitish", ""),
                        "name": release_info.get("name", ""),
                        "draft": release_info.get("draft", False),
                        "prerelease": release_info.get("prerelease", False),
                        "created_at": release_info.get("created_at", ""),
                        "published_at": release_info.get("published_at", ""),
                    },
                    "package_files": package_files,
                    "author": {
                        "login": version_info.get("author", {}).get("login", ""),
                        "id": version_info.get("author", {}).get("id"),
                        "avatar_url": version_info.get("author", {}).get("avatar_url", ""),
                        "html_url": version_info.get("author", {}).get("html_url", ""),
                    },
                    "installation_command": version_info.get("installation_command", ""),
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