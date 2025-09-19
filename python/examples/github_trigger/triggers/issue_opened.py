from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class IssueOpenedTrigger(TriggerEvent):
    """
    GitHub Issue Opened Event Trigger

    This trigger handles GitHub issue opened events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub issue opened event trigger with practical filtering

        Parameters:
        - labels: Filter by issue labels (comma-separated)
        - exclude_authors: Exclude issues from these authors
        - title_keywords: Only trigger if title contains these keywords
        - body_keywords: Only trigger if body contains these keywords
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

        # Extract issue information
        issue = payload.get("issue", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})

        # Author filtering
        exclude_authors = parameters.get("exclude_authors", "")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",") if a.strip()]
            author = issue.get("user", {}).get("login", "")
            if author in excluded:
                raise TriggerIgnoreEventError(f"Issue created by excluded author: {author}")

        # Label filtering
        labels_filter = parameters.get("labels", "")
        if labels_filter:
            required_labels = [l.strip() for l in labels_filter.split(",") if l.strip()]
            if required_labels:
                issue_labels = [label.get("name", "") for label in issue.get("labels", [])]
                # Check if issue has at least one of the required labels
                has_required_label = any(label in issue_labels for label in required_labels)
                if not has_required_label:
                    raise TriggerIgnoreEventError(
                        f"Issue doesn't have any of the required labels: {', '.join(required_labels)}"
                    )

        # Title keyword filtering
        title_keywords = parameters.get("title_keywords", "")
        if title_keywords:
            keywords = [k.strip().lower() for k in title_keywords.split(",") if k.strip()]
            if keywords:
                title = issue.get("title", "").lower()
                has_keyword = any(keyword in title for keyword in keywords)
                if not has_keyword:
                    raise TriggerIgnoreEventError(
                        f"Issue title doesn't contain any required keywords: {', '.join(keywords)}"
                    )

        # Body keyword filtering
        body_keywords = parameters.get("body_keywords", "")
        if body_keywords:
            keywords = [k.strip().lower() for k in body_keywords.split(",") if k.strip()]
            if keywords:
                body = (issue.get("body") or "").lower()
                has_keyword = any(keyword in body for keyword in keywords)
                if not has_keyword:
                    raise TriggerIgnoreEventError(
                        f"Issue body doesn't contain any required keywords: {', '.join(keywords)}"
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

        # Build variables for the workflow
        variables = {
            "issue": {
                "number": issue.get("number"),
                "title": issue.get("title", ""),
                "body": issue.get("body", ""),
                "state": issue.get("state", ""),
                "html_url": issue.get("html_url", ""),
                "created_at": issue.get("created_at", ""),
                "labels": labels,
                "assignees": [
                    {
                        "login": assignee.get("login", ""),
                        "avatar_url": assignee.get("avatar_url", ""),
                        "html_url": assignee.get("html_url", ""),
                    }
                    for assignee in issue.get("assignees", [])
                ],
                "author": {
                    "login": issue.get("user", {}).get("login", ""),
                    "avatar_url": issue.get("user", {}).get("avatar_url", ""),
                    "html_url": issue.get("user", {}).get("html_url", ""),
                },
                "milestone": {
                    "title": issue.get("milestone", {}).get("title", "") if issue.get("milestone") else "",
                    "description": issue.get("milestone", {}).get("description", "") if issue.get("milestone") else "",
                    "due_on": issue.get("milestone", {}).get("due_on", "") if issue.get("milestone") else "",
                } if issue.get("milestone") else None,
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