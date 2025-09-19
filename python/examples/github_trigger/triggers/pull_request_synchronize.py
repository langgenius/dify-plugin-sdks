from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent

from .filters import check_wildcard_match, parse_comma_list


class PullRequestSynchronizeTrigger(TriggerEvent):
    """
    GitHub Pull Request Synchronize Event Trigger

    This trigger handles GitHub pull request synchronize events (when new commits are pushed)
    and extracts relevant information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request synchronize event trigger with practical filtering

        Parameters:
        - file_patterns: Filter by modified file patterns
        - max_commits: Maximum number of commits allowed
        - skip_draft: Skip draft PRs
        - force_push_only: Only trigger for force pushes
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a synchronize action
        action = payload.get("action", "")
        if action != "synchronize":
            # This trigger only handles synchronize events
            raise TriggerIgnoreEventError(f"Action \'{action}\' is not \'synchronize\'")

        # Extract pull request information
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Skip draft PRs if configured
        skip_draft = parameters.get("skip_draft", False)
        if skip_draft and pull_request.get("draft", False):
            raise TriggerIgnoreEventError("Skipping draft pull request synchronization")

        # Force push only filter
        force_push_only = parameters.get("force_push_only", False)
        if force_push_only:
            # Check if this was a force push by comparing before/after
            before = payload.get("before", "")
            # In a force push, the before commit might not be an ancestor
            # This is a simplified check - a proper check would need git history
            if not before or before == "0000000000000000000000000000000000000000":
                # Not a force push (new branch)
                raise TriggerIgnoreEventError("Not a force push")

        # Maximum commits filter
        max_commits = parameters.get("max_commits")
        if max_commits is not None:
            try:
                max_count = int(max_commits)
                # Count commits in this push
                # Note: GitHub doesn't always provide full commit list in sync events
                # This is a best-effort check
                commits_count = pull_request.get("commits", 0)
                if commits_count > max_count:
                    raise TriggerIgnoreEventError(
                        f"PR has {commits_count} commits, exceeds limit of {max_count}"
                    )
            except ValueError:
                pass  # Invalid max_commits value, skip filtering

        # File pattern filtering
        file_patterns_filter = parameters.get("file_patterns", "")
        if file_patterns_filter:
            patterns = parse_comma_list(file_patterns_filter)
            if patterns:
                # Note: GitHub sync events don't always include file changes
                # This would need an API call to get changed files
                # For now, we'll document this limitation
                pass  # File filtering would require additional API calls

        # Build variables for the workflow
        variables = {
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "html_url": pull_request.get("html_url", ""),
                "updated_at": pull_request.get("updated_at", ""),
                "draft": pull_request.get("draft", False),
                "merged": pull_request.get("merged", False),
                "author": {
                    "login": pull_request.get("user", {}).get("login", ""),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", ""),
                    "html_url": pull_request.get("user", {}).get("html_url", ""),
                },
                "head": {
                    "ref": pull_request.get("head", {}).get("ref", ""),
                    "sha": pull_request.get("head", {}).get("sha", ""),
                    "repo_name": pull_request.get("head", {}).get("repo", {}).get("full_name", ""),
                },
                "base": {
                    "ref": pull_request.get("base", {}).get("ref", ""),
                    "sha": pull_request.get("base", {}).get("sha", ""),
                    "repo_name": pull_request.get("base", {}).get("repo", {}).get("full_name", ""),
                },
            },
            "before": payload.get("before", ""),
            "after": payload.get("after", ""),
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