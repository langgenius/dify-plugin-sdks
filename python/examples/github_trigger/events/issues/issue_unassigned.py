from collections.abc import Mapping
import re
from typing import Any

from dify_plugin.errors.trigger import EventIgnoreError
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class IssueUnassignedEvent(Event):
    """
    GitHub Issue Unassigned Event

    This event transforms GitHub issue unassigned webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    The payload includes an 'assignee' object with the user who was unassigned.
    """

    def _check_unassigned_from(self, payload: Mapping[str, Any], unassigned_from_param: str | None) -> None:
        """Check if the unassignee matches the allowed users"""
        if not unassigned_from_param:
            return

        allowed_unassignees = [unassignee.strip() for unassignee in unassigned_from_param.split(",") if unassignee.strip()]
        if not allowed_unassignees:
            return

        # The payload contains the assignee who was unassigned
        assignee = payload.get("assignee", {})
        assignee_login = assignee.get("login", "")

        if assignee_login not in allowed_unassignees:
            raise EventIgnoreError()

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

    def _check_unassigner(self, payload: Mapping[str, Any], unassigner_param: str | None) -> None:
        """Check if the user who unassigned the issue is in allowed list"""
        if not unassigner_param:
            return

        allowed_unassigners = [unassigner.strip() for unassigner in unassigner_param.split(",") if unassigner.strip()]
        if not allowed_unassigners:
            return

        unassigner = payload.get("sender", {}).get("login")
        if unassigner not in allowed_unassigners:
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

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub issue unassigned webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_unassigned_from(payload, parameters.get("unassigned_from"))
        self._check_title_pattern(issue, parameters.get("title_pattern"))
        self._check_labels(issue, parameters.get("labels"))
        self._check_unassigner(payload, parameters.get("unassigner"))
        self._check_milestone(issue, parameters.get("milestone"))

        return Variables(variables={**payload})
