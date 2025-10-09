from collections.abc import Mapping
from typing import Any

from dify_plugin.errors.trigger import EventIgnoreError
from werkzeug import Request

from dify_plugin.entities.trigger import Variables
from dify_plugin.interfaces.trigger import Event


class CommentDeletedEvent(Event):
    """
    GitHub Issue Comment Deleted Event

    This event transforms GitHub issue comment deleted webhook events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    Works for both issue comments and pull request comments.

    Note: There are known issues with GitHub not reliably sending deleted events.
    This may require "Issues: Read & write" permission to work correctly.
    """

    def _check_comment_body_contains(self, comment: Mapping[str, Any], body_contains_param: str | None) -> None:
        """Check if deleted comment body contained required keywords"""
        if not body_contains_param:
            return

        keywords = [keyword.strip().lower() for keyword in body_contains_param.split(",") if keyword.strip()]
        if not keywords:
            return

        comment_body = (comment.get("body") or "").lower()
        if not any(keyword in comment_body for keyword in keywords):
            raise EventIgnoreError()

    def _check_deleter(self, payload: Mapping[str, Any], deleter_param: str | None) -> None:
        """Check if the deleter is in allowed list"""
        if not deleter_param:
            return

        allowed_deleters = [deleter.strip() for deleter in deleter_param.split(",") if deleter.strip()]
        if not allowed_deleters:
            return

        deleter = payload.get("sender", {}).get("login")
        if deleter not in allowed_deleters:
            raise EventIgnoreError()

    def _check_comment_author(self, comment: Mapping[str, Any], author_param: str | None) -> None:
        """Check if the original comment author is in allowed list"""
        if not author_param:
            return

        allowed_authors = [author.strip() for author in author_param.split(",") if author.strip()]
        if not allowed_authors:
            return

        author = comment.get("user", {}).get("login")
        if author not in allowed_authors:
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

    def _check_is_pull_request(self, issue: Mapping[str, Any], is_pr_param: bool | None) -> None:
        """Check if comment was on a pull request"""
        if is_pr_param is None:
            return

        # Issue has a pull_request key if it's actually a PR
        has_pr_key = "pull_request" in issue

        if is_pr_param != has_pr_key:
            raise EventIgnoreError()

    def _on_event(self, request: Request, parameters: Mapping[str, Any]) -> Variables:
        """
        Transform GitHub issue comment deleted webhook event into structured Variables
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
        self._check_deleter(payload, parameters.get("deleter"))
        self._check_comment_author(comment, parameters.get("comment_author"))
        self._check_issue_labels(issue, parameters.get("issue_labels"))
        self._check_is_pull_request(issue, parameters.get("is_pull_request"))

        return Variables(variables={**payload})
