import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class RepositoryTrigger(TriggerEvent):
    """
    GitHub Repository Event Trigger

    This unified trigger handles all GitHub repository events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub repository event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, deleted, archived, etc.)
        - visibility_filter: Filter by repository visibility
        - owner_filter: Filter by repository owner
        - name_pattern: Filter by repository name pattern
        - topics_filter: Filter by repository topics
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

        # Extract repository and sender information
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply visibility filter
        visibility_filter = parameters.get("visibility_filter", "all")
        if visibility_filter != "all":
            repo_visibility = repository.get("visibility", "public")
            repo_private = repository.get("private", False)

            # Map private flag to visibility
            if visibility_filter == "public" and (repo_private or repo_visibility == "private"):
                raise TriggerIgnoreEventError("Repository is not public")
            elif visibility_filter == "private" and (not repo_private or repo_visibility != "private"):
                raise TriggerIgnoreEventError("Repository is not private")

        # Apply owner filter
        owner_filter = parameters.get("owner_filter")
        if owner_filter:
            allowed_owners = [o.strip() for o in owner_filter.split(",")]
            repo_owner = repository.get("owner", {}).get("login", "")
            if repo_owner not in allowed_owners:
                raise TriggerIgnoreEventError(
                    f"Repository owner '{repo_owner}' not in allowed list: {allowed_owners}"
                )

        # Apply name pattern filter
        name_pattern = parameters.get("name_pattern")
        if name_pattern:
            repo_name = repository.get("name", "")
            if not fnmatch.fnmatch(repo_name, name_pattern):
                raise TriggerIgnoreEventError(
                    f"Repository name '{repo_name}' doesn't match pattern: {name_pattern}"
                )

        # Apply topics filter
        topics_filter = parameters.get("topics_filter")
        if topics_filter:
            required_topics = [t.strip() for t in topics_filter.split(",")]
            repo_topics = repository.get("topics", [])
            if not any(topic in repo_topics for topic in required_topics):
                raise TriggerIgnoreEventError(
                    f"Repository doesn't have required topics: {required_topics}"
                )

        # Extract changes information (for edited/renamed actions)
        changes_info = {}
        if changes:
            if "name" in changes:
                changes_info["name"] = {"from": changes["name"].get("from", "")}
            if "description" in changes:
                changes_info["description"] = {"from": changes["description"].get("from", "")}
            if "homepage" in changes:
                changes_info["homepage"] = {"from": changes["homepage"].get("from", "")}
            if "topics" in changes:
                changes_info["topics"] = {"from": changes["topics"].get("from", [])}

        # Build variables for the workflow
        variables = {
            "action": action,
            "repository": {
                "id": repository.get("id"),
                "name": repository.get("name", ""),
                "full_name": repository.get("full_name", ""),
                "html_url": repository.get("html_url", ""),
                "description": repository.get("description", ""),
                "private": repository.get("private", False),
                "fork": repository.get("fork", False),
                "created_at": repository.get("created_at", ""),
                "updated_at": repository.get("updated_at", ""),
                "pushed_at": repository.get("pushed_at", ""),
                "homepage": repository.get("homepage", ""),
                "size": repository.get("size", 0),
                "stargazers_count": repository.get("stargazers_count", 0),
                "watchers_count": repository.get("watchers_count", 0),
                "forks_count": repository.get("forks_count", 0),
                "language": repository.get("language", ""),
                "topics": repository.get("topics", []),
                "has_issues": repository.get("has_issues", False),
                "has_projects": repository.get("has_projects", False),
                "has_wiki": repository.get("has_wiki", False),
                "has_pages": repository.get("has_pages", False),
                "has_downloads": repository.get("has_downloads", False),
                "has_discussions": repository.get("has_discussions", False),
                "archived": repository.get("archived", False),
                "disabled": repository.get("disabled", False),
                "visibility": repository.get("visibility", "public"),
                "default_branch": repository.get("default_branch", ""),
                "owner": {
                    "login": repository.get("owner", {}).get("login", ""),
                    "avatar_url": repository.get("owner", {}).get("avatar_url", ""),
                    "html_url": repository.get("owner", {}).get("html_url", ""),
                    "type": repository.get("owner", {}).get("type", ""),
                },
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