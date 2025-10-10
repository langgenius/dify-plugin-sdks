from collections.abc import Mapping
import re
from typing import Any

from dify_plugin.errors.trigger import EventIgnoreError
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class IssueCommentCreatedEvent(Event):
    """
    GitHub Issue Comment Created Event

    This event transforms GitHub issue comment created webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    Works for both issue comments and pull request comments.
    """

    def _check_comment_body_contains(self, comment: Mapping[str, Any], body_contains_param: str | None) -> None:
        """Check if comment body contains required keywords"""
        if not body_contains_param:
            return

        keywords = [keyword.strip().lower() for keyword in body_contains_param.split(",") if keyword.strip()]
        if not keywords:
            return

        comment_body = (comment.get("body") or "").lower()
        if not any(keyword in comment_body for keyword in keywords):
            raise EventIgnoreError()

    def _check_commenter(self, payload: Mapping[str, Any], commenter_param: str | None) -> None:
        """Check if the commenter is in allowed list"""
        if not commenter_param:
            return

        allowed_commenters = [commenter.strip() for commenter in commenter_param.split(",") if commenter.strip()]
        if not allowed_commenters:
            return

        commenter = payload.get("comment", {}).get("user", {}).get("login")
        if commenter not in allowed_commenters:
            raise EventIgnoreError()

    def _check_issue_labels(self, issue: Mapping[str, Any], labels_param: str | None) -> None:
        """Check if issue has required labels"""
        if not labels_param:
            return

        required_labels = [label.strip() for label in labels_param.split(",") if label.strip()]
        if not required_labels:
            return

        issue_labels = [label.get("name") for label in issue.get("labels", [])]
        if not any(label in issue_labels for label in required_labels):
            raise EventIgnoreError()

    def _check_issue_state(self, issue: Mapping[str, Any], state_param: str | None) -> None:
        """Check if issue state matches the filter"""
        if not state_param:
            return

        issue_state = issue.get("state", "").lower()
        if issue_state != state_param.lower():
            raise EventIgnoreError()

    def _check_is_pull_request(self, issue: Mapping[str, Any], is_pr_param: bool | None) -> None:
        """Check if comment is on a pull request"""
        if is_pr_param is None:
            return

        # Issue has a pull_request key if it's actually a PR
        has_pr_key = "pull_request" in issue

        if is_pr_param != has_pr_key:
            raise EventIgnoreError()

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub issue comment created webhook event into structured Variables
        """
        payload = request.get_json()
        if not payload:
            raise ValueError("No payload received")

        comment = payload.get("comment")
        if not comment:
            raise ValueError("No comment data in payload")

        issue = payload.get("issue")
        if not issue:
            raise ValueError("No issue data in payload")

        # Apply all filters
        self._check_comment_body_contains(comment, parameters.get("comment_body_contains"))
        self._check_commenter(payload, parameters.get("commenter"))
        self._check_issue_labels(issue, parameters.get("issue_labels"))
        self._check_issue_state(issue, parameters.get("issue_state"))
        self._check_is_pull_request(issue, parameters.get("is_pull_request"))

        return Variables(variables={**payload})
