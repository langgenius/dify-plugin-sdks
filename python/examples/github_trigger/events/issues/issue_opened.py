import re
from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.errors.trigger import EventIgnoreError
from dify_plugin.interfaces.trigger import Event


class IssueOpenedEvent(Event):
    """
    GitHub Issue Opened Event

    This event transforms GitHub issue opened webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _check_title_pattern(self, issue: Mapping[str, Any], pattern: str | None) -> None:
        """Check if issue title matches the pattern"""
        if not pattern:
            return

        title = issue.get("title", "")
        if not re.match(pattern, title):
            raise EventIgnoreError()

    def _check_labels(self, issue: Mapping[str, Any], labels_param: str | None) -> None:
        """Check if issue has required labels"""
        if not labels_param:
            return

        required_labels = [label.strip() for label in labels_param.split(",") if label.strip()]
        if not required_labels:
            return

        issue_labels = [label.get("name") for label in issue.get("labels", [])]
        if not any(label in issue_labels for label in required_labels):
            raise EventIgnoreError()

    def _check_assignee(self, issue: Mapping[str, Any], assignee_param: str | None) -> None:
        """Check if issue is assigned to allowed users"""
        if not assignee_param:
            return

        allowed_assignees = [assignee.strip() for assignee in assignee_param.split(",") if assignee.strip()]
        if not allowed_assignees:
            return

        issue_assignees: list[str] = []

        # Collect assignee usernames
        single_assignee = issue.get("assignee")
        if single_assignee and single_assignee.get("login"):
            issue_assignees.append(single_assignee["login"])

        for assignee in issue.get("assignees", []):
            login = assignee.get("login")
            if login:
                issue_assignees.append(login)

        if not any(assignee in issue_assignees for assignee in allowed_assignees):
            raise EventIgnoreError()

    def _check_authors(self, issue: Mapping[str, Any], authors_param: str | None) -> None:
        """Check if issue author is in allowed list"""
        if not authors_param:
            return

        allowed_authors = [author.strip() for author in authors_param.split(",") if author.strip()]
        if not allowed_authors:
            return

        issue_author = issue.get("user", {}).get("login")
        if issue_author not in allowed_authors:
            raise EventIgnoreError()

    def _check_milestone(self, issue: Mapping[str, Any], milestone_param: str | None) -> None:
        """Check if issue milestone matches allowed milestones"""
        if not milestone_param:
            return

        allowed_milestones = [milestone.strip() for milestone in milestone_param.split(",") if milestone.strip()]
        if not allowed_milestones:
            return

        milestone = issue.get("milestone")
        if not milestone:
            raise EventIgnoreError()

        milestone_title = milestone.get("title")
        if not milestone_title or milestone_title not in allowed_milestones:
            raise EventIgnoreError()

    def _check_body_contains(self, issue: Mapping[str, Any], body_contains_param: str | None) -> None:
        """Check if issue body contains required keywords"""
        if not body_contains_param:
            return

        keywords = [keyword.strip().lower() for keyword in body_contains_param.split(",") if keyword.strip()]
        if not keywords:
            return

        issue_body = (issue.get("body") or "").lower()
        if not any(keyword in issue_body for keyword in keywords):
            raise EventIgnoreError()

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub issue opened webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_title_pattern(issue, parameters.get("title_pattern"))
        self._check_labels(issue, parameters.get("labels"))
        self._check_assignee(issue, parameters.get("assignee"))
        self._check_authors(issue, parameters.get("authors"))
        self._check_milestone(issue, parameters.get("milestone"))
        self._check_body_contains(issue, parameters.get("body_contains"))

        return Variables(variables={**payload})
