import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestOpenedTrigger(TriggerEvent):
    """
    GitHub Pull Request Opened Event Trigger

    This trigger handles GitHub pull request opened events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request opened event trigger with practical filtering

        Parameters:
        - target_branches: Filter by target branch (comma-separated, supports wildcards)
        - labels: Filter by PR labels (comma-separated)
        - skip_draft: Skip draft PRs (default: true)
        - exclude_authors: Exclude PRs from these authors
        - file_count_limit: Ignore PRs with too many file changes
        """
        # Get the event payload
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        # Verify this is an opened action
        action = payload.get("action", "")
        if action != "opened":
            # This trigger only handles opened events
            raise TriggerIgnoreEventError(f"Action '{action}' is not 'opened'")

        # Extract pull request information
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Skip draft PRs if configured
        skip_draft = parameters.get("skip_draft", True)
        if skip_draft and pull_request.get("draft", False):
            raise TriggerIgnoreEventError("Skipping draft pull request")

        # Author filtering
        exclude_authors = parameters.get("exclude_authors", "")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",") if a.strip()]
            author = pull_request.get("user", {}).get("login", "")
            if author in excluded:
                raise TriggerIgnoreEventError(f"PR created by excluded author: {author}")

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

        # File count filtering
        file_count_limit = parameters.get("file_count_limit")
        if file_count_limit is not None:
            try:
                limit = int(file_count_limit)
                changed_files = pull_request.get("changed_files", 0)
                if changed_files > limit:
                    raise TriggerIgnoreEventError(
                        f"PR changes {changed_files} files, exceeds limit of {limit}"
                    )
            except ValueError:
                pass  # Invalid limit value, skip filtering

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
                "draft": pull_request.get("draft", False),
                "mergeable": pull_request.get("mergeable"),
                "mergeable_state": pull_request.get("mergeable_state", ""),
                "changed_files": pull_request.get("changed_files", 0),
                "additions": pull_request.get("additions", 0),
                "deletions": pull_request.get("deletions", 0),
                "labels": labels,
                "head": {
                    "ref": pull_request.get("head", {}).get("ref", ""),
                    "sha": pull_request.get("head", {}).get("sha", ""),
                    "repo": {
                        "name": pull_request.get("head", {}).get("repo", {}).get("name", "") if pull_request.get("head", {}).get("repo") else "",
                        "full_name": pull_request.get("head", {}).get("repo", {}).get("full_name", "") if pull_request.get("head", {}).get("repo") else "",
                    } if pull_request.get("head", {}).get("repo") else None,
                },
                "base": {
                    "ref": pull_request.get("base", {}).get("ref", ""),
                    "sha": pull_request.get("base", {}).get("sha", ""),
                    "repo": {
                        "name": pull_request.get("base", {}).get("repo", {}).get("name", "") if pull_request.get("base", {}).get("repo") else "",
                        "full_name": pull_request.get("base", {}).get("repo", {}).get("full_name", "") if pull_request.get("base", {}).get("repo") else "",
                    } if pull_request.get("base", {}).get("repo") else None,
                },
                "author": {
                    "login": pull_request.get("user", {}).get("login", ""),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", ""),
                    "html_url": pull_request.get("user", {}).get("html_url", ""),
                },
                "assignees": [
                    {
                        "login": assignee.get("login", ""),
                        "avatar_url": assignee.get("avatar_url", ""),
                        "html_url": assignee.get("html_url", ""),
                    }
                    for assignee in pull_request.get("assignees", [])
                ],
                "requested_reviewers": [
                    {
                        "login": reviewer.get("login", ""),
                        "avatar_url": reviewer.get("avatar_url", ""),
                        "html_url": reviewer.get("html_url", ""),
                    }
                    for reviewer in pull_request.get("requested_reviewers", [])
                ],
                "milestone": {
                    "title": pull_request.get("milestone", {}).get("title", "") if pull_request.get("milestone") else "",
                    "description": pull_request.get("milestone", {}).get("description", "") if pull_request.get("milestone") else "",
                    "due_on": pull_request.get("milestone", {}).get("due_on", "") if pull_request.get("milestone") else "",
                } if pull_request.get("milestone") else None,
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