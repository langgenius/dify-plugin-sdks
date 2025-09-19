import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class PullRequestTrigger(TriggerEvent):
    """
    GitHub Pull Request Event Trigger

    This unified trigger handles all GitHub pull request events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub pull request event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (opened, closed, edited, etc.)
        - target_branches: Filter by target branch (comma-separated, supports wildcards)
        - source_branches: Filter by source branch (comma-separated, supports wildcards)
        - labels: Filter by PR labels (comma-separated)
        - skip_draft: Skip draft PRs (default: true)
        - exclude_authors: Exclude PRs from these authors
        - file_count_limit: Ignore PRs with too many file changes
        - min_additions: Minimum lines added
        - max_additions: Maximum lines added
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

        # Extract pull request information
        pull_request = payload.get("pull_request", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Skip draft PRs if configured
        skip_draft = parameters.get("skip_draft", True)
        if skip_draft and pull_request.get("draft", False):
            # Only skip for actions that create/update the PR
            if action in ["opened", "reopened", "synchronize", "edited"]:
                raise TriggerIgnoreEventError("Skipping draft pull request")

        # Apply target branch filter
        target_branches = parameters.get("target_branches")
        if target_branches:
            target_branch = pull_request.get("base", {}).get("ref", "")
            branches = [b.strip() for b in target_branches.split(",")]
            if not any(fnmatch.fnmatch(target_branch, pattern) for pattern in branches):
                raise TriggerIgnoreEventError(
                    f"Target branch '{target_branch}' doesn't match filter: {branches}"
                )

        # Apply source branch filter
        source_branches = parameters.get("source_branches")
        if source_branches:
            source_branch = pull_request.get("head", {}).get("ref", "")
            branches = [b.strip() for b in source_branches.split(",")]
            if not any(fnmatch.fnmatch(source_branch, pattern) for pattern in branches):
                raise TriggerIgnoreEventError(
                    f"Source branch '{source_branch}' doesn't match filter: {branches}"
                )

        # Apply label filter
        labels_filter = parameters.get("labels")
        if labels_filter:
            required_labels = [l.strip() for l in labels_filter.split(",")]
            pr_labels = [label.get("name", "") for label in pull_request.get("labels", [])]
            if not any(label in pr_labels for label in required_labels):
                raise TriggerIgnoreEventError(
                    f"PR doesn't have required labels: {required_labels}"
                )

        # Apply author exclusion filter
        exclude_authors = parameters.get("exclude_authors")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",")]
            author = pull_request.get("user", {}).get("login", "")
            if author in excluded:
                raise TriggerIgnoreEventError(f"Author '{author}' is excluded")

        # Apply file count limit
        file_count_limit = parameters.get("file_count_limit")
        if file_count_limit is not None:
            changed_files = pull_request.get("changed_files", 0)
            if changed_files > int(file_count_limit):
                raise TriggerIgnoreEventError(
                    f"Too many files changed: {changed_files} > {file_count_limit}"
                )

        # Apply additions filters
        min_additions = parameters.get("min_additions")
        if min_additions is not None:
            additions = pull_request.get("additions", 0)
            if additions < int(min_additions):
                raise TriggerIgnoreEventError(
                    f"Too few additions: {additions} < {min_additions}"
                )

        max_additions = parameters.get("max_additions")
        if max_additions is not None:
            additions = pull_request.get("additions", 0)
            if additions > int(max_additions):
                raise TriggerIgnoreEventError(
                    f"Too many additions: {additions} > {max_additions}"
                )

        # Extract labels
        labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in pull_request.get("labels", [])
        ]

        # Extract assignees
        assignees = [
            {
                "login": assignee.get("login", ""),
                "avatar_url": assignee.get("avatar_url", ""),
                "html_url": assignee.get("html_url", ""),
            }
            for assignee in pull_request.get("assignees", [])
        ]

        # Extract requested reviewers (users)
        requested_reviewers = [
            {
                "login": reviewer.get("login", ""),
                "avatar_url": reviewer.get("avatar_url", ""),
                "html_url": reviewer.get("html_url", ""),
            }
            for reviewer in pull_request.get("requested_reviewers", [])
        ]

        # Extract requested teams
        requested_teams = [
            {
                "name": team.get("name", ""),
                "slug": team.get("slug", ""),
            }
            for team in pull_request.get("requested_teams", [])
        ]

        # Extract milestone information
        milestone = None
        if pull_request.get("milestone"):
            milestone = {
                "title": pull_request["milestone"].get("title", ""),
                "description": pull_request["milestone"].get("description", ""),
                "due_on": pull_request["milestone"].get("due_on", ""),
            }

        # Extract head (source) information
        head = {
            "ref": pull_request.get("head", {}).get("ref", ""),
            "sha": pull_request.get("head", {}).get("sha", ""),
            "repo": {
                "name": pull_request.get("head", {}).get("repo", {}).get("name", ""),
                "full_name": pull_request.get("head", {}).get("repo", {}).get("full_name", ""),
            } if pull_request.get("head", {}).get("repo") else None,
        }

        # Extract base (target) information
        base = {
            "ref": pull_request.get("base", {}).get("ref", ""),
            "sha": pull_request.get("base", {}).get("sha", ""),
            "repo": {
                "name": pull_request.get("base", {}).get("repo", {}).get("name", ""),
                "full_name": pull_request.get("base", {}).get("repo", {}).get("full_name", ""),
            } if pull_request.get("base", {}).get("repo") else None,
        }

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "title" in changes:
                changes_info["title"] = {"from": changes["title"].get("from", "")}
            if "body" in changes:
                changes_info["body"] = {"from": changes["body"].get("from", "")}

        # Build variables for the workflow
        variables = {
            "action": action,
            "pull_request": {
                "number": pull_request.get("number"),
                "title": pull_request.get("title", ""),
                "body": pull_request.get("body", ""),
                "state": pull_request.get("state", ""),
                "merged": pull_request.get("merged", False),
                "draft": pull_request.get("draft", False),
                "html_url": pull_request.get("html_url", ""),
                "diff_url": pull_request.get("diff_url", ""),
                "patch_url": pull_request.get("patch_url", ""),
                "created_at": pull_request.get("created_at", ""),
                "updated_at": pull_request.get("updated_at", ""),
                "closed_at": pull_request.get("closed_at", ""),
                "merged_at": pull_request.get("merged_at", ""),
                "head": head,
                "base": base,
                "user": {
                    "login": pull_request.get("user", {}).get("login", ""),
                    "avatar_url": pull_request.get("user", {}).get("avatar_url", ""),
                    "html_url": pull_request.get("user", {}).get("html_url", ""),
                },
                "labels": labels,
                "assignees": assignees,
                "requested_reviewers": requested_reviewers,
                "requested_teams": requested_teams,
                "milestone": milestone,
                "additions": pull_request.get("additions", 0),
                "deletions": pull_request.get("deletions", 0),
                "changed_files": pull_request.get("changed_files", 0),
                "commits": pull_request.get("commits", 0),
                "review_comments": pull_request.get("review_comments", 0),
                "comments": pull_request.get("comments", 0),
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