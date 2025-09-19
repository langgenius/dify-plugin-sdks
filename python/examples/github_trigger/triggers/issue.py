import fnmatch
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueTrigger(TriggerEvent):
    """
    GitHub Issue Event Trigger

    This unified trigger handles all GitHub issue events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (opened, closed, edited, etc.)
        - labels_filter: Filter by required labels (comma-separated)
        - exclude_labels: Exclude issues with these labels
        - assignee_filter: Filter by assignees
        - author_filter: Filter by authors
        - exclude_authors: Exclude issues from these authors
        - milestone_filter: Filter by milestones
        - title_pattern: Filter by title pattern (supports wildcards)
        - body_contains: Filter by body keywords
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

        # Extract issue information
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})
        label = payload.get("label", {})  # For labeled/unlabeled actions

        # Apply labels filter
        labels_filter = parameters.get("labels_filter")
        if labels_filter:
            required_labels = [l.strip() for l in labels_filter.split(",")]
            issue_labels = [label.get("name", "") for label in issue.get("labels", [])]
            if not any(label in issue_labels for label in required_labels):
                raise TriggerIgnoreEventError(
                    f"Issue doesn't have required labels: {required_labels}"
                )

        # Apply exclude labels filter
        exclude_labels = parameters.get("exclude_labels")
        if exclude_labels:
            excluded = [l.strip() for l in exclude_labels.split(",")]
            issue_labels = [label.get("name", "") for label in issue.get("labels", [])]
            if any(label in issue_labels for label in excluded):
                raise TriggerIgnoreEventError(
                    f"Issue has excluded labels: {excluded}"
                )

        # Apply assignee filter
        assignee_filter = parameters.get("assignee_filter")
        if assignee_filter:
            required_assignees = [a.strip() for a in assignee_filter.split(",")]
            issue_assignees = [
                assignee.get("login", "") for assignee in issue.get("assignees", [])
            ]
            if not any(assignee in issue_assignees for assignee in required_assignees):
                raise TriggerIgnoreEventError(
                    f"Issue not assigned to required users: {required_assignees}"
                )

        # Apply author filter
        author_filter = parameters.get("author_filter")
        if author_filter:
            allowed_authors = [a.strip() for a in author_filter.split(",")]
            issue_author = issue.get("user", {}).get("login", "")
            if issue_author not in allowed_authors:
                raise TriggerIgnoreEventError(
                    f"Issue author '{issue_author}' not in allowed list: {allowed_authors}"
                )

        # Apply exclude authors filter
        exclude_authors = parameters.get("exclude_authors")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",")]
            issue_author = issue.get("user", {}).get("login", "")
            if issue_author in excluded:
                raise TriggerIgnoreEventError(
                    f"Issue author '{issue_author}' is excluded"
                )

        # Apply milestone filter
        milestone_filter = parameters.get("milestone_filter")
        if milestone_filter:
            required_milestones = [m.strip() for m in milestone_filter.split(",")]
            issue_milestone = issue.get("milestone", {}).get("title", "")
            if issue_milestone and issue_milestone not in required_milestones:
                raise TriggerIgnoreEventError(
                    f"Issue milestone '{issue_milestone}' not in required list: {required_milestones}"
                )

        # Apply title pattern filter
        title_pattern = parameters.get("title_pattern")
        if title_pattern:
            issue_title = issue.get("title", "")
            if not fnmatch.fnmatch(issue_title, title_pattern):
                raise TriggerIgnoreEventError(
                    f"Issue title doesn't match pattern: {title_pattern}"
                )

        # Apply body contains filter
        body_contains = parameters.get("body_contains")
        if body_contains:
            keywords = [k.strip().lower() for k in body_contains.split(",")]
            issue_body = (issue.get("body") or "").lower()
            if not any(keyword in issue_body for keyword in keywords):
                raise TriggerIgnoreEventError(
                    f"Issue body doesn't contain required keywords: {keywords}"
                )

        # Extract labels
        labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in issue.get("labels", [])
        ]

        # Extract assignees
        assignees = [
            {
                "login": assignee.get("login", ""),
                "avatar_url": assignee.get("avatar_url", ""),
                "html_url": assignee.get("html_url", ""),
            }
            for assignee in issue.get("assignees", [])
        ]

        # Extract primary assignee (deprecated but included for compatibility)
        primary_assignee = None
        if issue.get("assignee"):
            primary_assignee = {
                "login": issue["assignee"].get("login", ""),
                "avatar_url": issue["assignee"].get("avatar_url", ""),
                "html_url": issue["assignee"].get("html_url", ""),
            }

        # Extract milestone information
        milestone = None
        if issue.get("milestone"):
            milestone = {
                "title": issue["milestone"].get("title", ""),
                "description": issue["milestone"].get("description", ""),
                "due_on": issue["milestone"].get("due_on", ""),
                "state": issue["milestone"].get("state", ""),
            }

        # Extract reactions
        reactions = None
        if issue.get("reactions"):
            reactions = {
                "total_count": issue["reactions"].get("total_count", 0),
            }

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "title" in changes:
                changes_info["title"] = {"from": changes["title"].get("from", "")}
            if "body" in changes:
                changes_info["body"] = {"from": changes["body"].get("from", "")}

        # Extract label information (for labeled/unlabeled actions)
        label_info = None
        if label and action in ["labeled", "unlabeled"]:
            label_info = {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }

        # Build variables for the workflow
        variables = {
            "action": action,
            "issue": {
                "number": issue.get("number"),
                "title": issue.get("title", ""),
                "body": issue.get("body", ""),
                "state": issue.get("state", ""),
                "locked": issue.get("locked", False),
                "html_url": issue.get("html_url", ""),
                "created_at": issue.get("created_at", ""),
                "updated_at": issue.get("updated_at", ""),
                "closed_at": issue.get("closed_at", ""),
                "user": {
                    "login": issue.get("user", {}).get("login", ""),
                    "avatar_url": issue.get("user", {}).get("avatar_url", ""),
                    "html_url": issue.get("user", {}).get("html_url", ""),
                },
                "labels": labels,
                "assignees": assignees,
                "assignee": primary_assignee,
                "milestone": milestone,
                "comments": issue.get("comments", 0),
                "reactions": reactions,
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

        # Add label info if present
        if label_info:
            variables["label"] = label_info

        return Event(variables=variables)