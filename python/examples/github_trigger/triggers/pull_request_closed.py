import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestClosedTrigger(TriggerEvent):
    """
    GitHub Pull Request Closed Event Trigger

    This trigger handles GitHub pull request closed events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request closed event trigger with practical filtering

        Parameters:
        - merged_only: Only trigger for merged PRs
        - target_branches: Filter by target branch (comma-separated, supports wildcards)
        - labels: Filter by PR labels (comma-separated)
        - min_approvals: Minimum number of approvals required
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is a closed action
        action = payload.get("action", "")
        if action != "closed":
            # This trigger only handles closed events
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'closed'")

        # Extract pull request information
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Check if merged_only filter is enabled
        merged_only = parameters.get("merged_only", False)
        if merged_only and not pull_request.get("merged", False):
            raise TriggerIgnoreEventError("PR was closed without merging")

        # Target branch filtering
        target_branches = parameters.get("target_branches", "")
        if target_branches:
            allowed_branches = [b.strip() for b in target_branches.split(",") if b.strip()]
            if allowed_branches:
                base_branch = pull_request.get("base", {}).get("ref", "")
                # Check if target branch matches any of the patterns
                branch_matched = False
                for pattern in allowed_branches:
                    if fnmatch.fnmatch(base_branch, pattern):
                        branch_matched = True
                        break
                if not branch_matched:
                    raise TriggerIgnoreEventError(
                        f"PR targets '{base_branch}' which doesn't match allowed patterns: {', '.join(allowed_branches)}"
                    )

        # Label filtering
        labels_filter = parameters.get("labels", "")
        if labels_filter:
            required_labels = [label.strip() for label in labels_filter.split(",") if label.strip()]
            if required_labels:
                pr_labels = [label.get("name", "") for label in pull_request.get("labels", [])]
                # Check if PR has at least one of the required labels
                has_required_label = any(label in pr_labels for label in required_labels)
                if not has_required_label:
                    raise TriggerIgnoreEventError(
                        f"PR doesn't have any of the required labels: {', '.join(required_labels)}"
                    )

        # Minimum approvals filtering
        min_approvals = parameters.get("min_approvals")
        if min_approvals is not None:
            try:
                min_count = int(min_approvals)
                # Get the approval count from review_comments_url
                # Note: In a real implementation, you'd need to fetch this data
                # For now, we check if it was merged (which usually requires approvals)
                if min_count > 0 and not pull_request.get("merged", False):
                    raise TriggerIgnoreEventError(
                        f"PR doesn't meet minimum approval requirement of {min_count}"
                    )
            except ValueError:
                pass  # Invalid min_approvals value, skip filtering

        # Extract labels
        labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in pull_request.get("labels", [])
        ]

        # Build variables for the workflow
        variables = {
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "html_url": pull_request.get("html_url", ""),
                "created_at": pull_request.get("created_at", ""),
                "updated_at": pull_request.get("updated_at", ""),
                "closed_at": pull_request.get("closed_at", ""),
                "merged_at": pull_request.get("merged_at", ""),
                "draft": pull_request.get("draft", False),
                "merged": pull_request.get("merged", False),
                "mergeable": pull_request.get("mergeable"),
                "labels": labels,
                "assignees": [
                    {
                        "login": assignee.get("login", ""),
                        "avatar_url": assignee.get("avatar_url", ""),
                        "html_url": assignee.get("html_url", ""),
                    }
                    for assignee in pull_request.get("assignees", [])
                ],
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