from collections.abc import Mapping
from typing import Any

from werkzeug import Request

from dify_plugin.entities.trigger import Event
from dify_plugin.errors.trigger import TriggerIgnoreEventError
from dify_plugin.interfaces.trigger import TriggerEvent


class DiscussionCommentTrigger(TriggerEvent):
    """
    GitHub Discussion Comment Event Trigger

    This unified trigger handles all GitHub discussion comment events and extracts relevant
    information from the webhook payload to provide as variables to the workflow.
    """

    def _trigger(self, request: Request, parameters: Mapping[str, Any]) -> Event:
        """
        Handle GitHub discussion comment event trigger with comprehensive filtering

        Parameters:
        - action_filter: Filter by action type (created, edited, deleted)
        - discussion_categories: Filter by discussion categories
        - exclude_authors: Exclude comments from these authors
        - min_comment_length: Minimum comment length in characters
        - exclude_discussion_authors: Exclude comments on discussions from these authors
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

        # Extract comment, discussion, and other information
        comment = payload.get("comment", {})
        discussion = payload.get("discussion", {})
        repository = payload.get("repository", {})
        sender = payload.get("sender", {})
        changes = payload.get("changes", {})

        # Apply discussion category filter
        discussion_categories_filter = parameters.get("discussion_categories")
        if discussion_categories_filter:
            allowed_categories = [c.strip() for c in discussion_categories_filter.split(",")]
            current_category = discussion.get("category", {}).get("name", "")
            if current_category not in allowed_categories:
                raise TriggerIgnoreEventError(
                    f"Discussion category '{current_category}' not in allowed categories: {allowed_categories}"
                )

        # Apply comment author exclusion filter
        exclude_authors = parameters.get("exclude_authors")
        if exclude_authors:
            excluded = [a.strip() for a in exclude_authors.split(",")]
            comment_author = comment.get("user", {}).get("login", "")
            if comment_author in excluded:
                raise TriggerIgnoreEventError(f"Comment author '{comment_author}' is excluded")

        # Apply discussion author exclusion filter
        exclude_discussion_authors = parameters.get("exclude_discussion_authors")
        if exclude_discussion_authors:
            excluded = [a.strip() for a in exclude_discussion_authors.split(",")]
            discussion_author = discussion.get("user", {}).get("login", "")
            if discussion_author in excluded:
                raise TriggerIgnoreEventError(f"Discussion author '{discussion_author}' is excluded")

        # Apply minimum comment length filter
        min_comment_length = parameters.get("min_comment_length")
        if min_comment_length is not None:
            comment_body = comment.get("body", "")
            if len(comment_body) < int(min_comment_length):
                raise TriggerIgnoreEventError(
                    f"Comment too short: {len(comment_body)} < {min_comment_length} characters"
                )

        # Extract discussion labels
        discussion_labels = [
            {
                "name": label.get("name", ""),
                "color": label.get("color", ""),
                "description": label.get("description", ""),
            }
            for label in discussion.get("labels", [])
        ]

        # Extract discussion category information
        discussion_category = None
        if discussion.get("category"):
            discussion_category = {
                "id": discussion["category"].get("id"),
                "name": discussion["category"].get("name", ""),
                "emoji": discussion["category"].get("emoji", ""),
                "description": discussion["category"].get("description", ""),
                "slug": discussion["category"].get("slug", ""),
            }

        # Extract changes information (for edited action)
        changes_info = {}
        if action == "edited" and changes:
            if "body" in changes:
                changes_info["body"] = {"from": changes["body"].get("from", "")}

        # Build variables for the workflow
        variables = {
            "action": action,
            "comment": {
                "id": comment.get("id"),
                "html_url": comment.get("html_url", ""),
                "body": comment.get("body", ""),
                "user": {
                    "login": comment.get("user", {}).get("login", ""),
                    "avatar_url": comment.get("user", {}).get("avatar_url", ""),
                    "html_url": comment.get("user", {}).get("html_url", ""),
                },
                "created_at": comment.get("created_at", ""),
                "updated_at": comment.get("updated_at", ""),
                "author_association": comment.get("author_association", ""),
                "parent_id": comment.get("parent_id"),
                "child_comment_count": comment.get("child_comment_count", 0),
            },
            "discussion": {
                "id": discussion.get("id"),
                "number": discussion.get("number"),
                "title": discussion.get("title", ""),
                "body": discussion.get("body", ""),
                "state": discussion.get("state", ""),
                "html_url": discussion.get("html_url", ""),
                "category": discussion_category,
                "user": {
                    "login": discussion.get("user", {}).get("login", ""),
                    "avatar_url": discussion.get("user", {}).get("avatar_url", ""),
                    "html_url": discussion.get("user", {}).get("html_url", ""),
                },
                "labels": discussion_labels,
                "locked": discussion.get("locked", False),
                "created_at": discussion.get("created_at", ""),
                "updated_at": discussion.get("updated_at", ""),
                "comments": discussion.get("comments", 0),
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